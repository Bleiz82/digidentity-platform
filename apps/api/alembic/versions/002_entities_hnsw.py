"""entities table with halfvec(3072) HNSW indexes + RLS

Revision ID: 002
Revises: 001
Create Date: 2026-05-14
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import HALFVEC
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("pack_id", sa.String(128), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("payload", JSONB, nullable=False, server_default="{}"),
        sa.Column("content_emb", HALFVEC(3072), nullable=True),
        sa.Column("lifestyle_emb", HALFVEC(3072), nullable=True),
        sa.Column("features_emb", HALFVEC(3072), nullable=True),
        sa.Column(
            "embedding_version",
            sa.String(64),
            nullable=False,
            server_default="text-embedding-3-large-halfvec-v1",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_entities_tenant_id", "entities", ["tenant_id"])
    op.create_index("ix_entities_pack_id", "entities", ["pack_id"])

    # HNSW indexes — shared, filtro tenant via RLS
    op.execute(
        """
        CREATE INDEX ix_entities_content_emb ON entities
        USING hnsw (content_emb halfvec_cosine_ops)
        WITH (m=16, ef_construction=128)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_entities_lifestyle_emb ON entities
        USING hnsw (lifestyle_emb halfvec_cosine_ops)
        WITH (m=16, ef_construction=128)
        """
    )
    op.execute(
        """
        CREATE INDEX ix_entities_features_emb ON entities
        USING hnsw (features_emb halfvec_cosine_ops)
        WITH (m=16, ef_construction=128)
        """
    )

    # RLS
    op.execute("ALTER TABLE entities ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE entities FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON entities
            FOR ALL
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON entities")
    op.execute("ALTER TABLE entities DISABLE ROW LEVEL SECURITY")
    op.drop_table("entities")
