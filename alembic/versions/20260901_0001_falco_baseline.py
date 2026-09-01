"""Falco 1.0 canonical paper schema baseline.

Revision ID: 20260901_0001
Revises:
Create Date: 2026-09-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260901_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EXPECTED_COLUMNS = {
    "id",
    "arxiv_id",
    "title",
    "authors",
    "abstract",
    "categories",
    "published_date",
    "pdf_url",
    "raw_text",
    "sections",
    "references",
    "parser_used",
    "parser_metadata",
    "pdf_processed",
    "pdf_processing_date",
    "created_at",
    "updated_at",
}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "papers" in inspector.get_table_names():
        existing_columns = {column["name"] for column in inspector.get_columns("papers")}
        missing = EXPECTED_COLUMNS - existing_columns
        if missing:
            raise RuntimeError(
                "Existing papers table is incompatible with the Falco 1.0 baseline; missing column(s): "
                + ", ".join(sorted(missing))
            )
        return

    op.create_table(
        "papers",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("arxiv_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=False),
        sa.Column("abstract", sa.Text(), nullable=False),
        sa.Column("categories", sa.JSON(), nullable=False),
        sa.Column("published_date", sa.DateTime(), nullable=False),
        sa.Column("pdf_url", sa.String(), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("sections", sa.JSON(), nullable=True),
        sa.Column("references", sa.JSON(), nullable=True),
        sa.Column("parser_used", sa.String(), nullable=True),
        sa.Column("parser_metadata", sa.JSON(), nullable=True),
        sa.Column("pdf_processed", sa.Boolean(), nullable=False),
        sa.Column("pdf_processing_date", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("arxiv_id"),
    )
    op.create_index("ix_papers_arxiv_id", "papers", ["arxiv_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_papers_arxiv_id", table_name="papers")
    op.drop_table("papers")
