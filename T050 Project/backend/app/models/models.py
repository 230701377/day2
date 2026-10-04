import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, Boolean, ForeignKey,
    UniqueConstraint, Index, Enum as SAEnum, Float, JSON, BigInteger, LargeBinary
)
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
import enum

from app.db.session import Base


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


class ContractStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    ACTIVE = "active"
    EXPIRED = "expired"
    RENEWED = "renewed"
    TERMINATED = "terminated"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class ContractType(str, enum.Enum):
    NDA = "nda"
    MSA = "msa"
    SOW = "sow"
    VENDOR = "vendor"
    EMPLOYMENT = "employment"
    LEASE = "lease"
    LICENSE = "license"
    PARTNERSHIP = "partnership"
    SERVICE = "service"
    OTHER = "other"


class ApprovalDecision(str, enum.Enum):
    NOT_STARTED = "not_started"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CHANGES_REQUESTED = "changes_requested"
    DELEGATED = "delegated"
    SKIPPED = "skipped"


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    email = Column(String(255), unique=True, nullable=False, index=True)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    department = Column(String(120))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class Contract(Base):
    __tablename__ = "contracts"
    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    title = Column(String(500), nullable=False, index=True)
    contract_number = Column(String(120), unique=True, nullable=False, index=True)
    contract_type = Column(String(50), nullable=False)
    status = Column(String(50), default=ContractStatus.DRAFT.value, nullable=False, index=True)
    counterparty = Column(String(255), index=True)
    owner_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False, index=True)
    department = Column(String(120))
    value_amount = Column(Float)
    value_currency = Column(String(10), default="INR")
    effective_date = Column(DateTime(timezone=True))
    expiration_date = Column(DateTime(timezone=True), index=True)
    auto_renew = Column(Boolean, default=False)
    renewal_notice_days = Column(Integer, default=60)
    tags = Column(JSONB, default=list)
    description = Column(Text)
    parent_contract_id = Column(UUID(as_uuid=False), ForeignKey("contracts.id"), nullable=True)
    template_id = Column(UUID(as_uuid=False), ForeignKey("contract_templates.id"), nullable=True)
    risk_score = Column(Float, default=0.0)
    risk_level = Column(String(20), default=RiskLevel.LOW.value)
    is_amendment = Column(Boolean, default=False)
    processing_status = Column(String(50), default="COMPLETED", nullable=False, index=True)
    processing_step = Column(String(100), default="Completed")
    processing_progress = Column(Integer, default=100)
    processing_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)

    versions = relationship("ContractVersion", back_populates="contract",
                            cascade="all,delete-orphan", order_by="ContractVersion.version_number.desc()")
    clauses = relationship("Clause", back_populates="contract",
                           cascade="all,delete-orphan")
    risks = relationship("RiskFinding", back_populates="contract",
                         cascade="all,delete-orphan")
    obligations = relationship("Obligation", back_populates="contract",
                               cascade="all,delete-orphan")
    approvals = relationship("Approval", back_populates="contract",
                             cascade="all,delete-orphan")
    metadata_records = relationship("ContractMetadata", back_populates="contract",
                                    cascade="all,delete-orphan", uselist=False)


