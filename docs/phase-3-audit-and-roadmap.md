# TRACE — Phase 3 Audit & Revised Roadmap

**Audit date**: 2026-09-02
**Auditor method**: direct code reading (`backend/app/core`, `backend/app/models`, `backend/app/api`, `backend/app/services`, `frontend/src`), `grep`/import-graph tracing, and a live `pytest` run — not a re-read of `PROGRESS.md`'s own claims.
**Verdict up front**: `PROGRESS.md` is wrong in both directions. It **understates** the causal graph and frontend (marked "0%"/"Design phase", actually built and wired), and it **overstates** the agent layer (marked "LangGraph ✅", there is no LangGraph — and no ReAct loop either). The ingestion pipeline and MCP evidence tools are real and genuinely end-to-end, more so than the doc's hedged "🔨 in progress" language suggests.

---

## 1. Corrected completion table

Same format as `PROGRESS.md`'s summary table (§ Development Status Summary), replaced with verified numbers.

| Phase | Name | Status | Completion % | Justification |
|---|---|---|---|---|
| 0 | Architecture Freeze | ✅ Complete | 100% | `docs/phase-0/*` present and consistent with blueprint. Unchanged from claim. |
| 1 | Core Infrastructure | ✅ Complete | 100% | FastAPI app boots (once venv is synced — see §5), SQLAlchemy models + Alembic present, audit log real and used. Unchanged from claim. |
| 2 | Evidence & Temporal | ✅ Complete | ~95% | Ingestion is genuinely end-to-end (upload → hash → parse → clean → record → event), verified by passing integration tests. Docked 5% only because clock correction uses `numpy.polyfit`, not the `scipy.stats.linregress` the doc's own tech-stack table claims, and `scipy` isn't even in `requirements.txt`. |
| 3 | Agents & MCP | 🔨 In Progress | **~55%**, not 70% | MCP tools: 7/7 blueprint MVP tools implemented and *callable by the in-process agent adapter* (strong). LangGraph: **absent** — no such dependency, no such import; agents are a fixed-sequence Python orchestrator, not a bounded ReAct loop (weak — this is the biggest gap between claim and reality). Ranking, persistence, and the findings/hypotheses API are fully done, not "pending". |
| 4 | Neo4j Causal Graph | 🔨 In Progress | **~60%**, not 0% | Full builder, Neo4j-backed store, API routes (`/graph`, `/graph/path`), and auto-build-on-investigate wiring all exist in code. Never exercised against a real Neo4j instance by the test suite (forced off via `conftest.py`), so its correctness against the real driver is unverified. This is not "planned" work — it's written and needs verification, not authorship. |
| 5 | Advanced ML | 📋 Planned | 0% | No DTW/pgmpy/Dempster-Shafer/DoWhy code anywhere in `backend/app`. Matches claim. |
| 6 | Future Features | 📋 Research | 0% | Matches claim. |

**Net read**: Phase 3 is *behind* where the doc says on the agent-orchestration axis and *ahead* on the MCP/ranking/persistence axis. Phase 4 is not "planned" — it's an unverified first draft that already runs on every investigation call. The doc's phase boundaries don't actually reflect how the code is organized: Phase 3 (`investigation_service.py`) already triggers Phase 4 graph building inline (see §2.3).

---

## 2. Module-by-module audit

### 2.1 Evidence ingestion pipeline — **exists and is wired in end-to-end**

`backend/app/services/ingestion.py` (`IngestionOrchestrator.ingest`) runs, in one call: SHA-256 hash → duplicate check → `ParserRegistry.parse` (`core/parsers/`) → `DomainProcessor.select_and_clean` (`core/processing/`) → `EvidenceRecord` rows → `EventService.extract_for_artifact` (`core/events/extractor.py`) → `Event` rows + timeline rebuild, all under one DB transaction with audit logging and custody-chain entries at each step. This is not disconnected pieces — `POST /cases/{id}/evidence` (`api/cases.py`) calls this orchestrator directly, and `tests/test_ingestion_pipeline.py` exercises it through the real FastAPI `TestClient` (real SQLite DB, real parsers, real cleaners), asserting record counts, parser/profile IDs, and malformed-input handling (`invalid_record_count`). CSV, JSON, PDF (`pypdf`), and TXT parsers all exist under `core/parsers/` with a registry (`registry.py`) that dispatches by extension/mime.

