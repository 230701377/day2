from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- User ----------
class UserCreate(BaseModel):
    email: EmailStr
    full_name: str
    password: str = Field(min_length=8)
    role: str
    department: Optional[str] = None


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None


class UserOut(ORMModel):
    id: str
    email: EmailStr
    full_name: str
    role: str
    department: Optional[str] = None
    is_active: bool
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------- Contract ----------
class ContractCreate(BaseModel):
    title: str
    contract_type: str
    counterparty: Optional[str] = None
    department: Optional[str] = None
    value_amount: Optional[float] = None
    value_currency: Optional[str] = "USD"
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    auto_renew: Optional[bool] = False
    renewal_notice_days: Optional[int] = 60
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    template_id: Optional[str] = None
    parent_contract_id: Optional[str] = None


class ContractUpdate(BaseModel):
    title: Optional[str] = None
    counterparty: Optional[str] = None
    department: Optional[str] = None
    value_amount: Optional[float] = None
    value_currency: Optional[str] = None
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    auto_renew: Optional[bool] = None
    renewal_notice_days: Optional[int] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None


class ApprovalStepSummary(BaseModel):
    id: str
    step_index: int
    step_name: str
    required_role: str
    decision: str
    sla_hours: int = 48
    due_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None


class ContractOut(ORMModel):
    id: str
    title: str
    contract_number: str
    contract_type: str
    status: str
    counterparty: Optional[str] = None
    owner_id: str
    department: Optional[str] = None
    value_amount: Optional[float] = None
    value_currency: Optional[str] = "USD"
    effective_date: Optional[datetime] = None
    expiration_date: Optional[datetime] = None
    auto_renew: bool = False
    renewal_notice_days: int = 60
    risk_score: float = 0.0
    risk_level: str = "low"
    is_amendment: bool = False
    processing_status: str = "COMPLETED"
    processing_step: Optional[str] = "Completed"
    processing_progress: int = 100
    processing_error: Optional[str] = None
    tags: List[str] = []
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    approval_steps: List[ApprovalStepSummary] = []
    current_approval_step: Optional[str] = None


class ProcessingStatusOut(ORMModel):
    contract_id: str
    processing_status: str
    processing_step: Optional[str] = None
    processing_progress: int = 0
    processing_error: Optional[str] = None
    updated_at: datetime


# ---------- Version ----------
class VersionOut(ORMModel):
    id: str
    contract_id: str
    version_number: int
    version_label: Optional[str] = None
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    sha256_hash: str
    page_count: Optional[int] = None
    change_summary: Optional[str] = None
    risk_delta: float = 0.0
    created_by: str
    created_at: datetime


class VersionDiffOut(BaseModel):
    from_version: int
    to_version: int
    added_clauses: List[Dict[str, Any]]
    removed_clauses: List[Dict[str, Any]]
    modified_clauses: List[Dict[str, Any]]
    risk_delta: float
    summary: str


# ---------- Clause ----------
class ClauseOut(ORMModel):
    id: str
    contract_id: str
    version_id: str
    clause_number: Optional[str] = None
    heading: Optional[str] = None
    body: str
    category: Optional[str] = None
    confidence: float = 0.0
    page_number: Optional[int] = None
    risk_level: str = "low"
    created_at: datetime


# ---------- Risk ----------
class RiskOut(ORMModel):
    id: str
    contract_id: str
    version_id: str
    clause_id: Optional[str] = None
    finding_type: str
    severity: str
    score_rule: float
    score_nlp: float
    score_llm: float
    score_total: float
    title: str
    description: str
    evidence: Optional[str] = None
    recommendation: Optional[str] = None
    source_excerpt: Optional[str] = None
    source_page: Optional[int] = None
    created_at: datetime


