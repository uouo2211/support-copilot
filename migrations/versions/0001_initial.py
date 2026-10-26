"""Initial schema, frozen SQL independent of future application models."""
from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.get_bind().exec_driver_sql((Path(__file__).parents[1] / "schema_v1.sql").read_text())


def downgrade():
    raise RuntimeError("Destructive initial downgrade disabled; restore a database backup instead")
