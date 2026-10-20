"""Turn cases and pets into comparable feature text for the embedding model.

Both sides of the search reduce to one short, structured string. Keeping the
format identical on both sides is what makes the cosine similarity meaningful:
the pet's query text and a stored case's text are built by the same function, so
"coughing" and "Coughing" never diverge, and the same species always appears in
the same position.

The representation is intentionally simple — a bag of clinical tokens, not a
trained model. It has to work with 431 examples, and a model with learned weights
would not have enough data to learn anything trustworthy.
"""

from __future__ import annotations

from app.ml.dataset import CaseRecord

#: Weight bands, so a 4.5 kg cat and a 600 kg cow are not compared by raw number.
_WEIGHT_BANDS = (
    (0, 5, "very small"),
    (5, 15, "small"),
    (15, 30, "medium"),
    (30, 60, "large"),
    (60, 200, "very large"),
    (200, 10_000, "giant"),
)


def _age_band(years: float | None) -> str | None:
    if years is None:
        return None
    if years < 1:
        return "infant"
    if years < 3:
        return "young"
    if years < 8:
        return "adult"
    return "senior"


def _weight_band(kg: float | None) -> str | None:
    if kg is None:
        return None
    for low, high, label in _WEIGHT_BANDS:
        if low <= kg < high:
            return label
    return None


def _tokenize_length(text: str | None) -> str | None:
    """Bucket the free-text duration ("3 days") into a coarse token."""
    if not text:
        return None
    lowered = text.strip().lower()
    if "hour" in lowered:
        return "duration hours"
    if "day" in lowered:
        return "duration days"
    if "week" in lowered:
        return "duration weeks"
    if "month" in lowered:
        return "duration months"
    if "year" in lowered:
        return "duration years"
    return "duration chronic"


def _temperature_token(celsius: float | None) -> str | None:
    if celsius is None:
        return None
    if celsius >= 39.5:
        return "high fever"
    if celsius >= 39.0:
        return "fever"
    if celsius < 37.5:
        return "low temperature"
    return "normal temperature"


def features_for_case(case: CaseRecord) -> str:
    """Build the feature string for a stored case."""
    parts = [f"species {case.animal_type.lower()}"]
    if case.breed:
        parts.append(f"breed {case.breed.lower()}")
    if case.gender:
        parts.append(f"sex {case.gender.lower()}")
    age_band = _age_band(case.age_years)
    if age_band:
        parts.append(f"age {age_band}")
    weight_band = _weight_band(case.weight_kg)
    if weight_band:
        parts.append(f"size {weight_band}")
    parts.append(_tokenize_length(case.duration) or "")
    parts.append(_temperature_token(case.body_temperature_c) or "")
    # The same clinical concept can appear both as a Symptom_n value and as a
    # Yes flag (e.g. "Vomiting" plus Vomiting=Yes). Emitting it twice would
    # double its weight in the embedding, so identical tokens are collapsed.
    seen: set[str] = set()
    for symptom in case.symptoms:
        token = f"symptom {symptom.strip().lower()}"
        if token not in seen:
            seen.add(token)
            parts.append(token)
    for flag in case.flags:
        token = f"symptom {flag}"
        if token not in seen:
            seen.add(token)
            parts.append(token)
    return " ".join(part for part in parts if part)


#: Map the pet's species to the dataset's vocabulary (singular, capitalised).
_SPECIES_ALIASES = {
    "dog": "Dog",
    "cat": "Cat",
    "cow": "Cow",
    "cattle": "Cow",
    "horse": "Horse",
    "sheep": "Sheep",
    "goat": "Goat",
    "pig": "Pig",
    "swine": "Pig",
    "rabbit": "Rabbit",
}


def _species_alias(species: str | None) -> str | None:
    if not species:
        return None
    return _SPECIES_ALIASES.get(species.strip().lower(), species.strip().capitalize())


def features_for_pet(
    *,
    species: str | None,
    breed: str | None,
    sex: str | None,
    age_months: int | None,
    weight_kg: float | None,
    symptom_names: list[str],
) -> str:
    """Build the feature string for a pet, in the same shape as a case.

    ``symptom_names`` are the pet's current symptom names from the twin. They are
    appended as ``symptom <name>`` tokens exactly like the dataset's own symptom
    and flag tokens, which is what lets the two sides line up.
    """
    return features_for_symptoms(
        species=species,
        breed=breed,
        sex=sex,
        age_months=age_months,
        weight_kg=weight_kg,
        symptoms=symptom_names,
    )


def features_for_symptoms(
    *,
    species: str | None,
    breed: str | None,
    sex: str | None,
    age_months: int | None,
    weight_kg: float | None,
    symptoms: list[str],
) -> str:
    """Build the feature string from explicit inputs.

    This is the shared core behind :func:`features_for_pet` and the user-editable
    symptom picker. Producing the query through one path guarantees a pet's
    features and a hand-entered symptom set are encoded identically.
    """
    parts: list[str] = []
    alias = _species_alias(species)
    if alias:
        parts.append(f"species {alias.lower()}")
    if breed:
        parts.append(f"breed {breed.lower()}")
    if sex:
        parts.append(f"sex {sex.lower()}")
    age_band = _age_band(age_months / 12 if age_months is not None else None)
    if age_band:
        parts.append(f"age {age_band}")
    weight_band = _weight_band(weight_kg)
    if weight_band:
        parts.append(f"size {weight_band}")
    for name in symptoms:
        cleaned = (name or "").strip().lower()
        token = f"symptom {cleaned}"
        if cleaned and token not in parts:
            parts.append(token)
    return " ".join(parts)
