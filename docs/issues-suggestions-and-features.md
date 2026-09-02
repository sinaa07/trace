# TRACE — Issues, Suggestions & Feature Ideas

**Date**: 2026-09-02
**Basis**: `docs/phase-3-audit-and-roadmap.md` (prior session) plus a fresh read-only pass over `backend/app/core`, `backend/app/services`, `backend/app/models`, `backend/app/api`, and `frontend/src` for this session. Documentation-only — nothing in this pass was edited, fixed, or run beyond `grep`/read.

---

## 1. Issues

Concrete problems, not already fully covered in the prior audit's §2/§2.7 environment-gap writeup.

1. **Conflict explanation text renders a Python method object instead of a number.** `f"... within {self.tolerance.total_seconds}s ..."` is missing the `()` call — `total_seconds` is a bound method, so investigator-facing conflict explanations will literally show `<built-in method total_seconds of datetime.timedelta object at 0x...>s`. `backend/app/core/conflicts/detector.py:64`. **Should-fix-soon** (correctness of investigator-facing text).

2. **Uploaded filenames are joined into filesystem paths with no sanitization.** `file.filename` from the multipart upload flows straight through `IngestionOrchestrator.ingest` into `FileStore.store_raw`, which does `dest_dir / filename` with no `Path(...).name` stripping or `..`-containment check before `os.replace`. A crafted filename (e.g. containing `../`) could write outside the intended per-evidence directory. `backend/app/services/storage/file_store.py:23-39`, `backend/app/api/cases.py:217`. **Should-fix-soon** (security; currently low exposure since it's a local single-user tool, but ironic for a chain-of-custody system).

3. **The "uploader can't delete their own evidence" custody control is unauthenticated and trivially bypassed.** `EvidenceService.delete_evidence` compares `actor` (a free-text string the caller supplies on the DELETE request) against the uploader recorded in custody history — there's no session/identity binding, so anyone can delete anyone's evidence by just passing a different `actor` string. `backend/app/services/evidence_service.py:96-105`, `backend/app/api/evidence.py:113-126`. **Should-fix-soon** (blueprint marks auth as Advanced, but this specific control implies protection it doesn't actually provide, which is worse than having no control and claiming nothing).

4. **Evidence delete hard-cascades records and events, contradicting the blueprint's "immutable evidence artifact" principle.** `EvidenceArtifact.records`/`.events` relationships use `cascade="all, delete-orphan"`, so deleting an artifact deletes every derived `EvidenceRecord` and `Event` too — but any `HypothesisFinding.relevant_events` or causal-graph node that already cited those events is left pointing at nothing, silently. `backend/app/models/evidence.py:47-52`, `backend/app/services/evidence_service.py:122-124`. **Should-fix-soon.**

5. **The global exception handler leaks raw exception text to API clients.** Any unhandled exception returns `{"error": {"message": str(exc)}}` with a 500 — this can expose internals (paths, query fragments, library error text) to whoever's calling the API. `backend/app/main.py:23-33`. **Minor today** (local-only deployment), **should-fix-soon** before any non-local exposure.

6. **Zero use of Python's `logging` module anywhere in the backend, and several failures are silently swallowed.** `except Exception: pass`/bare-except patterns discard real failures with no trace: LLM meta-narrative and per-agent LLM failures (`backend/app/core/agents/graph.py:132,159`), causal-graph build failure on investigation run (`backend/app/services/investigation_service.py:124`, comment says "succeeds even if Neo4j is unavailable" but there's no way to know it happened), and the CSV parser's pandas-vs-manual fallback (`backend/app/core/parsers/csv_parser.py:46`, the original pandas error is never recorded). **Should-fix-soon** — these are exactly the failures an operator most needs visibility into.

7. **Timeline-correction reattachment uses a non-unique correlation key.** `EventService.rebuild_case_timeline` builds `corrected_by_key` keyed by `(record_id, event_type)` to map `TemporalEngine.reconstruct()` output back onto persisted `Event` rows (needed because `reconstruct()` re-sorts its output, see `core/temporal/engine.py:82-87`, so a positional zip wouldn't work). Nothing in the event-rule schema prevents a single record from emitting two events of the same type, and if that happens one event's corrected timestamp/timeline index is silently dropped from the update with no warning. `backend/app/services/event_service.py:149-171`. **Should-fix-soon** — temporal reconstruction correctness is the project's stated core differentiator.

8. **`FileStore.verify_hash()` is dead code.** The blueprint's integrity workflow (§5) explicitly requires "verify hash when evidence is re-accessed," and the function exists to do exactly that — but nothing in the codebase ever calls it. `backend/app/services/storage/file_store.py:45-48`. **Should-fix-soon** (blueprint-mandated forensic-integrity gap, not just an unused helper).

9. **Only 4 of the blueprint's 7 anomaly rule categories are implemented.** `railway_rules.yaml` covers clock-backward, speed-threshold, brake-sequence, and signal-transition; missing entirely: temporal prerequisite, maintenance interval, physical plausibility. `PROGRESS.md`'s "✅ Railway-specific rules (signal transitions, speed violations, etc.)" reads as more complete than it is. `backend/app/core/anomalies/rules/railway_rules.yaml`. **Minor.**

10. **Evidence references on findings are unstructured strings, not validated IDs.** `HypothesisFindingCreate.supporting_evidence`/`contradicting_evidence` is a plain `list[str]` (`backend/app/schemas/investigation.py:33-34`), and `synthesizer.py` populates it with a mix of real IDs (`evidence_record:{uuid}`, `anomaly:{uuid}:...`) and free-text descriptive tags (`domain_feature:fatigue:...`, `low_risk_feature:...`) — nothing validates any of these are dereferenceable. This directly undercuts the blueprint's stated primary design principle ("no finding without an evidence path"). **Should-fix-soon** — conceptually central to the project's value proposition, not cosmetic.

11. **Two different, inconsistent speed thresholds coexist.** The anomaly engine's speed rule is configurable via YAML (`max_speed_kmh: 120`), but `ConflictDetector._maintenance_sensor_conflicts` hardcodes `speed_val > 100` for its own "abnormal condition" check, unrelated to and inconsistent with the configured threshold. `backend/app/core/conflicts/detector.py:111`. **Minor.**

12. **Default DB/Neo4j credentials are baked into `Settings` class defaults, not just `.env.example`.** If env vars are ever unset in a real deployment, the app silently runs with `trace_dev_password` rather than failing to start. `backend/app/core/config.py:14,40`. **Minor** at current (local dev) stage.

13. **`scipy` is referenced by docs but was never actually declared as a dependency.** `PROGRESS.md`'s tech-stack table and the blueprint's Preferred column both list SciPy for clock correction; `requirements.txt` never included it at all (not just missing from the venv, as the prior audit found for `neo4j` — this one was never pinned). Code uses `numpy.polyfit` instead, which works fine. `backend/requirements.txt`. **Minor** (doc/dependency-declaration mismatch, not a runtime break).

---

## 2. Suggestions

Improvements to what already exists — no new functionality.

1. **Reconcile "LangGraph"/"bounded ReAct loop" language with reality.** `PROGRESS.md`, blueprint cross-references, and even `core/agents/graph.py`'s own docstring ("LangGraph-shaped state machine") describe something more adaptive than the fixed tool-plan pipeline that's actually there. Either the language or the implementation should move. — **S**

2. **Decide what `core/mcp/server.py` is for.** It's a real FastMCP stdio/HTTP server but only registers 4 of the 8 blueprint tools and is never started by the app or exercised by any test. Finish registering the rest + add a startup smoke test, or explicitly document it as not part of the supported path yet. — **S/M**

3. **Add structured logging at the silent-failure points in Issue #6.** Even just `logging.getLogger(__name__).exception(...)` in those four spots would turn invisible failures into diagnosable ones. — **S**

4. **Add an integration test tier that runs against real Neo4j.** `conftest.py:19-20,67` monkeypatches `neo4j_enabled=False` for every test; `Neo4jGraphStore`'s Cypher has never actually executed. A `docker-compose up neo4j` + `@pytest.mark.integration`-gated test would close this. — **M**

5. **Add a Postgres-backed test run.** Tests only ever use per-test SQLite despite Postgres being the intended shared-deployment DB (`docker-compose.yml` defines it). Even one CI job running the suite against real Postgres would catch dialect-specific issues (e.g. JSONB handling that's currently monkeypatched away for SQLite in `conftest.py:36-42`). — **S/M**

6. **Add a smoke test for the network-backed LLM providers.** `OpenAICompatibleLLM`/`AnthropicLLM` have zero test coverage today; a test that's skipped when no local endpoint/key is configured would still catch request/response-shape regressions when one is available. — **S**

7. **Sanitize uploaded filenames before they touch the filesystem.** `Path(filename).name` plus a character allowlist in `FileStore.store_raw` is cheap defense-in-depth, independent of and prior to adding real auth (Issue #2). — **S**

8. **Make evidence references structured instead of freeform strings.** Splitting `supporting_evidence`/`contradicting_evidence` into e.g. `evidence_refs: list[UUID]` + separate free-text `notes` would make the "evidence path" claim in Issue #10 machine-checkable rather than aspirational. — **M**

9. **Fill out the 3 missing anomaly rule categories** (temporal prerequisite, maintenance interval, physical plausibility) in `railway_rules.yaml`. The rule engine's `type`-dispatch pattern already supports adding new rule types without touching existing ones. — **S per rule, M total**

10. **Unify the two speed thresholds** (Issue #11) into one config value shared by the anomaly engine and conflict detector. — **S**

11. **Replace the hand-rolled SVG causal-graph layout with a real graph library.** `CausalGraphPage.tsx` does its own layered-layout math with no pan/zoom/drag/overlap-avoidance; fine for a handful of nodes, will become unreadable as cases grow. Blueprint already recommends Cytoscape.js/React Flow for this. — **M**

12. **Update `PROGRESS.md` to reflect the corrected completion table** from the prior audit. Right now a new contributor reading it forms the same wrong picture this audit had to correct — the doc itself is the biggest "process" gap. — **S**

13. **Make CORS origins configurable via `Settings`** instead of hardcoded to `localhost:5173`, ahead of any non-local deployment. — **S**

14. **Wire `FileStore.verify_hash()` into an actual code path** (e.g. an `/evidence/{id}/verify` action or a check on evidence GET) so the blueprint's re-access integrity check (Issue #8) is real rather than unreachable. — **S**

---

## 3. New feature ideas

Opinionated — includes blueprint items that are missing outright, and a couple of pushbacks on blueprint scope.

### MVP-adjacent (blueprint already calls for these; they're just not built)

1. **Raw evidence file viewer/download.** `EvidenceExplorerPage.tsx` only ever shows parsed/normalized JSON — there's no API route that serves the original uploaded file at all. Investigators verifying provenance need to see the actual PDF/CSV, not just what TRACE extracted from it. Blueprint §14 explicitly calls for source/provenance inspection in the Evidence Explorer.

2. **Finding review workflow (accept/reject/needs-review).** Named explicitly in blueprint §14 and the MVP freeze checklist (§19: "Investigator accept/reject/review ✓"). There's no status field on `HypothesisFinding` and no corresponding UI control in `FindingsPage.tsx` — this isn't partially done, it hasn't started.

3. **Evidence integrity re-verification action**, surfacing the currently-dead `FileStore.verify_hash()` (Issue #8) as a real "Verify Integrity" button on the evidence detail view — directly matches blueprint §5's re-access verification requirement.

4. **Richer evidence-gaps objects.** Blueprint §13C's example ties a gap to specific *affected hypotheses* and a *recommended next evidence* action; the current `get_evidence_gaps`/`EvidenceGapsPage` only returns flat missing-source/missing-input lists with no link back to which hypotheses they'd affect or what to go collect. Worth tightening to match the blueprint's own example shape.

### Advanced (blueprint already scopes these as Advanced — noting priority within that tier)

5. **Adaptive/iterative agent retrieval** (an actual ReAct loop, not the current fixed tool-plan). This is technically MVP language in the blueprint, but the value — agents deciding mid-investigation that they need more evidence — only shows up once cases get evidentially messy. I'd treat it as the first Advanced-adjacent item to build, not an MVP blocker, once §2's language mismatch (above) is at least acknowledged.

6. **Similar-case retrieval.** Already Advanced per blueprint; noting it's premature until there's more than one real synthetic case in `data/synthetic/cases/` to retrieve *against*.

### Genuinely future, or worth reconsidering

7. **Hold off on DTW/Bayesian Network/Dempster-Shafer/DoWhy.** Nothing in the current data model or ingestion pipeline produces the continuous telemetry DTW needs, and there's no accident corpus to seed BN priors from. I'd go further than the existing Model Architecture Review's caution here: don't start any of these speculatively — wait until 3-5 real synthetic E2E cases have gone through the MVP path and a concrete, observed gap in ranking or explainability motivates one specifically.

8. **Reconsider whether Neo4j needs to be MVP at all.** The causal-graph feature set investigators actually touch (path tracing, evidence-linked edges) is already fully served by the in-memory fallback that exists today (`graph_service.py:36`, `_memory` dict) for a single-case, single-investigator workflow — which is the only workflow this system currently has. Neo4j adds a whole separate database, driver, and docker-compose dependency for benefits (cross-case graph queries at scale) that don't exist yet. The blueprint itself offers NetworkX as a "smaller prototype" alternative (§11) — I think that alternative undersells how far it could actually carry the project, and would suggest revisiting the Neo4j-as-MVP call rather than just verifying the untested Cypher (audit roadmap item 2).
