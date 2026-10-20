"""A minimal LangGraph agent that routes between the pet's twin and the corpus.

The graph has two nodes and one conditional edge:

    START → plan ──(tool calls?)──► use_tools ──► plan
                   │
                   └──(no tool calls)──► END

``plan`` asks the model what to do next, with the two tools advertised. If the
model asks to call a tool, ``use_tools`` runs it and feeds the result back;
otherwise the model's message is the final answer.

This is deliberately small. There is no planner/executor split, no reflection
loop, and no multi-agent choreography — those would add moving parts without
improving an answer that can only draw on one pet's records and a fixed corpus.
The graph exists to make the *routing* explicit and inspectable: every run
records which tools were used, and that trace is returned to the caller.

The model can only reach the two tools it is given. It cannot read arbitrary
records, and there is no tool that writes anything.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Annotated, Any, TypedDict

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from app.agents.tools import AgentContext, read_pet_twin, search_literature

#: Shown with every agent answer.
DISCLAIMER = (
    "This is an assistant summary built from this pet's verified records and "
    "the indexed veterinary documents. It is not a diagnosis and not veterinary "
    "advice. Confirm with a licensed veterinarian before acting on it."
)

SYSTEM_PROMPT = (
    "You are a veterinary assistant helping an owner or clinician understand one "
    "pet. You have two tools:\n"
    "  - read_pet_twin: the pet's verified health state (conditions, symptoms, "
    "medications, allergies, vaccination status, recent history).\n"
    "  - search_literature: passages from an indexed corpus of veterinary "
    "documents.\n\n"
    "Rules you must follow:\n"
    "1. Use read_pet_twin whenever the question is about this specific pet.\n"
    "2. Use search_literature for general clinical questions (vaccination "
    "schedules, disease transmission, symptoms). Often you need both.\n"
    "3. Answer ONLY from the tool results. If they do not cover the question, say "
    "so plainly.\n"
    "4. NEVER give a diagnosis, a prognosis, a drug dose, or a treatment plan. "
    "If asked for one, say that is for a veterinarian to decide and explain what "
    "the records and literature do show.\n"
    "5. Cite literature passages as [1], [2]. Refer to the pet by name.\n"
    "6. Be concise and factual. Do not invent facts.\n"
    "When you have enough information, answer directly without calling more tools."
)

#: The tools advertised to the model, as JSON schemas, plus their implementations.
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_pet_twin",
            "description": (
                "Read the pet's verified Digital Twin: identity, ongoing "
                "conditions, current symptoms, medications, allergies, "
                "vaccination status, and recent verified history."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_literature",
            "description": (
                "Search the indexed veterinary literature for passages about a "
                "clinical topic. Returns numbered passages to cite."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The clinical question or topic to search for.",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "How many passages to return (1-8).",
                        "default": 4,
                    },
                },
                "required": ["query"],
            },
        },
    },
]


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    #: Number of planning turns taken so far, so the step budget counts model
    #: round trips rather than total messages (which includes the prompt).
    steps: int


@dataclass
class AgentRun:
    """The outcome of one agent run, including which tools it used."""

    answer: str
    tools_used: list[str] = field(default_factory=list)
    model: str | None = None
    disclaimer: str = DISCLAIMER


class AgentUnavailableError(RuntimeError):
    """Raised when no LLM is configured or the agent cannot complete."""


def _execute_tool(context: AgentContext, name: str, arguments: dict[str, Any]) -> str:
    if name == "read_pet_twin":
        return read_pet_twin(context)
    if name == "search_literature":
        query = str(arguments.get("query", "")).strip()
        if not query:
            return "No query was provided to the literature search."
        return search_literature(context, query, top_k=arguments.get("top_k", 4))
    return f"Unknown tool: {name}"


def _parse_arguments(raw: Any) -> dict[str, Any]:
    """Tool arguments arrive as a JSON string from the chat API, or already dict."""
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else {}
    except (ValueError, TypeError):
        return {}


def _coerce_tool_calls(message: AIMessage) -> list[tuple[str, str, dict[str, Any]]]:
    """Normalise the several tool-call shapes into (id, name, arguments)."""
    calls: list[tuple[str, str, dict[str, Any]]] = []
    for call in getattr(message, "tool_calls", None) or []:
        # LangChain normalised form: {"name": ..., "args": {...}, "id": ...}
        name = call.get("name")
        if not name:
            continue
        calls.append(
            (
                call.get("id") or name,
                name,
                _parse_arguments(call.get("args")),
            )
        )

    if calls:
        return calls

    # Fallback: the raw OpenAI/Groq shape, where arguments are a JSON string.
    for call in getattr(message, "additional_kwargs", {}).get("tool_calls", []) or []:
        function = call.get("function", {})
        name = function.get("name")
        if not name:
            continue
        calls.append(
            (
                call.get("id") or name,
                name,
                _parse_arguments(function.get("arguments")),
            )
        )
    return calls


def build_agent_graph(model: Any, context: AgentContext, *, max_steps: int = 6):
    """Compile the graph with ``model`` and ``context`` bound in.

    ``max_steps`` caps the number of tool-using planning turns. A ``finalize``
    node runs once when the loop stops and always produces prose: if the budget
    is spent while the model was still asking for tools, the final call is made
    without tools so there is always an answer rather than a dangling tool call.
    """
    bound_model = model.bind_tools(TOOL_SCHEMAS)

    def plan(state: AgentState) -> AgentState:
        response = bound_model.invoke(state["messages"])
        return {"messages": [response], "steps": state.get("steps", 0) + 1}

    def use_tools(state: AgentState) -> AgentState:
        last = state["messages"][-1]
        assert isinstance(last, AIMessage)
        results: list[BaseMessage] = []
        for call_id, name, arguments in _coerce_tool_calls(last):
            output = _execute_tool(context, name, arguments)
            results.append(ToolMessage(content=output, tool_call_id=call_id))
        return {"messages": results}

    def finalize(state: AgentState) -> AgentState:
        """Force a text answer with tools disabled.

        Used only when the step budget ran out mid-loop. ``bind_tools`` is not
        applied here, so the model cannot ask for another tool and must answer
        from what it already gathered.
        """
        messages = list(state["messages"])
        messages.append(
            HumanMessage(
                content=(
                    "Answer now using only the tool results above. Do not request "
                    "more tools. If the information is insufficient, say so."
                )
            )
        )
        response = _invoke_without_tools(model, messages)
        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        if state.get("steps", 0) >= max_steps:
            return "finalize"
        last = state["messages"][-1]
        if isinstance(last, AIMessage) and _has_tool_calls(last):
            return "use_tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("plan", plan)
    graph.add_node("use_tools", use_tools)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "plan")
    graph.add_conditional_edges(
        "plan",
        should_continue,
        {"use_tools": "use_tools", "finalize": "finalize", END: END},
    )
    graph.add_edge("use_tools", "plan")
    graph.add_edge("finalize", END)
    return graph.compile()


def _has_tool_calls(message: AIMessage) -> bool:
    if getattr(message, "tool_calls", None):
        return True
    return bool(getattr(message, "additional_kwargs", {}).get("tool_calls"))


def _invoke_without_tools(raw_model: Any, messages: list[BaseMessage]) -> AIMessage:
    """Call the underlying model with no tools bound, tolerating either shape."""
    # A LangChain chat model supports ``invoke``; the fake models used in tests do
    # too. If the passed object is itself the bound wrapper, ``model`` unwrapping
    # above gives the unbound original.
    try:
        return raw_model.invoke(messages)
    except Exception:  # pragma: no cover - defensive; tests use a fake
        return AIMessage(
            content=(
                "I could not produce a final answer from the available "
                "information. Please rephrase, or consult a veterinarian."
            )
        )


def run_agent(
    model: Any,
    context: AgentContext,
    question: str,
    *,
    model_name: str | None = None,
    max_steps: int = 6,
) -> AgentRun:
    """Run the graph for one question and return the answer plus the tool trace."""
    app = build_agent_graph(model, context, max_steps=max_steps)
    initial: AgentState = {
        "messages": [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=question)],
        "steps": 0,
    }
    final_state = app.invoke(initial)

    messages = final_state["messages"]
    tools_used: list[str] = []
    for message in messages:
        if isinstance(message, AIMessage):
            for _, name, _ in _coerce_tool_calls(message):
                if name not in tools_used:
                    tools_used.append(name)

    answer = ""
    for message in reversed(messages):
        if isinstance(message, AIMessage) and message.content:
            answer = str(message.content).strip()
            break

    if not answer:
        answer = (
            "I could not produce an answer from this pet's records and the "
            "indexed documents. Please rephrase, or consult a veterinarian."
        )

    return AgentRun(answer=answer, tools_used=tools_used, model=model_name)
