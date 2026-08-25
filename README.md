# TRACE


## Local development

1. Copy `backend/.env.example` to `backend/.env` and set values if needed.
2. Start the backing services: `docker compose up -d postgres neo4j`.
3. Backend: create a virtual environment, install `backend/requirements.txt`, then run `uvicorn app.main:app --reload` from `backend/`.
4. Frontend: run `npm install` then `npm run dev` from `frontend/`.

PostgreSQL and Neo4j Community are provided through Docker Compose. SQLite is acceptable only for a very small local development setup; PostgreSQL is the default configuration here. Local filesystem storage is the initial evidence-store boundary.