One accuracy note vs. the blueprint: clock-drift correction (`core/temporal/engine.py:132`) uses `numpy.polyfit`, not `scipy.stats.linregress` as the blueprint's Preferred column and `PROGRESS.md`'s tech-stack table both state. `scipy` is absent from `requirements.txt` entirely. Functionally equivalent (both fit the same affine model), but the doc's own stack table is inaccurate.

### 2.2 MCP layer — **two different things exist under one name**

The blueprint's 8 tools, checked against `core/mcp/tools.py:TOOL_NAMES`:

| Blueprint tool | MVP? | In `EvidenceTools` (in-process adapter) | In `core/mcp/server.py` (real FastMCP/stdio server) |
|---|---|---|---|
| `query_evidence` | YES | ✅ | ✅ |
| `get_event` | YES | ✅ | ❌ |
| `get_events` | YES | ✅ | ❌ |
| `get_timeline` | YES | ✅ | ❌ |
| `get_source_metadata` | YES | ✅ | ❌ |
| `get_evidence_provenance` | YES | ✅ | ❌ |
| `get_evidence_gaps` | YES | ✅ | ✅ |
| `get_related_events` | Advanced | ❌ (not required yet) | ❌ |

Plus non-blueprint extras (`get_domain_features`, `get_anomalies`, `get_conflicts`, `fetch_weather_at_location`) that are real and useful.

The nuance the status doc collapses: there are **two MCP surfaces**. `core/mcp/tools.py::EvidenceTools` is a plain Python class ("MCP-shaped... in-process adapter" per its own docstring) that the investigation orchestrator imports and calls directly — no MCP wire protocol involved. `core/mcp/server.py` is the *actual* Python MCP SDK (`mcp.server.fastmcp.FastMCP`) server that speaks the real protocol over stdio/HTTP for external clients (e.g., Claude Desktop) — but it only registers 4 of the 8 tools (`fetch_weather_at_location`, `query_evidence`, `get_domain_features`, `get_evidence_gaps`) and is never started by the FastAPI app or any test; it's a standalone entrypoint (`python -m app.core.mcp.server`). So: "all 7 MVP tools implemented and reachable by the agent" is true. "MCP evidence access layer" as a standalone protocol surface a third-party agent could connect to is roughly half-built and unexercised.

### 2.3 LangGraph agents — **real findings pipeline, wrong technology, not a ReAct loop**

`core/agents/graph.py`'s own docstring says it plainly: *"LangGraph-shaped state machine (simple async-capable Python orchestrator)."* `langgraph` is not in `requirements.txt` and is not installed in the venv (`ModuleNotFoundError: No module named 'langgraph'` on import attempt). `PROGRESS.md` lists "✅ LangGraph agent orchestration framework" under Phase 1–2 *Complete* — this is false as written; what exists is a hand-rolled orchestrator that happens to produce the same shape of output.

More important than the naming: it is **not a bounded ReAct loop** in the blueprint's sense (§9: hypothesis → retrieve → analyze → identify uncertainty → retrieve more if needed → finding, capped at 3–5 *adaptive* iterations). What's actually implemented (`AGENT_SPECS["tool_plan"]` in `core/agents/synthesizer.py`, executed by `InvestigationOrchestrator._run_domain_agent`) is a **fixed, non-adaptive sequence of tool calls per agent** (4–6 calls, always the same ones, sliced by `max_iterations`) followed by exactly one synthesis step — either the deterministic `synthesize_finding()` heuristic or one LLM call. There is no branching on intermediate results, no "retrieve additional evidence if required" decision point, no loop. It is a real, working, evidence-grounded pipeline — just not the iterative agent behavior the blueprint specifies.

