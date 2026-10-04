# Enterprise Contract Lifecycle & Approval Management System

A production-style full-stack **CLM** platform with AI-powered contract intelligence,
configurable multi-level approval workflows, obligation tracking, semantic version
comparison, RAG-based Q&A, explainable hybrid risk scoring, tamper-evident audit
logs (SHA-256 hash chain, no blockchain) and real analytics.

> Built as an end-to-end, runnable system. Every feature uses real database
> records - nothing is hardcoded, faked or mocked.

---

## Highlights

| Area | What's included |
|------|-----------------|
| **Contract repository** | Create, upload, version, amend, renew, archive. SHA-256 hashes verified on every download. |
| **Lifecycle** | `draft → in_review → approved → active → (renewed | expired | archived | terminated | rejected)`. |
| **RBAC** | 7 roles (`requester`, `legal`, `finance`, `manager`, `compliance`, `executive`, `admin`) with scoped JWT tokens. |
| **Approval workflow** | Configurable multi-level engine. SLA per step, role-based routing, comments, history, delegation. Default + high-value + lightweight flows auto-selected by risk/value. |
| **AI** | Clause extraction & classification (40+ categories, CUAD-inspired), metadata extraction, summaries, hybrid risk scoring (rules + NLP + LLM), RAG Q&A with pgvector, semantic version comparison, obligation extraction, missing-clause detection, template-deviation analysis. |
| **Explainability** | Every risk finding cites its source clause, page, and three detector scores (rule / NLP / LLM). |
| **RAG security** | Hardened system prompt. Input scrubbing for prompt-injection patterns. Strict "answer only from cited excerpts" guarantee. Cross-contract leakage guarded by RBAC at retrieval time. |
| **Audit** | Tamper-evident SHA-256 hash-chained log with on-demand integrity verification. |
| **Storage** | Local filesystem by default; S3-compatible (MinIO) supported. Documents hashed on every read. |
| **Analytics** | Overview, risk distribution, type breakdown, bottleneck analysis, timeline, risk trend, obligations. |
| **Workers** | Celery worker + beat scheduler for renewal sweeps and overdue-approval alerts. |

---

## Stack

- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2, Alembic, Pydantic v2, pgvector, Celery, Redis, scikit-learn, PyMuPDF, pypdf, python-docx.
- **Frontend:** Next.js 14 (App Router), React 18, TypeScript, TanStack Query, Tailwind, Recharts, Zustand.
- **DB / Storage:** PostgreSQL 16 + pgvector, Redis, local FS (or MinIO).
- **AI:** Local TF-IDF + hashing embeddings by default (zero external dependencies). Optional OpenAI-compatible LLM for richer answers when `LLM_API_KEY` is provided.

---

## Repository layout

```
contracts-system/
├── docker-compose.yml          # Full stack (db, redis, api, worker, beat, frontend)
├── README.md
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI entrypoint
│   │   ├── core/               # config, security, RBAC
│   │   ├── db/                 # SQLAlchemy session
│   │   ├── models/             # ORM models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── services/
│   │   │   ├── storage.py      # Pluggable storage (local + S3)
│   │   │   ├── parser.py       # PDF / DOCX / TXT extraction
│   │   │   ├── ai/
│   │   │   │   ├── embeddings.py    # Local TF-IDF + cosine
│   │   │   │   ├── clauses.py       # Extraction & 40+ category classification
│   │   │   │   ├── risk.py          # Hybrid rule + NLP + LLM scoring
│   │   │   │   ├── llm.py           # Prompt-hardened LLM + deterministic fallback
│   │   │   │   ├── rag.py           # RAG over pgvector with RBAC filter
│   │   │   │   └── compare.py       # Semantic clause diff
│   │   │   ├── workflow/engine.py   # Multi-level approval engine
│   │   │   ├── audit/chain.py       # SHA-256 hash chain
│   │   │   └── obligations.py
│   │   ├── workers/            # Celery tasks
│   │   └── api/v1/             # FastAPI routers
│   ├── alembic/                # Migrations
│   ├── tests/                  # Unit + integration tests
│   ├── scripts/
│   │   ├── seed.py             # Realistic demo data
│   │   └── demo.py
│   ├── Dockerfile
│   └── requirements.txt
└── frontend/
    ├── app/                    # Next.js 14 App Router
    │   ├── login/
    │   └── (app)/              # Authenticated shell
    │       ├── dashboard/
    │       ├── contracts/
    │       ├── approvals/
    │       ├── obligations/
    │       ├── renewals/
    │       ├── qa/
    │       ├── analytics/
    │       ├── audit/
    │       └── admin/users/
    ├── components/
    ├── lib/
    └── Dockerfile
```

