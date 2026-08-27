# API contract freeze

Freeze request/response models, status codes, pagination, error format, and authorization assumptions for these specified API groups:

- Cases: `POST /cases`, `GET /cases`, `GET /cases/{id}`, `PATCH /cases/{id}`
- Evidence: `POST /cases/{id}/evidence`, `GET /cases/{id}/evidence`, `GET /evidence/{id}`, `DELETE /evidence/{id}`
- Records: `GET /cases/{id}/records`, `GET /evidence/{id}/records`, `GET /evidence/records/{record_id}`
- Timeline: `GET /cases/{id}/timeline`, `GET /cases/{id}/events`, `POST /cases/{id}/timeline/rebuild`
- Quality: `GET /cases/{id}/anomalies`, `GET /cases/{id}/conflicts`
- Investigation: `GET /cases/{id}/domain-features`, `POST /cases/{id}/investigate`
- Findings: `GET /cases/{id}/findings`
- Hypotheses: `GET /cases/{id}/hypotheses`
- Graph: `GET /cases/{id}/graph`
- Reports: `POST /cases/{id}/reports`
- Audit: `GET /cases/{id}/audit`

Live endpoints exist for cases, evidence, records, timeline, quality, domain-features, investigate, findings, and hypotheses. Remaining graph/report routes are Phase 4–5 contracts.
