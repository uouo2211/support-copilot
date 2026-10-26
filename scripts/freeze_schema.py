"""Generate the immutable initial migration once; do not rerun for later schema changes."""
from pathlib import Path

from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from app.db import Base
import app.models  # noqa: F401

dialect = postgresql.dialect()
parts = [str(CreateTable(t).compile(dialect=dialect)) + ";" for t in Base.metadata.sorted_tables]
parts += [str(CreateIndex(i).compile(dialect=dialect)) + ";" for t in Base.metadata.sorted_tables for i in t.indexes]
Path("migrations/schema_v1.sql").write_text("\n".join(parts))
