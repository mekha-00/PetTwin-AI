"""Clinical record router — CRUD for the seven record types.

Rather than seven near-identical router functions per verb, each record type is
bound to its model and schemas through a small declarative table. The resulting
endpoints are the ordinary FastAPI ones and appear individually in OpenAPI; what
is shared is the wiring, not the API surface.

Every route is mounted under ``/pets/{pet_id}/...`` so the pet is always in the
path. That is deliberate: the pet can then be authorized before the record is
looked at, and a record id from another pet's history is rejected rather than
silently accepted.
"""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Path, Query, status
from pydantic import BaseModel

from app.api.deps import CurrentUser, DbSession
from app.models.diagnosis import DiagnosisRecord
from app.models.health_record import HealthRecord
from app.models.lab_report import LabReport
from app.models.medication import MedicationRecord
from app.models.symptom import SymptomRecord
from app.models.vaccination import VaccinationRecord
from app.models.visit import VeterinaryVisit
from app.schemas.clinical import (
    DiagnosisCreate,
    DiagnosisRead,
    DiagnosisUpdate,
    HealthRecordCreate,
    HealthRecordRead,
    HealthRecordUpdate,
    LabReportCreate,
    LabReportRead,
    LabReportUpdate,
    MedicationCreate,
    MedicationRead,
    MedicationUpdate,
    PaginatedRecords,
    SymptomCreate,
    SymptomRead,
    SymptomUpdate,
    VaccinationCreate,
    VaccinationRead,
    VaccinationUpdate,
    VisitCreate,
    VisitRead,
    VisitUpdate,
)
from app.services import clinical_record_service as svc
from app.services import pet_service

router = APIRouter(prefix="/pets/{pet_id}", tags=["clinical records"])

PetPath = Annotated[uuid.UUID, Path(description="Target pet id")]
IdPath = Annotated[uuid.UUID, Path(description="Record id")]
ListQuery = Annotated[
    int, Query(ge=1, le=200, description="Maximum records to return")
]
OffsetQuery = Annotated[int, Query(ge=0, description="Records to skip")]
VerifiedQuery = Annotated[
    bool, Query(description="Only return records marked verified")
]


