"""Phase 6 tests — the tool-using agent over a pet's twin and the corpus.

These run entirely offline. The chat model is replaced with a scripted fake and
the retriever with a fixed list, so the tests exercise the graph's routing, the
tool implementations, and the API's authorization without a network call or a
live embedding model. What is under test is the wiring and the guardrails, not
the quality of any particular LLM answer.
"""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import AIMessage

from app.agents import graph as graph_module
from app.agents import service as service_module
from app.agents.graph import run_agent
from app.agents.tools import (
    AgentContext,
    read_pet_twin,
    search_literature,
    summarize_twin,
)

TWIN = {
    "profile": {
        "name": "Rex",
        "species": "dog",
        "breed": "Beagle",
        "sex": "male",
        "age": {"total_months": 26},
    },
    "current_health_status": {
        "existing_conditions": [{"name": "Otitis"}],
        "current_symptoms": [],
        "current_medications": [],
        "allergies": [{"allergen": "Chicken", "reaction": "itching"}],
        "vaccination_status": {
            "status": "overdue",
            "overdue": [{"vaccine": "Rabies"}],
        },
        "weight_kg": 12.4,
    },
    "medical_history": [{"occurred_at": "2026-02-01", "title": "Ear check"}],
}


@dataclass
class Hit:
    text: str
    source: str
    page: int
    score: float


def fake_retrieve(query, top_k=4, min_score=0.0):
    return [
        Hit("Core vaccines protect against parvovirus.", "WSAVA.pdf", 11, 0.9),
        Hit("Boosters are given annually.", "WSAVA.pdf", 14, 0.84),
    ][:top_k]


class ScriptedModel:
    """A fake chat model that returns a fixed sequence of messages.

    It also records the prompts it received so a test can assert what the agent
    actually sent to the model.
    """

    def __init__(self, script):
        self.script = list(script)
        self.invocations = []
        self.tools_bound = None

    def bind_tools(self, schemas):
        self.tools_bound = schemas
        return self

    def invoke(self, messages):
        self.invocations.append(messages)
        if len(self.script) > 1:
            return self.script.pop(0)
        return self.script[0]


def tool_call_message(*calls):
    message = AIMessage(content="")
    message.tool_calls = [
        {"name": name, "args": args, "id": f"call-{i}"}
        for i, (name, args) in enumerate(calls)
    ]
    return message


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
def test_read_pet_twin_summarizes_only_signal() -> None:
    context = AgentContext(twin_snapshot=TWIN, retrieve=fake_retrieve)
    summary = read_pet_twin(context)

    assert "Rex" in summary
    assert "dog" in summary
    assert "Otitis" in summary
    assert "Chicken" in summary
    assert "overdue" in summary
    # Provenance/id noise must not be handed to the model.
    assert "id:" not in summary


def test_read_pet_twin_handles_missing_twin() -> None:
    context = AgentContext(twin_snapshot={}, retrieve=fake_retrieve)
    assert "No Digital Twin" in read_pet_twin(context)


def test_summarize_twin_is_bounded() -> None:
    """A huge history must be truncated, not passed through in full."""
    huge = {
        "profile": {"name": "Rex", "species": "dog", "sex": "male"},
        "current_health_status": {},
        "medical_history": [
            {"occurred_at": "2026-01-01", "title": "x" * 200} for _ in range(200)
        ],
    }
    assert len(summarize_twin(huge)) <= 6200


def test_search_literature_numbers_passages() -> None:
    context = AgentContext(twin_snapshot=TWIN, retrieve=fake_retrieve)
    output = search_literature(context, "vaccines", top_k=2)
    assert "[1]" in output and "[2]" in output
    assert "WSAVA.pdf" in output


def test_search_literature_reports_empty_result() -> None:
    context = AgentContext(twin_snapshot=TWIN, retrieve=lambda q, **k: [])
    output = search_literature(context, "capital of france")
    assert "No passages" in output


# ---------------------------------------------------------------------------
# Graph routing
# ---------------------------------------------------------------------------
def test_agent_uses_tool_then_answers() -> None:
    model = ScriptedModel(
        [
            tool_call_message(("read_pet_twin", {})),
            AIMessage(content="Rex is overdue for Rabies."),
        ]
    )
    context = AgentContext(twin_snapshot=TWIN, retrieve=fake_retrieve)

    run = run_agent(model, context, "Is Rex up to date?", model_name="fake")

    assert run.answer == "Rex is overdue for Rabies."
    assert run.tools_used == ["read_pet_twin"]
    assert run.disclaimer


def test_agent_can_use_both_tools() -> None:
    model = ScriptedModel(
        [
            tool_call_message(
                ("read_pet_twin", {}),
                ("search_literature", {"query": "vaccines", "top_k": 2}),
            ),
            AIMessage(content="Answer with citations [1][2]."),
        ]
    )
    context = AgentContext(twin_snapshot=TWIN, retrieve=fake_retrieve)

    run = run_agent(model, context, "vaccine schedule?")

    assert set(run.tools_used) == {"read_pet_twin", "search_literature"}


