"""Tools the PetTwin agent may call.

Two tools, and deliberately no more:

* :func:`read_pet_twin` — returns a compact summary of the pet's **verified**
  Digital Twin. The twin is assembled by ``digital_twin_service`` under the
  caller's access grant, so the agent can only ever see a pet the user can see.
* :func:`search_literature` — retrieves passages from the indexed veterinary
  corpus via the Phase 5 RAG store.

Neither tool writes anything, and neither exposes an endpoint the caller could
not already reach on their own. The agent adds routing and prose, not new access.

The functions here take an :class:`AgentContext` rather than reaching for the
database or the embedding model directly. That keeps them callable in tests
without a live DB or network, and makes it obvious that the twin was already
authorized before the agent ran.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.rag.store import RetrievedChunk


@dataclass
class AgentContext:
    """Everything the tools are allowed to touch, assembled by the caller.

    ``twin_snapshot`` is the dict returned by ``build_digital_twin`` for a pet
    the caller has already been authorized against. ``retrieve`` is the RAG
    search function; it defaults to the real store and is replaced in tests.
    ``predict`` returns ranked condition candidates for the pet (Phase 7) and is
    injected by the service so tests can substitute a fake.
    """

    twin_snapshot: dict[str, Any]
    retrieve: Callable[..., list[RetrievedChunk]] = field(default=None)  # type: ignore[assignment]
    predict: Callable[[], list[dict[str, Any]]] = field(default=None)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.retrieve is None:
            from app.rag.store import search

            self.retrieve = search


# Hard cap on how much twin text is handed to the model. A large history should
# not silently consume the whole context window; the summary is meant to orient
# the model, and it can ask a narrower question rather than receive everything.
MAX_TWIN_CHARS = 6000


def _format_value(value: Any) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def summarize_twin(snapshot: dict[str, Any]) -> str:
    """Turn the twin dict into a short, model-readable text block.

    Only fields a clinician would use to answer a question are kept. Provenance
    counts and id fields are dropped: they are for the UI, and they would waste
    the model's attention without changing any answer.
    """
    profile = snapshot.get("profile", {})
    status = snapshot.get("current_health_status", {})
    lines: list[str] = []

    name = profile.get("name", "the pet")
    species = profile.get("species", "unknown species")
    breed = profile.get("breed")
    sex = profile.get("sex", "unknown")
    age = profile.get("age")
    age_text = ""
    if isinstance(age, dict) and age.get("total_months") is not None:
        years, months = divmod(int(age["total_months"]), 12)
        age_text = f", {years}y {months}m" if years else f", {months}m"
    header = f"{name} — {species}"
    if breed:
        header += f" ({breed})"
    header += f", {sex}{age_text}"
    lines.append(header)

    weight = status.get("weight_kg")
    if weight is not None:
        lines.append(f"Weight: {weight} kg")

    conditions = status.get("existing_conditions") or []
    if conditions:
        names = ", ".join(c.get("name", "?") for c in conditions)
        lines.append(f"Ongoing conditions: {names}")

    symptoms = status.get("current_symptoms") or []
    if symptoms:
        names = ", ".join(s.get("name", "?") for s in symptoms)
        lines.append(f"Current symptoms: {names}")

    medications = status.get("current_medications") or []
    if medications:
        parts = []
        for m in medications:
            detail = m.get("name", "?")
            dose = " ".join(
                filter(None, [m.get("dose"), m.get("route"), m.get("frequency")])
            )
            parts.append(f"{detail} ({dose})" if dose else detail)
        lines.append(f"Current medications: {', '.join(parts)}")

    allergies = status.get("allergies") or []
    if allergies:
        parts = []
        for a in allergies:
            allergen = a.get("allergen", "?")
            reaction = a.get("reaction")
            parts.append(f"{allergen} ({reaction})" if reaction else allergen)
        lines.append(f"Allergies: {', '.join(parts)}")

    vaccination = status.get("vaccination_status") or {}
    if vaccination:
        line = f"Vaccination status: {vaccination.get('status', 'unknown')}"
        overdue = vaccination.get("overdue") or []
        if overdue:
            names = ", ".join(v.get("vaccine", "?") for v in overdue)
            line += f"; overdue: {names}"
        lines.append(line)

    history = snapshot.get("medical_history") or []
    if history:
        recent = history[:8]
        entries = "; ".join(
            f"{h.get('occurred_at', '?')} {h.get('title', '?')}" for h in recent
        )
        lines.append(f"Recent verified history: {entries}")

    text = "\n".join(lines)
    if len(text) > MAX_TWIN_CHARS:
        text = text[:MAX_TWIN_CHARS] + "\n…(truncated)"
    return text


def read_pet_twin(context: AgentContext) -> str:
    """Tool: read the pet's verified Digital Twin as a short text summary."""
    if not context.twin_snapshot:
        return "No Digital Twin is available for this pet."
    return summarize_twin(context.twin_snapshot)


def suggest_conditions(context: AgentContext) -> str:
    """Tool: rank possible conditions from recorded cases using the pet's symptoms.

    Returns evidence from the Phase 7 predictor (case counts and average
    resemblance) rather than probabilities. If no predictor is bound or no
    symptoms are present, the result is reported plainly so the model does not
    guess.
    """
    if context.predict is None:
        return "Condition prediction is not available for this request."
    try:
        candidates = context.predict()
    except Exception as exc:
        return f"Condition prediction could not be run: {exc}"
    if not candidates:
        return "No similar recorded cases were found to rank possible conditions."

def search_literature(context: AgentContext, query: str, top_k: int = 4) -> str:
    """Tool: retrieve veterinary literature passages for ``query``.

    Returns a numbered block so the model can cite passages as ``[1]``, matching
    the Phase 5 answer format. An empty result is reported as such rather than
    left blank, so the model knows the corpus did not cover it.
    """
    top_k = max(1, min(int(top_k), 8))
    passages = context.retrieve(query, top_k=top_k, min_score=0.25)
    if not passages:
        return "No passages in the indexed documents matched that query."
    blocks = []
    for i, passage in enumerate(passages, start=1):
        blocks.append(
            f"[{i}] (source: {passage.source}, page {passage.page})\n{passage.text}"
        )
    return "\n\n".join(blocks)