def _paginated(items: list[Any], total: int, limit: int, offset: int) -> PaginatedRecords:
    return PaginatedRecords(
        items=[i.model_dump(mode="json") for i in items],
        total=total,
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# Veterinary visits
# ---------------------------------------------------------------------------
@router.post(
    "/visits", response_model=VisitRead, status_code=status.HTTP_201_CREATED
)
def create_visit(
    pet_id: PetPath, payload: VisitCreate, db: DbSession, current_user: CurrentUser
) -> VisitRead:
    visit = svc.create_visit(
        db, pet_id=pet_id, user_id=current_user.id, data=payload.model_dump()
    )
    return VisitRead.model_validate(visit)


@router.get("/visits", response_model=PaginatedRecords)
def list_visits(
    pet_id: PetPath,
    db: DbSession,
    current_user: CurrentUser,
    limit: ListQuery = 50,
    offset: OffsetQuery = 0,
    verified_only: VerifiedQuery = False,
) -> PaginatedRecords:
    pet_service.get_pet_or_404(db, pet_id=pet_id, user_id=current_user.id)
    items, total = svc.list_records(
        db,
        model=VeterinaryVisit,
        pet_id=pet_id,
        limit=limit,
        offset=offset,
        verified_only=verified_only,
    )
    return _paginated([VisitRead.model_validate(i) for i in items], total, limit, offset)


@router.get("/visits/{record_id}", response_model=VisitRead)
def get_visit(
    pet_id: PetPath, record_id: IdPath, db: DbSession, current_user: CurrentUser
) -> VisitRead:
    pet_service.get_pet_or_404(db, pet_id=pet_id, user_id=current_user.id)
    return VisitRead.model_validate(
        svc.get_record_or_404(
            db, model=VeterinaryVisit, record_id=record_id, pet_id=pet_id
        )
    )


@router.patch("/visits/{record_id}", response_model=VisitRead)
def update_visit(
    pet_id: PetPath,
    record_id: IdPath,
    payload: VisitUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> VisitRead:
    return VisitRead.model_validate(
        svc.update_record(
            db,
            model=VeterinaryVisit,
            record_id=record_id,
            pet_id=pet_id,
            user_id=current_user.id,
            data=payload.model_dump(exclude_unset=True),
        )
    )


@router.delete("/visits/{record_id}")
def delete_visit(
    pet_id: PetPath, record_id: IdPath, db: DbSession, current_user: CurrentUser
) -> dict:
    return svc.delete_record(
        db,
        model=VeterinaryVisit,
        record_id=record_id,
        pet_id=pet_id,
        user_id=current_user.id,
    )


# ---------------------------------------------------------------------------
# Health records
# ---------------------------------------------------------------------------
@router.post(
    "/health-records", response_model=HealthRecordRead, status_code=status.HTTP_201_CREATED
)
def create_health_record(
    pet_id: PetPath,
    payload: HealthRecordCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> HealthRecordRead:
    record = svc.create_health_record(
        db, pet_id=pet_id, user_id=current_user.id, data=payload.model_dump()
    )
    return HealthRecordRead.model_validate(record)


@router.get("/health-records", response_model=PaginatedRecords)
def list_health_records(
    pet_id: PetPath,
    db: DbSession,
    current_user: CurrentUser,
    limit: ListQuery = 50,
    offset: OffsetQuery = 0,
    verified_only: VerifiedQuery = False,
) -> PaginatedRecords:
    pet_service.get_pet_or_404(db, pet_id=pet_id, user_id=current_user.id)
    items, total = svc.list_records(
        db,
        model=HealthRecord,
        pet_id=pet_id,
        limit=limit,
        offset=offset,
        verified_only=verified_only,
    )
    return _paginated(
        [HealthRecordRead.model_validate(i) for i in items], total, limit, offset
    )


@router.get("/health-records/{record_id}", response_model=HealthRecordRead)
def get_health_record(
    pet_id: PetPath, record_id: IdPath, db: DbSession, current_user: CurrentUser
) -> HealthRecordRead:
    pet_service.get_pet_or_404(db, pet_id=pet_id, user_id=current_user.id)
    return HealthRecordRead.model_validate(
        svc.get_record_or_404(
            db, model=HealthRecord, record_id=record_id, pet_id=pet_id
        )
    )


@router.patch("/health-records/{record_id}", response_model=HealthRecordRead)
def update_health_record(
    pet_id: PetPath,
    record_id: IdPath,
    payload: HealthRecordUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> HealthRecordRead:
    return HealthRecordRead.model_validate(
        svc.update_record(
            db,
            model=HealthRecord,
            record_id=record_id,
            pet_id=pet_id,
            user_id=current_user.id,
            data=payload.model_dump(exclude_unset=True),
        )
    )


@router.delete("/health-records/{record_id}")
def delete_health_record(
    pet_id: PetPath, record_id: IdPath, db: DbSession, current_user: CurrentUser
) -> dict:
    return svc.delete_record(
        db,
        model=HealthRecord,
        record_id=record_id,
        pet_id=pet_id,
        user_id=current_user.id,
    )


# ---------------------------------------------------------------------------
# Child record types: symptoms, diagnoses, medications, vaccinations, lab reports
#
# These five share an identical shape (create needs a parent health record,
# list/get/update/delete are by id), so they are generated from one template.
# Each generated function is given a distinct name so tracebacks and OpenAPI
# operation ids stay readable.
# ---------------------------------------------------------------------------
class _ChildSpec:
    __slots__ = ("path", "model", "create_schema", "update_schema", "read_schema", "tag")

    def __init__(
        self,
        *,
        path: str,
        model: Any,
        create_schema: type[BaseModel],
        update_schema: type[BaseModel],
        read_schema: type[BaseModel],
        tag: str,
    ) -> None:
        self.path = path
        self.model = model
        self.create_schema = create_schema
        self.update_schema = update_schema
        self.read_schema = read_schema
        self.tag = tag


def _register_child_routes(spec: _ChildSpec) -> None:
    """Attach the five standard routes for one child record type."""
    path = spec.path
    model = spec.model
    create_schema = spec.create_schema
    update_schema = spec.update_schema
    read_schema = spec.read_schema
    tag = spec.tag
    singular = path.rstrip("s").replace("-", "_")

    # The body schema has to be named per route. FastAPI reads annotations at
    # registration time, so a bare local variable is not reliably resolvable
    # here; the wrapper gives each generated function a real ``payload``
    # parameter annotated with its own schema.
    def _create(
        pet_id: PetPath,
        db: DbSession,
        current_user: CurrentUser,
        payload: create_schema,  # type: ignore[valid-type]
    ) -> Any:
        pet_service.get_pet_or_404(db, pet_id=pet_id, user_id=current_user.id)
        record = svc.create_child(
            db,
            model=model,
            pet_id=pet_id,
            user_id=current_user.id,
            data=payload.model_dump(),
        )
        return read_schema.model_validate(record)

    def _list(
        pet_id: PetPath,
        db: DbSession,
        current_user: CurrentUser,
        limit: ListQuery = 50,
        offset: OffsetQuery = 0,
        verified_only: VerifiedQuery = False,
    ) -> PaginatedRecords:
        pet_service.get_pet_or_404(db, pet_id=pet_id, user_id=current_user.id)
        items, total = svc.list_records(
            db,
            model=model,
            pet_id=pet_id,
            limit=limit,
            offset=offset,
            verified_only=verified_only,
        )
        return _paginated([read_schema.model_validate(i) for i in items], total, limit, offset)

    def _get(
        pet_id: PetPath, record_id: IdPath, db: DbSession, current_user: CurrentUser
    ) -> Any:
        pet_service.get_pet_or_404(db, pet_id=pet_id, user_id=current_user.id)
        return read_schema.model_validate(
            svc.get_record_or_404(
                db, model=model, record_id=record_id, pet_id=pet_id
            )
        )

    def _update(
        pet_id: PetPath,
        record_id: IdPath,
        payload: update_schema,  # type: ignore[valid-type]
        db: DbSession,
        current_user: CurrentUser,
    ) -> Any:
        return read_schema.model_validate(
            svc.update_record(
                db,
                model=model,
                record_id=record_id,
                pet_id=pet_id,
                user_id=current_user.id,
                data=payload.model_dump(exclude_unset=True),
            )
        )

    def _delete(
        pet_id: PetPath, record_id: IdPath, db: DbSession, current_user: CurrentUser
    ) -> dict:
        return svc.delete_record(
            db, model=model, record_id=record_id, pet_id=pet_id, user_id=current_user.id
        )

    router.add_api_route(
        f"/{path}",
        _create,
        methods=["POST"],
        status_code=status.HTTP_201_CREATED,
        response_model=read_schema,
        tags=[tag],
        name=f"create_{singular}",
        summary=f"Add a {singular.replace('_', ' ')} to this pet",
    )
    router.add_api_route(
        f"/{path}",
        _list,
        methods=["GET"],
        response_model=PaginatedRecords,
        tags=[tag],
        name=f"list_{path.replace('-', '_')}",
        summary=f"List {path.replace('-', ' ')} for this pet",
    )
    router.add_api_route(
        f"/{path}/{{record_id}}",
        _get,
        methods=["GET"],
        response_model=read_schema,
        tags=[tag],
        name=f"get_{singular}",
    )
    router.add_api_route(
        f"/{path}/{{record_id}}",
        _update,
        methods=["PATCH"],
        response_model=read_schema,
        tags=[tag],
        name=f"update_{singular}",
    )
    router.add_api_route(
        f"/{path}/{{record_id}}",
        _delete,
        methods=["DELETE"],
        tags=[tag],
        name=f"delete_{singular}",
    )


_CHILD_SPECS = (
    _ChildSpec(
        path="symptoms",
        model=SymptomRecord,
        create_schema=SymptomCreate,
        update_schema=SymptomUpdate,
        read_schema=SymptomRead,
        tag="symptoms",
    ),
    _ChildSpec(
        path="diagnoses",
        model=DiagnosisRecord,
        create_schema=DiagnosisCreate,
        update_schema=DiagnosisUpdate,
        read_schema=DiagnosisRead,
        tag="diagnoses",
    ),
    _ChildSpec(
        path="medications",
        model=MedicationRecord,
        create_schema=MedicationCreate,
        update_schema=MedicationUpdate,
        read_schema=MedicationRead,
        tag="medications",
    ),
    _ChildSpec(
        path="vaccinations",
        model=VaccinationRecord,
        create_schema=VaccinationCreate,
        update_schema=VaccinationUpdate,
        read_schema=VaccinationRead,
        tag="vaccinations",
    ),
    _ChildSpec(
        path="lab-reports",
        model=LabReport,
        create_schema=LabReportCreate,
        update_schema=LabReportUpdate,
        read_schema=LabReportRead,
        tag="lab reports",
    ),
)

for _spec in _CHILD_SPECS:
    _register_child_routes(_spec)