---

## Quick start (Docker)

```bash
cd contracts-system
cp .env.example backend/.env
docker compose up --build
```

Once the stack is up:

- Frontend: <http://localhost:3000>
- API docs (Swagger UI): <http://localhost:8000/api/v1/docs>
- MinIO console (if using S3 backend): <http://localhost:9001>  (`minio` / `minio123`)

The seed script runs automatically inside the backend container on first start,
creating 10 users (one per role), 3 workflows, 3 templates and 6 contracts
spanning low / medium / high / critical risk. A demo amendment is created for the
MSA to exercise the version-comparison flow.

### Demo credentials

Password for every account: **`Demo1234!`**

| Email | Role |
|-------|------|
| `admin@acme.io` | Administrator |
| `exec@acme.io` | Executive |
| `legal@acme.io` | Legal |
| `finance@acme.io` | Finance |
| `compliance@acme.io` | Compliance |
| `manager@acme.io` | Manager |
| `requester@acme.io` | Requester |

---

## Quick start (local Python + Node)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Make sure PostgreSQL is running with the pgvector extension available.
# Then run the schema and seed:
alembic upgrade head
python scripts/seed.py
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

---

## End-to-end demo flow

This is the exact flow that demonstrates every part of the system working
together with real data:

1. **Sign in** as `requester@acme.io` → Dashboard.
2. **Open "Vendor Agreement - Quantum Logistics (HIGH RISK)"** in Contracts.
3. Click **AI analyze** → the system extracts clauses, classifies them across
   40+ categories (e.g. `limitation_of_liability`, `indemnification`),
   computes the hybrid risk score (rules + NLP + LLM signals), persists every
   finding with its source clause and page, and extracts obligations.
4. Open the **Q&A** tab and ask e.g. *"What is the liability cap?"* — the
   answer is generated only from this contract's clauses, with citations.
5. Click **Submit for review** → the engine selects an approval workflow
   appropriate for the contract's risk/value, creates approval steps with
   assignees and SLA deadlines, and notifies the assignees.
6. Sign out, sign in as `legal@acme.io` → the **Approvals inbox** shows the
   pending step. Approve with a comment. Repeat as `manager@acme.io` etc.
7. Sign in as `admin@acme.io` → **Activate** the contract.
8. Switch back to the **Versions** tab → upload a redlined PDF → re-analyze
   → use **Compare versions** to see semantic clause diffs with risk impact.
9. Visit **Obligations** → see extracted action items and mark them complete.
10. Visit **Renewals** → the auto-renewal deadline is visible.
11. Visit **Audit Trail** → every action is in the SHA-256 hash chain. The
    header chip reports "Chain intact".
12. Visit **Analytics** → risk distribution, bottleneck steps, approval
    timeline, risk-findings trend.

---

## Security model

- **JWT** with bearer tokens, configurable expiry.
- **bcrypt** password hashing.
- **RBAC scopes** per role; admin overrides all.
- **Document integrity**: SHA-256 of file bytes stored at upload time and
  re-verified on every download; mismatch → 500.
- **Audit hash chain**: each entry seals the previous one; integrity check
  available at `GET /api/v1/audit/verify`.
- **Prompt-injection defence**: every user-supplied string passed to the
  LLM is scanned for instruction-following patterns and either redacted or
  rejected.
- **Cross-contract leakage**: the RAG retriever applies RBAC filters at the
  SQL layer; requesters can only retrieve clauses from contracts they own.
- **API authorization**: every router uses `Depends(get_current_user)` and
  role checks where required.

---

## AI design

The system is designed so it works **out-of-the-box with zero external
dependencies**. Every "AI" capability has a deterministic, reproducible
implementation:

- **Embeddings** are a local hashed TF-IDF (sign-stabilised, L2-normalised,
  384-dim). IDF is fit at startup on a small corpus so similar phrases land
  near each other in vector space. `sentence-transformers` can be substituted
  by setting `EMBEDDING_MODEL` and adding the dependency.
- **Clause classification** uses cosine similarity against curated category
  prototypes inspired by CUAD; returns a calibrated confidence.
- **Hybrid risk** combines three signals with configurable weights
  (`AI_RISK_RULE_WEIGHT`, `AI_RISK_NLP_WEIGHT`, `AI_RISK_LLM_WEIGHT`) and
  reports all three on every finding. The LLM signal is only added when an
  LLM is configured; otherwise the two available signals are normalised.
- **RAG** retrieves top-k clauses by vector similarity, then a hardened
  prompt constrains the LLM (or the extractive fallback) to answer from
  those excerpts only and cite the clause id + page.
- **Version comparison** uses heading identity plus embedding similarity to
  detect added / removed / modified clauses; risk delta is computed against
  the persisted risk findings of the two versions.

> All AI outputs are **decision support**, not legal authority. Every finding
> is explainable and links back to a source clause.

---

## API surface

| Group | Endpoints |
|-------|-----------|
| Auth | `POST /auth/login`, `POST /auth/refresh`, `GET /auth/me`, `POST /auth/users`, `GET /auth/users`, `PATCH /auth/users/{id}` |
| Contracts | `POST /contracts`, `GET /contracts`, `GET /contracts/{id}`, `PATCH /contracts/{id}`, `POST /contracts/{id}/versions`, `GET /contracts/{id}/versions`, `GET /contracts/{id}/versions/{vid}/download`, `POST /contracts/{id}/submit-for-review`, `POST /contracts/{id}/activate`, `POST /contracts/{id}/archive`, `POST /contracts/{id}/renew`, `POST /contracts/{id}/amendments` |
| AI | `POST /ai/analyze/{cid}/{vid}`, `GET /ai/compare/{cid}?from_version=&to_version=`, `GET /ai/clauses/{cid}`, `GET /ai/risks/{cid}` |
| Approvals | `GET /approvals/inbox`, `GET /approvals/contract/{cid}`, `POST /approvals/{id}/decide`, `GET /approvals/workflows`, `POST /approvals/workflows`, `POST /approvals/workflows/seed-defaults` |
| Obligations | `GET /obligations`, `POST /obligations/{id}/complete`, `POST /obligations/{id}/assign`, `GET /obligations/renewals` |
| Q&A | `POST /qa/ask`, `GET /qa/sessions` |
| Audit | `GET /audit`, `GET /audit/verify`, `GET /audit/contract/{cid}` |
| Analytics | `/analytics/overview`, `/risk-distribution`, `/by-type`, `/bottlenecks`, `/approval-timeline`, `/obligations-summary`, `/risk-trend` |
| Templates | `GET /templates`, `POST /templates` |

Full OpenAPI: <http://localhost:8000/api/v1/docs>

---

## Tests

```bash
cd backend
pytest tests/ -v                  # unit tests (no DB needed for AI tests)
DATABASE_URL=postgresql://contracts:contracts@localhost:5432/contracts pytest tests/ -v
```

The test suite covers embedding similarity, clause extraction, hybrid risk
detection, audit hash-chain determinism, and a full end-to-end API flow.

---

## Production checklist

- [ ] Replace `SECRET_KEY` with a 32+ char random secret.
- [ ] Set `STORAGE_BACKEND=s3` and configure S3/MinIO credentials.
- [ ] Configure an LLM provider (`LLM_PROVIDER=openai`, `LLM_API_KEY=...`)
      for richer answers.
- [ ] Set up TLS termination and rotate JWT signing keys periodically.
- [ ] Add an admin-only endpoint to rotate audit genesis hashes if needed.
- [ ] Wire Celery beat to your monitoring for the renewal/overdue sweeps.

---

## License

MIT — for demonstration and research purposes. Always have qualified counsel
review any production contract before relying on AI-generated outputs.
#   C L M  
 #   C o n t r a c t _ A p p r o v a l _ S y s t e m  
 