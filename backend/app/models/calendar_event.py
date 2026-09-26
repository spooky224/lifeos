from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class CalendarEventStatus(str, Enum):
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CalendarEvent(Base):
    __tablename__ = "calendar_events"

    id: Mapped[int] = mapped_column(primary_key=True)

    # A calendar event can belong to either:
    # - a one-time Task
    # - a recurring Routine
    task_id: Mapped[int | None] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=True,
    )

    routine_id: Mapped[int | None] = mapped_column(
        ForeignKey("routines.id", ondelete="SET NULL"),
        nullable=True,
    )

    google_event_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )

    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    # Example:
    # RRULE:FREQ=DAILY
    # RRULE:FREQ=WEEKLY;BYDAY=MO,WE,FR
    # RRULE:FREQ=MONTHLY;BYMONTHDAY=1
    recurrence_rule: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    status: Mapped[CalendarEventStatus] = mapped_column(
        String(20),
        nullable=False,
        default=CalendarEventStatus.SCHEDULED,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    task: Mapped["Task | None"] = relationship(
        "Task",
        back_populates="calendar_events",
    )

    __table_args__ = (
        Index("ix_calendar_events_task_id", "task_id"),
        Index("ix_calendar_events_routine_id", "routine_id"),
        Index("ix_calendar_events_start_time", "start_time"),
        Index("ix_calendar_events_status", "status"),
    )


from app.models.task import Task