The four domain agents (`train_driver`, `signalling`, `track`, `environment`) are real — each has a distinct tool plan, distinct feature-domain mapping, and distinct hypothesis-text logic in `synthesizer.py`, and `tests/test_investigation_agents.py::test_investigate_api_persists_ranked_findings` confirms all four run and persist through the real API. The meta-agent/arbitration step (`InvestigationOrchestrator.run`, `synthesize_meta_narrative`) is also real and, notably, already produces evidence-weighted ranking exactly per blueprint §10's six dimensions (`core/investigation/ranking.py:DEFAULT_WEIGHTS`) — this is *more* done than the doc's "🔨 Evidence-weighted ranking refinement" suggests; it's not a refinement, it's the whole thing, faithfully implemented.

Pluggable LLM: real. `core/agents/llm.py` implements `HeuristicLLM` (default, no network), `OpenAICompatibleLLM` (Ollama/vLLM/OpenAI), and `AnthropicLLM`, selected via `LLM_PROVIDER` env var — matches blueprint's local-first/pluggable requirement. Only the heuristic path is exercised by tests; the two network-backed providers have no test coverage (reasonably, since they need a live endpoint).

### 2.4 Causal graph (Phase 4) — **substantially built, not "0% planned"**

`core/graph/builder.py` (`CausalGraphBuilder`) materializes blueprint node types (EVENT, HYPOTHESIS, FACTOR, OUTCOME) and edge types (PRECEDES, ASSERTS→CONTRIBUTES_TO/CAUSES per YAML templates in `templates.yaml`, CITED_BY) from real case events and findings, and computes a `causal_support` score via evidenced-path BFS that feeds back into ranking (`graph_service.py:rescore_findings_with_causal_support`). `core/graph/store.py` (`Neo4jGraphStore`) is a real Neo4j driver client (Cypher `MERGE`/`shortestPath` queries) behind `app/api/graph.py` (`GET /cases/{id}/graph`, `POST /graph/rebuild`, `GET /graph/path`). `services/investigation_service.py:run_investigation` already calls `GraphService.build_and_persist` and the causal rescore **inline, on every investigation run** — Phase 3 and Phase 4 are not sequential in the code the way `PROGRESS.md`'s phase table implies.

The caveat: `tests/conftest.py` force-disables Neo4j for every test (`monkeypatch.setattr(settings, "neo4j_enabled", False)`), so all causal-graph tests (`test_causal_graph.py`) exercise only the in-memory dict fallback path in `graph_service.py`, never `Neo4jGraphStore`'s actual Cypher queries. The Neo4j code compiles and follows a coherent schema, but has zero verified executions against a real database in this repo. Call this "written, untested" rather than "built" or "planned."

### 2.5 Frontend — **materially further along than claimed**

`PROGRESS.md` describes the frontend as "Component structure scaffolding" (Phase 1–2 ✅) and "Frontend investigation UI... Status: Design phase" (Phase 3 🔨). In `frontend/src/pages/` there are 12 real, wired page components, not scaffolding: `FindingsPage.tsx` (160 lines), `HypothesesPage.tsx` (110), `CausalGraphPage.tsx` (223), `TimelinePage.tsx` (200), `EvidenceGapsPage.tsx` (130), `EvidenceExplorerPage.tsx` (413), `CaseIngestionPage.tsx` (594), `ConflictsPage.tsx`, `AnomaliesPage.tsx`, `AuditTrailPage.tsx`, `CaseOverviewPage.tsx`, `CasesPage.tsx`, `DashboardPage.tsx` — ~2,750 lines total. `services/api.ts` calls the real backend routes (`fetch` against `/cases/{id}/investigate`, `/findings`, `/hypotheses`, `/graph`, etc.), not mock data. This is not a doc rounding error — "Design phase" is simply false for findings/hypotheses, and the causal graph UI (listed nowhere as started) already exists.

### 2.6 Tests — real integration, minimal mocking

