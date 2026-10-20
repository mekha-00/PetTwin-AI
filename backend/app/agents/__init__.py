"""A small, read-only agent over one pet's Digital Twin and the RAG corpus.

The agent is a two-node LangGraph loop: it plans, optionally calls one of two
tools, and repeats until it answers.

* :mod:`app.agents.tools` exposes the two tools — ``read_pet_twin`` (the pet's
  verified health state) and ``search_literature`` (passages from the indexed
  veterinary documents) — over an explicit :class:`~app.agents.tools.AgentContext`.
* :mod:`app.agents.graph` builds and runs the graph and returns the answer plus
  the list of tools that were used.
* :mod:`app.agents.service` assembles the twin, builds the model from settings,
  and is what the API calls.

There is no tool that writes, diagnoses, or prescribes. The agent can only use
material the caller already has access to.
"""

from app.agents.graph import AgentRun, AgentUnavailableError, run_agent
from app.agents.service import answer_pet_question

__all__ = ["AgentRun", "AgentUnavailableError", "answer_pet_question", "run_agent"]
