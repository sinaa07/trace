# TRACE

TRACE starts as a modular monolith for railway evidence investigation. This repository deliberately contains **no feature logic yet**: it is the Phase 0 architecture-freeze workspace and the minimum scaffold needed to begin Phase 1.

## Immediate work: Phase 0 — Architecture Freeze

Before Phase 1 implementation, freeze and review these artifacts:

1. Core schemas: `Case`, `EvidenceArtifact`, `EvidenceRecord`, `Event`, `HypothesisFinding`, and `Finding`.
2. API contracts and graph model.
3. Synthetic railway evidence specification.
4. Evaluation metrics and ground truth.

The placeholders for these decisions live in [`docs/phase-0`](docs/phase-0/). They are intentionally documentation, rather than premature database or feature code.

## What comes next: Phase 1 — Foundation & Evidence

After Phase 0 is approved, implement case creation, evidence intake, SHA-256/provenance, parsing, and the Evidence Explorer. Keep that work inside `backend/app/core` and `frontend/src/core`. Do not begin the `future` modules until their later phases are scheduled.

## Local development

1. Copy `backend/.env.example` to `backend/.env` and set values if needed.
2. Start the backing services: `docker compose up -d postgres neo4j`.
3. Backend: create a virtual environment, install `backend/requirements.txt`, then run `uvicorn app.main:app --reload` from `backend/`.
4. Frontend: run `npm install` then `npm run dev` from `frontend/`.

PostgreSQL and Neo4j Community are provided through Docker Compose. SQLite is acceptable only for a very small local development setup; PostgreSQL is the default configuration here. Local filesystem storage is the initial evidence-store boundary.

## Repository layout

```text
backend/                 FastAPI application and pytest suite
frontend/                React + TypeScript application
data/synthetic/          Versioned synthetic evidence specifications/data
data/raw/, processed/    Local development evidence (ignored by Git)
docs/phase-0/            Architecture-freeze decision records
docs/future/             Advanced / future-phase parking area
docker-compose.yml       Reproducible local dependencies
```
