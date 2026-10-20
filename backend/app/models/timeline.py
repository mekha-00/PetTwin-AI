"""Health timeline event — an append-only chronological log for one pet.

This is the query surface the future Digital Twin service will read to know
*what happened and when*. It records verified clinical events in time order.

It is **not** the Digital Twin and is **not** a health state. It stores no
interpretation, no risk score, no summary and no current status. A twin is
assembled on demand from these events plus the detailed records they point at;
persisting that assembly as columns here would create a second source of truth
that drifts from the clinical records.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import (
    Base,
    TimelineEventType,
    TimestampMixin,
    enum_column,
)


class HealthTimelineEvent(Base, TimestampMixin):
    __tablename__ = "health_timeline_events"
    __table_args__ = (
        Index("ix_health_timeline_events_pet_occurred", "pet_id", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    pet_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type: Mapped[TimelineEventType] = enum_column(
        TimelineEventType, "timeline_event_type"
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[int | None] = mapped_column(nullable=True)

    source_table: Mapped[str | None] = mapped_column(String(64))
    source_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True))

    pet: Mapped["Pet"] = relationship(  # noqa: F821
        back_populates="timeline_events"
    )

    def __repr__(self) -> str:
        return f"<HealthTimelineEvent {self.event_type} pet={self.pet_id}>"
