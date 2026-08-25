# API contract freeze

Freeze request/response models, status codes, pagination, error format, and authorization assumptions for these specified API groups:

- Cases: `POST /cases`, `GET /cases/{id}`
- Evidence: `POST /cases/{id}/evidence`, `GET /evidence/{id}`
- Timeline: `GET /cases/{id}/timeline`
- Events: `GET /cases/{id}/events`, `POST /cases/{id}/timeline/rebuild`
- Quality: `GET /cases/{id}/anomalies`, `GET /cases/{id}/conflicts`
- Investigation: `POST /cases/{id}/investigate`
- Findings: `GET /cases/{id}/findings`
- Hypotheses: `GET /cases/{id}/hypotheses`
- Graph: `GET /cases/{id}/graph`
- Reports: `POST /cases/{id}/reports`
- Audit: `GET /cases/{id}/audit`

Only `/health` is live in this scaffold. The entries above are contracts to finalize, not implemented endpoints.