19 test files, 68 tests, **all pass** (once the environment gap in §2.7 is fixed). Only `conftest.py` (DB/Neo4j fixtures) and `test_mcp_weather.py` (external HTTP call to Open-Meteo) use mocking/monkeypatching — every other test drives the real FastAPI `TestClient` against a real (SQLite, per-test) database, exercising actual parser → cleaner → event → investigation → graph code paths, not isolated units with stubbed collaborators. `test_investigation_agents.py::test_investigate_api_persists_ranked_findings` and `test_ingestion_pipeline.py` are the clearest evidence the E2E path (upload → parse → normalize → extract events → investigate → rank → persist) genuinely works, not just individually-passing unit tests. The weak spot: nothing exercises the real Neo4j driver, the real LLM providers (`OpenAICompatibleLLM`/`AnthropicLLM`), or PostgreSQL (tests always use SQLite) — the "PostgreSQL/SQLite database support" claim is real in code (`docker-compose.yml` defines Postgres) but untested.

### 2.7 Environment gap found during this audit (now fixed)

The checked-out `backend/venv` was missing the `neo4j` driver even though it's pinned in `requirements.txt`. Because `core/graph/store.py` imports `neo4j` unconditionally, and that import is reached from `app/main.py` → `api/router.py` → `api/graph.py` → `graph_service.py` → `core/graph/__init__.py`, **the entire FastAPI app failed to start** and `pytest` couldn't even collect tests, before this audit ran `pip install neo4j` in the venv. `scipy` is missing too, but nothing currently imports it at module load time so it didn't block boot. This isn't a code defect — `venv/` isn't tracked in git — but it means "tests pass" and "app runs" were not true in this checkout until now, and it's worth a `pip install -r requirements.txt` in CI/onboarding docs to prevent recurrence.

---

## 3. Revised roadmap

Ordered by what actually needs to happen next, given the gap between what's built and what's verified — not a re-statement of the blueprint's phase list.

1. **Make the agent loop adaptive, or stop calling it a ReAct loop.** Either implement the blueprint's actual retrieve→analyze→identify-uncertainty→retrieve-more pattern (even without LangGraph — a plain `while` loop with an LLM-driven continue/stop decision would satisfy the blueprint), or update the docs/checklist language to describe what's really there: a fixed evidence-gathering pipeline with single-shot synthesis. Don't adopt LangGraph just to match the doc unless there's a concrete need for its graph/state features the current orchestrator lacks — the Model Architecture Review already recommends against pulling in machinery ahead of need.
2. **Verify the Neo4j path for real.** Spin up `docker-compose up neo4j`, flip `neo4j_enabled=True` in a dedicated integration test (or a `@pytest.mark.integration` tier excluded from the default fast run), and confirm `Neo4jGraphStore.replace_case_graph`/`find_path` actually work against the real driver — the Cypher has never executed. This is higher priority than new Phase 4 features since the code already claims to be Phase-4-capable.
3. **Decide what the standalone MCP server (`core/mcp/server.py`) is for, and finish it or drop it.** Right now it's a half-registered, never-started, never-tested entrypoint (4 of 8 tools). If the goal is external MCP-client compatibility (e.g. investigators using Claude Desktop against a case), register the remaining tools and add a smoke test that starts it. If it's not actually needed yet, say so in the docs instead of listing "MCP server" as MVP-status.
4. **Close the frontend/doc gap.** Update `PROGRESS.md` to reflect that findings, hypotheses, causal graph, evidence gaps, conflicts, and audit UI all exist and are wired to real endpoints. This changes what "Phase 3 completion" actually requires — mostly polish/UX and error-state handling, not net-new screens.
5. **Add integration coverage for the two things no test touches**: a live-LLM-provider smoke test (`OpenAICompatibleLLM` against a local Ollama, gated/skipped if unavailable) and a Postgres-backed test run (even just running the existing suite against `docker-compose`'s Postgres once in CI) — both are claimed as supported but only SQLite + heuristic-LLM paths are actually exercised today.
6. **Fix the stack-table inaccuracies** in `PROGRESS.md`/blueprint cross-references: `scipy` isn't a dependency (numpy.polyfit is used instead, which is fine — just say so), and add `pip install -r requirements.txt` as an explicit onboarding step given the venv drift found in §2.7.
7. **Only after 1–3 above are done**, treat the Phase 3→4 gate (blueprint §19: "complete MVP workflow succeeds on at least one fully synthetic end-to-end accident case, all findings traceable to evidence") as met — the ingredients are close, but the gate is about verified behavior, not code existing.
