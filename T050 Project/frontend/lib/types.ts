export type Role = "requester" | "legal" | "finance" | "manager" | "compliance" | "executive" | "admin";

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  department?: string;
  is_active: boolean;
  created_at: string;
}

export interface Contract {
  id: string;
  title: string;
  contract_number: string;
  contract_type: string;
  status: string;
  counterparty?: string;
  owner_id: string;
  department?: string;
  value_amount?: number;
  value_currency: string;
  effective_date?: string;
  expiration_date?: string;
  auto_renew: boolean;
  renewal_notice_days: number;
  risk_score: number;
  risk_level: "low" | "medium" | "high" | "critical";
  is_amendment: boolean;
  tags: string[];
  description?: string;
  created_at: string;
  updated_at: string;
}

export interface ContractVersion {
  id: string;
  contract_id: string;
  version_number: number;
  version_label?: string;
  original_filename?: string;
  mime_type?: string;
  size_bytes?: number;
  sha256_hash: string;
  page_count?: number;
  change_summary?: string;
  risk_delta: number;
  created_by: string;
  created_at: string;
}

export interface Clause {
  id: string;
  contract_id: string;
  version_id: string;
  clause_number?: string;
  heading?: string;
  body: string;
  category?: string;
  confidence: number;
  page_number?: number;
  risk_level: string;
  created_at: string;
}

export interface RiskFinding {
  id: string;
  contract_id: string;
  version_id: string;
  clause_id?: string;
  finding_type: string;
  severity: "low" | "medium" | "high" | "critical";
  score_rule: number;
  score_nlp: number;
  score_llm: number;
  score_total: number;
  title: string;
  description: string;
  evidence?: string;
  recommendation?: string;
  source_excerpt?: string;
  source_page?: number;
  created_at: string;
}

export interface Analysis {
  contract_id: string;
  version_id: string;
  status: string;
  summary?: string;
  metadata: Record<string, any>;
  clauses: Clause[];
  risks: RiskFinding[];
  risk_score: number;
  risk_level: string;
  missing_clauses: { category: string; reason: string }[];
  template_deviation: any[];
  obligations: { title: string; description: string; category?: string; priority: string }[];
  version_comparison?: VersionDiff;
}

export interface VersionDiff {
  from_version: number;
  to_version: number;
  added_clauses: { clause_number?: string; heading?: string; preview: string }[];
  removed_clauses: { clause_number?: string; heading?: string; preview: string }[];
  modified_clauses: {
    clause_number?: string;
    heading?: string;
    similarity: number;
    risk_changed: boolean;
    preview: { from: string; to: string };
  }[];
  risk_delta: number;
  summary: string;
}

export interface Approval {
  id: string;
  contract_id: string;
  workflow_id: string;
  step_index: number;
  step_name: string;
  required_role: Role;
  assignee_id?: string;
  decision: "pending" | "approved" | "rejected" | "changes_requested" | "delegated" | "skipped";
  comments?: string;
  sla_hours: number;
  due_at: string;
  decided_at?: string;
  created_at: string;
}

export interface Obligation {
  id: string;
  contract_id: string;
  title: string;
  description: string;
  owner_id?: string;
  responsible_role?: string;
  due_date?: string;
  cadence?: string;
  status: string;
  priority: string;
  recurrence_count: number;
  last_completed_at?: string;
  created_at: string;
}

export interface QASource {
  contract_id: string;
  contract_title: string;
  clause_id?: string;
  heading?: string;
  page_number?: number;
  excerpt: string;
  score: number;
}

export interface QAResponse {
  question: string;
  answer: string;
  sources: QASource[];
  confidence: number;
}

export interface AuditEntry {
  id: number;
  sequence: number;
  timestamp: string;
  actor_email?: string;
  action: string;
  resource_type?: string;
  resource_id?: string;
  payload: Record<string, any>;
  entry_hash: string;
  previous_hash?: string;
}

export interface AnalyticsOverview {
  total_contracts: number;
  active_contracts: number;
  pending_approvals: number;
  overdue_approvals: number;
  high_risk_count: number;
  obligations_due_30d: number;
  renewals_due_60d: number;
  total_value: number;
}
