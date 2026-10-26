"""Digital Twin router — the assembled health-state endpoints.

Two endpoints:

* ``GET /pets/{pet_id}/digital-twin`` — the full assembled twin.
* ``GET /pets/{pet_id}/health-timeline`` — just the chronological event list.

Both authorize through ``load_accessible_pet``, so a pet belonging to another
user returns 404 and never reaches the assembly step. Neither endpoint writes
anything: the twin is computed per request and discarded afterwards.
"""

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Path, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.digital_twin import (
    DigitalTwinResponse,
    HealthTimelineResponse,
)
from app.services.authorization import load_accessible_pet
from app.services.digital_twin_service import build_digital_twin
from app.services.timeline_service import build_health_timeline

router = APIRouter(prefix="/pets/{pet_id}", tags=["digital twin"])

PetPath = Annotated[uuid.UUID, Path(description="Target pet id")]


@router.get(
    "/digital-twin",
    response_model=DigitalTwinResponse,
    summary="Assembled Digital Twin for this pet",
)
def get_digital_twin(
    pet_id: PetPath, db: DbSession, current_user: CurrentUser
) -> DigitalTwinResponse:
    """Return the pet's current health state, assembled from its records.

    Recomputed on every call from the clinical records, so it always reflects
    the latest saved data. It reports verified facts plus counts and date
    arithmetic; it performs no inference of its own.
    """
    load_accessible_pet(db, pet_id=pet_id, user_id=current_user.id)
    snapshot = build_digital_twin(db, pet_id=pet_id, user_id=current_user.id)
    return DigitalTwinResponse(**snapshot)


@router.get(
    "/health-timeline",
    response_model=HealthTimelineResponse,
    summary="Chronological health events for this pet",
)
def get_health_timeline(
    pet_id: PetPath,
    db: DbSession,
    current_user: CurrentUser,
    verified_only: Annotated[
        bool, Query(description="Exclude records that are not yet verified")
    ] = True,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> HealthTimelineResponse:
    """Return every recorded clinical event, newest first.

    The timeline is derived by merging the typed record tables with the
    narrative log, then sorting. It is not stored, so it cannot fall out of step
    with the records it describes.

    ``total`` is the number of events matching the filter, not the size of the
    returned page. Reporting the truncated length instead would make the count
    shrink as the caller pages further, so the merged list is assembled in full
    and then windowed. A single pet's history is small enough that this costs
    little, and it keeps the arithmetic honest.
    """
    load_accessible_pet(db, pet_id=pet_id, user_id=current_user.id)
    events = build_health_timeline(db, pet_id=pet_id, verified_only=verified_only)
    window = events[offset : offset + limit]
    return HealthTimelineResponse(
        pet_id=str(pet_id),
        generated_at=datetime.now(timezone.utc),
        verified_only=verified_only,
        total=len(events),
        items=window,
    )