def test_agent_answers_without_tools() -> None:
    model = ScriptedModel([AIMessage(content="I need the records to answer.")])
    context = AgentContext(twin_snapshot=TWIN, retrieve=fake_retrieve)

    run = run_agent(model, context, "what is a dog?")

    assert run.tools_used == []
    assert run.answer == "I need the records to answer."


def test_agent_stops_at_max_steps() -> None:
    """A model that only ever calls tools must not loop forever."""
    forever = [tool_call_message(("read_pet_twin", {})) for _ in range(10)]

    class Looping(ScriptedModel):
        def invoke(self, messages):
            self.invocations.append(messages)
            return forever[0]

    model = Looping(forever)
    context = AgentContext(twin_snapshot=TWIN, retrieve=fake_retrieve)

    run = run_agent(model, context, "loop?", max_steps=2)

    # Two planning calls plus one forced finalize call — never unbounded.
    assert len(model.invocations) == 3
    # The finalize turn still yields text, so the caller never gets an empty answer.
    assert run.answer
    assert run.tools_used == ["read_pet_twin"]


def test_budget_exhaustion_still_produces_answer() -> None:
    """When the loop is cut off, the forced final turn supplies the answer."""

    class AlwaysTool(ScriptedModel):
        def invoke(self, messages):
            self.invocations.append(messages)
            # The finalize call receives the extra instruction appended; answer
            # to it, keep calling tools otherwise.
            if messages and "Answer now" in str(messages[-1].content):
                return AIMessage(content="Refusal after gathering context.")
            return tool_call_message(("search_literature", {"query": "x"}))

    model = AlwaysTool([])
    context = AgentContext(twin_snapshot=TWIN, retrieve=fake_retrieve)

    run = run_agent(model, context, "prescribe something", max_steps=2)

    assert run.answer == "Refusal after gathering context."


def test_system_prompt_forbids_diagnosis() -> None:
    """The guardrail must be in the prompt actually sent to the model."""
    model = ScriptedModel([AIMessage(content="ok")])
    context = AgentContext(twin_snapshot=TWIN, retrieve=fake_retrieve)

    run_agent(model, context, "diagnose my dog")

    system_message = model.invocations[0][0]
    assert "read_pet_twin first" in system_message.content
    assert "predict_conditions" in system_message.content
    assert "not a confirmed diagnosis" in system_message.content
    assert "drug doses unless" in system_message.content
    assert "NEVER give a diagnosis" not in system_message.content


# ---------------------------------------------------------------------------
# Service + API
# ---------------------------------------------------------------------------
def test_ask_endpoint_requires_authentication(client, owner_pet) -> None:
    response = client.post(
        f"/api/pets/{owner_pet['id']}/ask", json={"question": "is Rex healthy?"}
    )
    assert response.status_code == 401


def test_ask_endpoint_rejects_short_question(client, owner_pet, owner_token) -> None:
    response = client.post(
        f"/api/pets/{owner_pet['id']}/ask",
        json={"question": "x"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 422


def test_ask_endpoint_returns_503_without_model(
    client, owner_pet, owner_token, monkeypatch
) -> None:
    monkeypatch.setattr(service_module.settings, "groq_api_key", "")

    response = client.post(
        f"/api/pets/{owner_pet['id']}/ask",
        json={"question": "is Rex healthy?"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 503


def test_ask_endpoint_happy_path(client, owner_pet, owner_token, monkeypatch) -> None:
    """The endpoint wires the graph to real records and returns the trace."""
    monkeypatch.setattr(
        service_module,
        "_build_model",
        lambda: ScriptedModel(
            [
                tool_call_message(("read_pet_twin", {})),
                AIMessage(content="Rex has no recorded conditions."),
            ]
        ),
    )
    monkeypatch.setattr(graph_module, "search_literature", lambda *a, **k: "no passages")

    response = client.post(
        f"/api/pets/{owner_pet['id']}/ask",
        json={"question": "what conditions does Rex have?"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["pet_id"] == owner_pet["id"]
    assert body["tools_used"] == ["read_pet_twin"]
    assert body["read_only"] is True
    assert "clinical decision support" in body["disclaimer"].lower()


def test_ask_endpoint_hides_another_users_pet(
    client, intruder_pet, owner_token
) -> None:
    """A pet owned by someone else must 404, not answer."""
    response = client.post(
        f"/api/pets/{intruder_pet['id']}/ask",
        json={"question": "tell me about this pet"},
        headers={"Authorization": f"Bearer {owner_token}"},
    )
    assert response.status_code == 404
