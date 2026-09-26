"""add recurring routine calendar events

Revision ID: f4c8b7d91a2e
Revises: de7735abeee3
Create Date: 2026-09-21 21:00:00
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f4c8b7d91a2e"
down_revision: Union[str, Sequence[str], None] = "de7735abeee3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # Existing one-time calendar events remain valid,
    # but task_id is no longer mandatory because a
    # recurring event can belong to a Routine instead.
    op.alter_column(
        "calendar_events",
        "task_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    op.add_column(
        "calendar_events",
        sa.Column(
            "routine_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.add_column(
        "calendar_events",
        sa.Column(
            "recurrence_rule",
            sa.String(length=255),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_calendar_events_routine_id",
        "calendar_events",
        "routines",
        ["routine_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_index(
        "ix_calendar_events_routine_id",
        "calendar_events",
        ["routine_id"],
    )


def downgrade() -> None:

    op.drop_index(
        "ix_calendar_events_routine_id",
        table_name="calendar_events",
    )

    op.drop_constraint(
        "fk_calendar_events_routine_id",
        "calendar_events",
        type_="foreignkey",
    )

    op.drop_column(
        "calendar_events",
        "recurrence_rule",
    )

    op.drop_column(
        "calendar_events",
        "routine_id",
    )

    op.alter_column(
        "calendar_events",
        "task_id",
        existing_type=sa.Integer(),
        nullable=False,
    )