# ---------- AI Analysis ----------
class AnalysisOut(BaseModel):
    contract_id: str
    version_id: str
    status: str
    summary: Optional[str] = None
    metadata: Dict[str, Any] = {}
    clauses: List[ClauseOut] = []
    risks: List[RiskOut] = []
    risk_score: float = 0.0
    risk_level: str = "low"
    missing_clauses: List[Dict[str, Any]] = []
    template_deviation: List[Dict[str, Any]] = []
    obligations: List[Dict[str, Any]] = []
    version_comparison: Optional[VersionDiffOut] = None


# ---------- Approvals ----------
class ApprovalOut(ORMModel):
    id: str
    contract_id: str
    workflow_id: str
    step_index: int
    step_name: str
    required_role: str
    assignee_id: Optional[str] = None
    decision: str
    comments: Optional[str] = None
    sla_hours: int
    due_at: datetime
    decided_at: Optional[datetime] = None
    created_at: datetime
    # Optional Contract metadata fields
    contract_title: Optional[str] = None
    contract_number: Optional[str] = None
    counterparty: Optional[str] = None
    contract_type: Optional[str] = None
    value_amount: Optional[float] = None
    value_currency: Optional[str] = "USD"
    risk_level: Optional[str] = "low"
    risk_score: Optional[float] = 0.0


class ApprovalDecisionRequest(BaseModel):
    decision: str
    comments: Optional[str] = None


class WorkflowCreate(BaseModel):
    name: str
    description: Optional[str] = None
    definition: Dict[str, Any]
    is_default: Optional[bool] = False


class WorkflowOut(ORMModel):
    id: str
    name: str
    description: Optional[str] = None
    definition: Dict[str, Any]
    is_default: bool
    is_active: bool
    created_at: datetime


# ---------- Obligations ----------
class ObligationOut(ORMModel):
    id: str
    contract_id: str
    title: str
    description: str
    owner_id: Optional[str] = None
    responsible_role: Optional[str] = None
    due_date: Optional[datetime] = None
    cadence: Optional[str] = None
    status: str
    priority: str
    recurrence_count: int = 0
    last_completed_at: Optional[datetime] = None
    created_at: datetime


class ObligationComplete(BaseModel):
    notes: Optional[str] = None


# ---------- Audit ----------
class AuditOut(ORMModel):
    id: int
    sequence: int
    timestamp: datetime
    actor_email: Optional[str] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    payload: Dict[str, Any] = {}
    entry_hash: str
    previous_hash: Optional[str] = None


class AuditVerifyResult(BaseModel):
    valid: bool
    total_entries: int
    broken_at_sequence: Optional[int] = None
    message: str


# ---------- QA ----------
class QARequest(BaseModel):
    question: str
    contract_ids: Optional[List[str]] = None
    top_k: Optional[int] = 5


class QASource(BaseModel):
    contract_id: str
    contract_title: str
    clause_id: Optional[str] = None
    heading: Optional[str] = None
    page_number: Optional[int] = None
    excerpt: str
    score: float


class QAResponse(BaseModel):
    question: str
    answer: str
    sources: List[QASource] = []
    confidence: float


# ---------- Analytics ----------
class AnalyticsOverview(BaseModel):
    total_contracts: int
    draft: int = 0
    processing: int = 0
    ready_for_review: int = 0
    pending_approval: int = 0
    approved: int = 0
    active: int = 0
    rejected: int = 0
    changes_requested: int = 0
    high_risk: int = 0
    expiring_soon: int = 0
    expired: int = 0
    # Backward compatibility
    active_contracts: int = 0
    pending_approvals: int = 0
    overdue_approvals: int = 0
    high_risk_count: int = 0
    obligations_due_30d: int = 0
    renewals_due_60d: int = 0
    total_value: float = 0.0


class RiskDistribution(BaseModel):
    level: str
    count: int


class ContractByType(BaseModel):
    contract_type: str
    count: int


class BottleneckStep(BaseModel):
    step_name: str
    average_hours: float
    pending_count: int


class ApprovalTimelinePoint(BaseModel):
    date: str
    submitted: int
    approved: int
    rejected: int