class ContractVersion(Base):
    __tablename__ = "contract_versions"
    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    contract_id = Column(UUID(as_uuid=False), ForeignKey("contracts.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    version_label = Column(String(80), default="")
    storage_key = Column(String(500), nullable=False)
    original_filename = Column(String(500))
    mime_type = Column(String(120))
    size_bytes = Column(BigInteger)
    sha256_hash = Column(String(64), nullable=False, index=True)
    page_count = Column(Integer)
    content_text = Column(Text)
    content_tsv = Column(TSVECTOR)
    embedding = Column(Vector(384))
    change_summary = Column(Text)
    risk_delta = Column(Float, default=0.0)
    created_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False, index=True)

    contract = relationship("Contract", back_populates="versions")
    creator = relationship("User")

    __table_args__ = (
        UniqueConstraint("contract_id", "version_number", name="uq_contract_version"),
        Index("ix_contract_versions_contract_created", "contract_id", "created_at"),
    )


class ContractMetadata(Base):
    __tablename__ = "contract_metadata"
    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    contract_id = Column(UUID(as_uuid=False), ForeignKey("contracts.id", ondelete="CASCADE"),
                         nullable=False, unique=True)
    effective_date = Column(DateTime(timezone=True))
    expiration_date = Column(DateTime(timezone=True))
    governing_law = Column(String(255))
    payment_terms = Column(String(255))
    termination_notice_days = Column(Integer)
    liability_cap = Column(String(255))
    signatories = Column(JSONB, default=list)
    extracted_at = Column(DateTime(timezone=True), default=_now)
    extractor_version = Column(String(50), default="heuristic-1.0")

    contract = relationship("Contract", back_populates="metadata_records")


class Clause(Base):
    __tablename__ = "clauses"
    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    contract_id = Column(UUID(as_uuid=False), ForeignKey("contracts.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    version_id = Column(UUID(as_uuid=False), ForeignKey("contract_versions.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    clause_number = Column(String(50))
    heading = Column(String(500))
    body = Column(Text, nullable=False)
    category = Column(String(80), index=True)
    confidence = Column(Float, default=0.0)
    page_number = Column(Integer)
    start_offset = Column(Integer)
    end_offset = Column(Integer)
    risk_level = Column(String(20), default=RiskLevel.LOW.value)
    embedding = Column(Vector(384))
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    contract = relationship("Contract", back_populates="clauses")


class RiskFinding(Base):
    __tablename__ = "risk_findings"
    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    contract_id = Column(UUID(as_uuid=False), ForeignKey("contracts.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    version_id = Column(UUID(as_uuid=False), ForeignKey("contract_versions.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    clause_id = Column(UUID(as_uuid=False), ForeignKey("clauses.id", ondelete="SET NULL"),
                       nullable=True)
    finding_type = Column(String(80), nullable=False, index=True)
    severity = Column(String(20), nullable=False, index=True)
    score_rule = Column(Float, default=0.0)
    score_nlp = Column(Float, default=0.0)
    score_llm = Column(Float, default=0.0)
    score_total = Column(Float, default=0.0)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    evidence = Column(Text)
    recommendation = Column(Text)
    source_excerpt = Column(Text)
    source_page = Column(Integer)
    detector_version = Column(String(50), default="hybrid-1.0")
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    contract = relationship("Contract", back_populates="risks")


class ApprovalWorkflow(Base):
    __tablename__ = "approval_workflows"
    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False, unique=True)
    description = Column(Text)
    definition = Column(JSONB, nullable=False)
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_now, onupdate=_now, nullable=False)


class Approval(Base):
    __tablename__ = "approvals"
    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    contract_id = Column(UUID(as_uuid=False), ForeignKey("contracts.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    workflow_id = Column(UUID(as_uuid=False), ForeignKey("approval_workflows.id"),
                         nullable=False)
    step_index = Column(Integer, nullable=False)
    step_name = Column(String(200), nullable=False)
    required_role = Column(String(50), nullable=False)
    assignee_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    decision = Column(String(40), default=ApprovalDecision.PENDING.value, nullable=False)
    comments = Column(Text)
    sla_hours = Column(Integer, default=48)
    due_at = Column(DateTime(timezone=True), nullable=False, index=True)
    decided_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    contract = relationship("Contract", back_populates="approvals")
    assignee = relationship("User")
    workflow = relationship("ApprovalWorkflow")


class Obligation(Base):
    __tablename__ = "obligations"
    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    contract_id = Column(UUID(as_uuid=False), ForeignKey("contracts.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    owner_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True, index=True)
    responsible_role = Column(String(50))
    due_date = Column(DateTime(timezone=True), index=True)
    cadence = Column(String(50))
    status = Column(String(40), default="open", index=True)
    priority = Column(String(20), default="medium")
    recurrence_count = Column(Integer, default=0)
    last_completed_at = Column(DateTime(timezone=True))
    source_clause_id = Column(UUID(as_uuid=False), ForeignKey("clauses.id", ondelete="SET NULL"),
                              nullable=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    contract = relationship("Contract", back_populates="obligations")
    owner = relationship("User")


class ContractTemplate(Base):
    __tablename__ = "contract_templates"
    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    name = Column(String(200), nullable=False, unique=True)
    contract_type = Column(String(50), nullable=False)
    body = Column(Text, nullable=False)
    required_clauses = Column(JSONB, default=list)
    recommended_clauses = Column(JSONB, default=list)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    sequence = Column(BigInteger, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), default=_now, nullable=False)
    actor_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True, index=True)
    actor_email = Column(String(255))
    action = Column(String(80), nullable=False, index=True)
    resource_type = Column(String(80), index=True)
    resource_id = Column(String(80), index=True)
    ip_address = Column(String(64))
    user_agent = Column(String(500))
    payload = Column(JSONB, default=dict)
    previous_hash = Column(String(64))
    entry_hash = Column(String(64), nullable=False, index=True)


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, index=True)
    title = Column(String(500), nullable=False)
    body = Column(Text)
    level = Column(String(20), default="info")
    link = Column(String(500))
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class QASession(Base):
    __tablename__ = "qa_sessions"
    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    user_id = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text)
    sources = Column(JSONB, default=list)
    contract_ids = Column(JSONB, default=list)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)


class ContractStatusHistory(Base):
    __tablename__ = "contract_status_history"
    id = Column(UUID(as_uuid=False), primary_key=True, default=_uuid)
    contract_id = Column(UUID(as_uuid=False), ForeignKey("contracts.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=False, index=True)
    changed_by = Column(UUID(as_uuid=False), ForeignKey("users.id"), nullable=True)
    reason = Column(Text, nullable=True)
    changed_at = Column(DateTime(timezone=True), default=_now, nullable=False, index=True)

    contract = relationship("Contract")
    user = relationship("User")
