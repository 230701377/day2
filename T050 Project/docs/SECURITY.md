# Security model

## Authentication

- JWT (HS256) with bearer tokens, configurable expiry (`ACCESS_TOKEN_EXPIRE_MINUTES`).
- Refresh tokens carry a unique `jti` and longer expiry.
- Passwords stored with bcrypt.
- Token revocation is not implemented (production: add a revocation list).

## Authorization

- **Roles**: `requester`, `legal`, `finance`, `manager`, `compliance`,
  `executive`, `admin`.
- **Scope map** (`app/core/rbac.py`): each role gets an explicit list of
  scopes like `contract:read:all`, `approval:act:legal`,
  `obligation:read:all`. Admin gets `*`.
- **Route-level**: every router uses `Depends(get_current_user)` (401 if
  no token) and `Depends(require_role(...))` where stronger guarantees
  are needed (403 if role mismatch).
- **Object-level**: contract endpoints check ownership / role before
  returning or modifying a specific contract.

## Document integrity

- SHA-256 of file bytes is computed at upload and persisted.
- On every download, the hash is recomputed and compared.
- Any mismatch returns 500 and is recorded in the audit log.

## Audit log (hash chain)

- Each entry hashes: `sequence | timestamp | actor | action | resource_type
  | resource_id | payload_json | previous_hash`.
- `previous_hash` is the previous entry's `entry_hash`, or all-zeros for
  the genesis entry.
- `GET /api/v1/audit/verify` walks the chain and returns
  `{ valid, total_entries, broken_at_sequence?, message }`.

## Prompt-injection defence

- Every user-supplied string passed to the LLM is scanned by `sanitize()`,
  which replaces known patterns:
  - `ignore (previous|all|the) instructions`
  - `system prompt`
  - `you are a/an ...`
  - `disregard ... rules/policy`
  - `reveal ... secret/password/key`
  - `act as`
  - `<|...|>`
  - `{{ ... }}`
  - `### instruction`
- The system prompt explicitly forbids the model from following any
  instruction found inside retrieved context.
- The RAG retriever applies RBAC at the SQL layer; requesters can only
  retrieve clauses from contracts they own.

## Input validation

- All API inputs use Pydantic v2 models with strict types, length limits,
  and email format validation.
- File uploads are streamed (`UploadFile`) and size is checked by the
  reverse proxy / nginx in production.
- Path traversal is prevented by storage key construction
  (`contracts/<id>/v<n>_<hash>_<safe_filename>`).

## What is NOT covered (production checklist)

- [ ] TLS termination (handled by reverse proxy in prod)
- [ ] Rate limiting (recommend nginx or an API gateway)
- [ ] Secrets management (use Vault / AWS Secrets Manager / Doppler)
- [ ] Token revocation
- [ ] GDPR data export / delete endpoints
- [ ] SOC2 audit log export
- [ ] WAF rules
- [ ] Vulnerability scanning in CI
