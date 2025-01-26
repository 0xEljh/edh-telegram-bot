"""add_deletion_features

Revision ID: 382ba7a72c60
Revises: 
Create Date: 2025-01-26 07:17:27.802856

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision: str = "382ba7a72c60"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    inspector = inspect(op.get_bind())

    # Add deletion_reference column if it doesn't exist
    columns = [col["name"] for col in inspector.get_columns("games")]
    if "deletion_reference" not in columns:
        op.add_column(
            "games", sa.Column("deletion_reference", sa.String(), nullable=True)
        )

    # Create game_deletion_requests table only if it doesn't exist
    if not inspector.has_table("game_deletion_requests"):
        op.create_table(
            "game_deletion_requests",
            sa.Column("request_id", sa.Integer(), nullable=False),
            sa.Column("game_id", sa.Integer(), nullable=False),
            sa.Column("requester_id", sa.Integer(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.PrimaryKeyConstraint("request_id"),
            sa.ForeignKeyConstraint(["game_id"], ["games.game_id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["requester_id"], ["pods_players.pods_player_id"], ondelete="CASCADE"
            ),
        )

    # Create indexes conditionally
    if not inspector.has_index("games", "ix_games_pod_id"):
        op.create_index(op.f("ix_games_pod_id"), "games", ["pod_id"], unique=False)

    if not inspector.has_index("games", "ix_games_created_at"):
        op.create_index(
            op.f("ix_games_created_at"), "games", ["created_at"], unique=False
        )

    if not inspector.has_index("games", "ix_games_deletion_reference"):
        op.create_index(
            op.f("ix_games_deletion_reference"),
            "games",
            ["deletion_reference"],
            unique=True,
        )

    # Add unique constraint only if it doesn't exist
    with op.batch_alter_table("pods_players") as batch_op:
        constraints = [
            c["name"] for c in inspector.get_unique_constraints("pods_players")
        ]
        if "uq_pod_player" not in constraints:
            batch_op.create_unique_constraint(
                "uq_pod_player", ["pod_id", "telegram_id"]
            )


def downgrade():
    # Downgrade logic remains the same but safer
    op.drop_index(
        op.f("ix_games_deletion_reference"), table_name="games", if_exists=True
    )
    op.drop_index(op.f("ix_games_created_at"), table_name="games", if_exists=True)
    op.drop_index(op.f("ix_games_pod_id"), table_name="games", if_exists=True)

    with op.batch_alter_table("pods_players") as batch_op:
        batch_op.drop_constraint("uq_pod_player", type_="unique", if_exists=True)

    op.drop_table("game_deletion_requests", if_exists=True)
    op.drop_column("games", "deletion_reference", if_exists=True)
