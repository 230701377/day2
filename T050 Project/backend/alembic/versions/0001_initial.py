"""Initial schema with pgvector support."""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    PK = "postgresql.UUID(as_uuid=False)"
    FK = lambda target, **kw: postgresql.UUID(as_uuid=False)  # placeholder for column type

    def col(name, type_, **kw):
        return sa.Column(name, type_, **kw)

    def uuid_pk(name):
        return sa.Column(name, postgresql.UUID(as_uuid=False), primary_key=True)

    def uuid_fk(name, target, nullable=True, **fk_kw):
        col = sa.Column(name, postgresql.UUID(as_uuid=False),
                        sa.ForeignKey(target, **fk_kw),
                        nullable=nullable)
        return col

    op.create_table(
        "users",
        uuid_pk("id"),
        col("email", sa.String(255), nullable=False, unique=True),
        col("full_name", sa.String(255), nullable=False),
        col("hashed_password", sa.String(255), nullable=False),
        col("role", sa.String(50), nullable=False),
        col("department", sa.String(120)),
        col("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        col("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        col("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "contract_templates",
        uuid_pk("id"),
        col("name", sa.String(200), nullable=False, unique=True),
        col("contract_type", sa.String(50), nullable=False),
        col("body", sa.Text(), nullable=False),
        col("required_clauses", postgresql.JSONB, server_default="[]"),
        col("recommended_clauses", postgresql.JSONB, server_default="[]"),
        col("description", sa.Text()),
        col("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "contracts",
        uuid_pk("id"),
        col("title", sa.String(500), nullable=False),
        col("contract_number", sa.String(120), nullable=False, unique=True),
        col("contract_type", sa.String(50), nullable=False),
        col("status", sa.String(50), nullable=False, server_default="draft"),
        col("counterparty", sa.String(255)),
        uuid_fk("owner_id", "users.id", nullable=False),
        col("department", sa.String(120)),
        col("value_amount", sa.Float()),
        col("value_currency", sa.String(10), server_default="USD"),
        col("effective_date", sa.DateTime(timezone=True)),
        col("expiration_date", sa.DateTime(timezone=True)),
        col("auto_renew", sa.Boolean(), server_default=sa.text("false")),
        col("renewal_notice_days", sa.Integer(), server_default="60"),
        col("tags", postgresql.JSONB, server_default="[]"),
        col("description", sa.Text()),
        uuid_fk("parent_contract_id", "contracts.id"),
        uuid_fk("template_id", "contract_templates.id"),
        col("risk_score", sa.Float(), server_default="0"),
        col("risk_level", sa.String(20), server_default="low"),
        col("is_amendment", sa.Boolean(), server_default=sa.text("false")),
        col("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        col("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_contracts_title", "contracts", ["title"])
    op.create_index("ix_contracts_status", "contracts", ["status"])
    op.create_index("ix_contracts_counterparty", "contracts", ["counterparty"])
    op.create_index("ix_contracts_owner", "contracts", ["owner_id"])
    op.create_index("ix_contracts_expiration", "contracts", ["expiration_date"])

    op.create_table(
        "contract_versions",
        uuid_pk("id"),
        uuid_fk("contract_id", "contracts.id", nullable=False, ondelete="CASCADE"),
        col("version_number", sa.Integer(), nullable=False),
        col("version_label", sa.String(80), server_default=""),
        col("storage_key", sa.String(500), nullable=False),
        col("original_filename", sa.String(500)),
        col("mime_type", sa.String(120)),
        col("size_bytes", sa.BigInteger()),
        col("sha256_hash", sa.String(64), nullable=False),
        col("page_count", sa.Integer()),
        col("content_text", sa.Text()),
        col("content_tsv", postgresql.TSVECTOR),
        col("embedding", Vector(384)),
        col("change_summary", sa.Text()),
        col("risk_delta", sa.Float(), server_default="0"),
        uuid_fk("created_by", "users.id", nullable=False),
        col("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("contract_id", "version_number", name="uq_contract_version"),
    )
    op.create_index("ix_contract_versions_contract", "contract_versions", ["contract_id"])
    op.create_index("ix_contract_versions_sha", "contract_versions", ["sha256_hash"])
    op.create_index("ix_contract_versions_created", "contract_versions", ["created_at"])

    op.create_table(
        "contract_metadata",
        uuid_pk("id"),
        uuid_fk("contract_id", "contracts.id", nullable=False, ondelete="CASCADE"),
        sa.UniqueConstraint("contract_id", name="uq_contract_metadata_contract"),
        col("effective_date", sa.DateTime(timezone=True)),
        col("expiration_date", sa.DateTime(timezone=True)),
        col("governing_law", sa.String(255)),
        col("payment_terms", sa.String(255)),
        col("termination_notice_days", sa.Integer()),
        col("liability_cap", sa.String(255)),
        col("signatories", postgresql.JSONB, server_default="[]"),
        col("extracted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        col("extractor_version", sa.String(50), server_default="heuristic-1.0"),
    )

    op.create_table(
        "clauses",
        uuid_pk("id"),
        uuid_fk("contract_id", "contracts.id", nullable=False, ondelete="CASCADE"),
        uuid_fk("version_id", "contract_versions.id", nullable=False, ondelete="CASCADE"),
        col("clause_number", sa.String(50)),
        col("heading", sa.String(500)),
        col("body", sa.Text(), nullable=False),
        col("category", sa.String(80)),
        col("confidence", sa.Float(), server_default="0"),
        col("page_number", sa.Integer()),
        col("start_offset", sa.Integer()),
        col("end_offset", sa.Integer()),
        col("risk_level", sa.String(20), server_default="low"),
        col("embedding", Vector(384)),
        col("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_clauses_contract", "clauses", ["contract_id"])
    op.create_index("ix_clauses_version", "clauses", ["version_id"])
    op.create_index("ix_clauses_category", "clauses", ["category"])

    op.create_table(
        "risk_findings",
        uuid_pk("id"),
        uuid_fk("contract_id", "contracts.id", nullable=False, ondelete="CASCADE"),
        uuid_fk("version_id", "contract_versions.id", nullable=False, ondelete="CASCADE"),
        uuid_fk("clause_id", "clauses.id", ondelete="SET NULL"),
        col("finding_type", sa.String(80), nullable=False),
        col("severity", sa.String(20), nullable=False),
        col("score_rule", sa.Float(), server_default="0"),
        col("score_nlp", sa.Float(), server_default="0"),
        col("score_llm", sa.Float(), server_default="0"),
        col("score_total", sa.Float(), server_default="0"),
        col("title", sa.String(500), nullable=False),
        col("description", sa.Text(), nullable=False),
        col("evidence", sa.Text()),
        col("recommendation", sa.Text()),
        col("source_excerpt", sa.Text()),
        col("source_page", sa.Integer()),
        col("detector_version", sa.String(50), server_default="hybrid-1.0"),
        col("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_risk_findings_contract", "risk_findings", ["contract_id"])
    op.create_index("ix_risk_findings_version", "risk_findings", ["version_id"])
    op.create_index("ix_risk_findings_type", "risk_findings", ["finding_type"])
    op.create_index("ix_risk_findings_severity", "risk_findings", ["severity"])

    op.create_table(
        "approval_workflows",
        uuid_pk("id"),
        col("name", sa.String(200), nullable=False, unique=True),
        col("description", sa.Text()),
        col("definition", postgresql.JSONB, nullable=False),
        col("is_default", sa.Boolean(), server_default=sa.text("false")),
        col("is_active", sa.Boolean(), server_default=sa.text("true")),
        col("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        col("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "approvals",
        uuid_pk("id"),
        uuid_fk("contract_id", "contracts.id", nullable=False, ondelete="CASCADE"),
        uuid_fk("workflow_id", "approval_workflows.id", nullable=False),
        col("step_index", sa.Integer(), nullable=False),
        col("step_name", sa.String(200), nullable=False),
        col("required_role", sa.String(50), nullable=False),
        uuid_fk("assignee_id", "users.id"),
        col("decision", sa.String(40), nullable=False, server_default="pending"),
        col("comments", sa.Text()),
        col("sla_hours", sa.Integer(), server_default="48"),
        col("due_at", sa.DateTime(timezone=True), nullable=False),
        col("decided_at", sa.DateTime(timezone=True)),
        col("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_approvals_contract", "approvals", ["contract_id"])
    op.create_index("ix_approvals_due", "approvals", ["due_at"])

    op.create_table(
        "obligations",
        uuid_pk("id"),
        uuid_fk("contract_id", "contracts.id", nullable=False, ondelete="CASCADE"),
        col("title", sa.String(500), nullable=False),
        col("description", sa.Text(), nullable=False),
        uuid_fk("owner_id", "users.id"),
        col("responsible_role", sa.String(50)),
        col("due_date", sa.DateTime(timezone=True)),
        col("cadence", sa.String(50)),
        col("status", sa.String(40), server_default="open"),
        col("priority", sa.String(20), server_default="medium"),
        col("recurrence_count", sa.Integer(), server_default="0"),
        col("last_completed_at", sa.DateTime(timezone=True)),
        uuid_fk("source_clause_id", "clauses.id", ondelete="SET NULL"),
        col("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_obligations_contract", "obligations", ["contract_id"])
    op.create_index("ix_obligations_owner", "obligations", ["owner_id"])
    op.create_index("ix_obligations_due", "obligations", ["due_date"])
    op.create_index("ix_obligations_status", "obligations", ["status"])

    op.create_table(
        "audit_log",
        col("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        col("sequence", sa.BigInteger(), nullable=False),
        col("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        uuid_fk("actor_id", "users.id"),
        col("actor_email", sa.String(255)),
        col("action", sa.String(80), nullable=False),
        col("resource_type", sa.String(80)),
        col("resource_id", sa.String(80)),
        col("ip_address", sa.String(64)),
        col("user_agent", sa.String(500)),
        col("payload", postgresql.JSONB, server_default="{}"),
        col("previous_hash", sa.String(64)),
        col("entry_hash", sa.String(64), nullable=False),
    )
    op.create_index("ix_audit_sequence", "audit_log", ["sequence"], unique=True)
    op.create_index("ix_audit_action", "audit_log", ["action"])
    op.create_index("ix_audit_resource_type", "audit_log", ["resource_type"])
    op.create_index("ix_audit_resource_id", "audit_log", ["resource_id"])
    op.create_index("ix_audit_actor", "audit_log", ["actor_id"])
    op.create_index("ix_audit_hash", "audit_log", ["entry_hash"], unique=True)

    op.create_table(
        "notifications",
        uuid_pk("id"),
        uuid_fk("user_id", "users.id", nullable=False, ondelete="CASCADE"),
        col("title", sa.String(500), nullable=False),
        col("body", sa.Text()),
        col("level", sa.String(20), server_default="info"),
        col("link", sa.String(500)),
        col("is_read", sa.Boolean(), server_default=sa.text("false")),
        col("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notifications_user", "notifications", ["user_id"])

    op.create_table(
        "qa_sessions",
        uuid_pk("id"),
        uuid_fk("user_id", "users.id", nullable=False),
        col("question", sa.Text(), nullable=False),
        col("answer", sa.Text()),
        col("sources", postgresql.JSONB, server_default="[]"),
        col("contract_ids", postgresql.JSONB, server_default="[]"),
        col("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("qa_sessions")
    op.drop_table("notifications")
    op.drop_table("audit_log")
    op.drop_table("obligations")
    op.drop_table("approvals")
    op.drop_table("approval_workflows")
    op.drop_table("risk_findings")
    op.drop_table("clauses")
    op.drop_table("contract_metadata")
    op.drop_table("contract_versions")
    op.drop_table("contracts")
    op.drop_table("contract_templates")
    op.drop_table("users")
