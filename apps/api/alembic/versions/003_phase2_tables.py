"""phase 2 tables: visitor_sessions, conversations, conversation_turns, leads + RLS

Revision ID: 003
Revises: 002
Create Date: 2026-05-18

BIBLE refs: §6.1, §6.4, §7.1, §7.3, §7.4
ADR refs: ADR-003 (tenant isolation FORCE RLS)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Riferimenti ai tipi enum — solo nome, create_type=False garantisce zero emissione CREATE TYPE
_CONV_STATUS = PGEnum(name="conversation_status", create_type=False)
_CONV_CHANNEL = PGEnum(name="conversation_channel", create_type=False)
_TURN_ROLE = PGEnum(name="turn_role", create_type=False)
_LEAD_BUCKET = PGEnum(name="lead_bucket", create_type=False)


def upgrade() -> None:
    # ── enum types (raw SQL — idempotente) ────────────────────────────────────
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_type WHERE typname = 'conversation_status') THEN
                CREATE TYPE conversation_status AS ENUM ('active', 'completed', 'abandoned');
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_type WHERE typname = 'conversation_channel') THEN
                CREATE TYPE conversation_channel AS ENUM ('web', 'voice');
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_type WHERE typname = 'turn_role') THEN
                CREATE TYPE turn_role AS ENUM ('user', 'assistant', 'tool', 'system');
            END IF;
        END $$
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            IF NOT EXISTS (SELECT FROM pg_type WHERE typname = 'lead_bucket') THEN
                CREATE TYPE lead_bucket AS ENUM ('cold', 'warm', 'hot');
            END IF;
        END $$
        """
    )

    # ── visitor_sessions (BIBLE §7.1 — VisitorPrior) ─────────────────────────
    op.create_table(
        "visitor_sessions",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("visitor_hash", sa.String(64), nullable=False),
        sa.Column(
            "inferred_personas",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "signals",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("confidence", sa.Float, nullable=False, server_default="0.0"),
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
    op.create_index("ix_visitor_sessions_tenant_id", "visitor_sessions", ["tenant_id"])
    op.create_index(
        "ix_visitor_sessions_tenant_hash",
        "visitor_sessions",
        ["tenant_id", "visitor_hash"],
    )

    op.execute("ALTER TABLE visitor_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE visitor_sessions FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON visitor_sessions
            FOR ALL
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )

    # ── conversations (BIBLE §6.1, §6.4 — idempotency_key) ───────────────────
    op.create_table(
        "conversations",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("visitor_session_id", PG_UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("status", _CONV_STATUS, nullable=False, server_default="active"),
        sa.Column("channel", _CONV_CHANNEL, nullable=False, server_default="web"),
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
        sa.ForeignKeyConstraint(
            ["visitor_session_id"], ["visitor_sessions.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_conversations_tenant_id", "conversations", ["tenant_id"])
    # partial unique: idempotency enforced only when key is non-NULL
    op.execute(
        """
        CREATE UNIQUE INDEX ix_conversations_tenant_idempotency
        ON conversations (tenant_id, idempotency_key)
        WHERE idempotency_key IS NOT NULL
        """
    )

    op.execute("ALTER TABLE conversations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE conversations FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON conversations
            FOR ALL
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )

    # ── conversation_turns (BIBLE §7.4) ───────────────────────────────────────
    op.create_table(
        "conversation_turns",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", PG_UUID(as_uuid=True), nullable=False),
        # tenant_id denormalizzato per RLS — no FK, enforced via conversation chain
        sa.Column("tenant_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("turn_index", sa.Integer, nullable=False),
        sa.Column("role", _TURN_ROLE, nullable=False),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("user_intent", sa.String(32), nullable=True),
        sa.Column("quality_score", sa.SmallInteger, nullable=True),
        sa.Column("tool_calls_json", JSONB, nullable=True),
        sa.Column("tool_call_success_overall", sa.Boolean, nullable=True),
        sa.Column("rendering_directives_emitted", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"], ["conversations.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "conversation_id", "turn_index", name="uq_conversation_turns_idx"
        ),
    )
    op.create_index(
        "ix_conversation_turns_conversation_id", "conversation_turns", ["conversation_id"]
    )
    op.create_index(
        "ix_conversation_turns_tenant_id", "conversation_turns", ["tenant_id"]
    )

    op.execute("ALTER TABLE conversation_turns ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE conversation_turns FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON conversation_turns
            FOR ALL
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )

    # ── leads (BIBLE §7.3 — LeadScore) ───────────────────────────────────────
    op.create_table(
        "leads",
        sa.Column("id", PG_UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("visitor_session_id", PG_UUID(as_uuid=True), nullable=False),
        sa.Column("score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("bucket", _LEAD_BUCKET, nullable=False, server_default="cold"),
        sa.Column(
            "signals",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("handoff_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handoff_briefing_uri", sa.String(500), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["visitor_session_id"], ["visitor_sessions.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("visitor_session_id", name="uq_leads_visitor_session"),
    )
    op.create_index("ix_leads_tenant_id", "leads", ["tenant_id"])

    op.execute("ALTER TABLE leads ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE leads FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON leads
            FOR ALL
            USING (tenant_id = current_setting('app.tenant_id', true)::uuid)
        """
    )


def downgrade() -> None:
    # drop in reverse FK order: leads, conversation_turns, conversations, visitor_sessions

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON leads")
    op.execute("ALTER TABLE leads DISABLE ROW LEVEL SECURITY")
    op.drop_table("leads")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON conversation_turns")
    op.execute("ALTER TABLE conversation_turns DISABLE ROW LEVEL SECURITY")
    op.drop_table("conversation_turns")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON conversations")
    op.execute("ALTER TABLE conversations DISABLE ROW LEVEL SECURITY")
    op.drop_table("conversations")

    op.execute("DROP POLICY IF EXISTS tenant_isolation ON visitor_sessions")
    op.execute("ALTER TABLE visitor_sessions DISABLE ROW LEVEL SECURITY")
    op.drop_table("visitor_sessions")

    # drop enum types dopo aver rimosso tutte le tabelle che le usano
    op.execute("DROP TYPE IF EXISTS lead_bucket")
    op.execute("DROP TYPE IF EXISTS turn_role")
    op.execute("DROP TYPE IF EXISTS conversation_channel")
    op.execute("DROP TYPE IF EXISTS conversation_status")
