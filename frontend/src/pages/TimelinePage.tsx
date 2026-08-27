import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CaseWorkspaceBanner, formatDateTime } from "../components/CaseWorkspaceBanner";
import {
  getCase,
  getCaseTimeline,
  rebuildCaseTimeline,
} from "../services/api";
import {
  getActiveCaseId,
  setActiveCaseId,
} from "../services/workspace";
import type { Case, TimelineEvent } from "../types/case";

function eventLaneKey(event: TimelineEvent): string {
  return event.source_id || event.entity_id || event.evidence_id.slice(0, 8);
}

export function TimelinePage() {
  const [params] = useSearchParams();
  const caseId = params.get("case") || getActiveCaseId();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [rebuiltAt, setRebuiltAt] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<TimelineEvent | null>(null);

  const load = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      setActiveCaseId(id);
      const [caseResp, timeline] = await Promise.all([
        getCase(id),
        getCaseTimeline(id),
      ]);
      setCaseData(caseResp);
      setEvents(timeline.events);
      setRebuiltAt(timeline.rebuilt_at);
      setSelected(timeline.events[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load timeline");
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (caseId) void load(caseId);
  }, [caseId, load]);

  async function handleRebuild() {
    if (!caseId) return;
    setLoading(true);
    setError(null);
    try {
      const timeline = await rebuildCaseTimeline(caseId);
      setEvents(timeline.events);
      setRebuiltAt(timeline.rebuilt_at);
      setSelected(timeline.events[0] ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Timeline rebuild failed");
    } finally {
      setLoading(false);
    }
  }

  const lanes = useMemo(() => {
    const map = new Map<string, TimelineEvent[]>();
    for (const event of events) {
      const key = eventLaneKey(event);
      const list = map.get(key) ?? [];
      list.push(event);
      map.set(key, list);
    }
    return Array.from(map.entries());
  }, [events]);

  const timeBounds = useMemo(() => {
    const stamps = events
      .map((e) => e.corrected_timestamp || e.raw_timestamp)
      .filter(Boolean)
      .map((s) => new Date(s as string).getTime())
      .filter((n) => !Number.isNaN(n));
    if (stamps.length === 0) return null;
    return { min: Math.min(...stamps), max: Math.max(...stamps) };
  }, [events]);

  function positionPercent(event: TimelineEvent): number {
    if (!timeBounds) return 0;
    const stamp = event.corrected_timestamp || event.raw_timestamp;
    if (!stamp) return 0;
    const t = new Date(stamp).getTime();
    if (timeBounds.max === timeBounds.min) return 50;
    return ((t - timeBounds.min) / (timeBounds.max - timeBounds.min)) * 100;
  }

  return (
    <>
      <div className="page-header">
        <h1>Timeline</h1>
        <p>
          Unified temporal reconstruction with source lanes. Markers use
          corrected timestamps from the affine clock model.
        </p>
      </div>

      <CaseWorkspaceBanner
        caseId={caseId || null}
        title={caseData?.title}
        status={caseData?.status}
        evidenceCount={caseData?.evidence_count}
      />

      {error && <div className="alert alert-error">{error}</div>}

      {caseId && (
        <section className="panel">
          <div className="panel-toolbar">
            <h2>
              Events ({events.length})
              {rebuiltAt ? ` · rebuilt ${formatDateTime(rebuiltAt)}` : ""}
            </h2>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={loading}
              onClick={() => void handleRebuild()}
            >
              {loading ? "Working…" : "Rebuild timeline"}
            </button>
          </div>

          {loading && events.length === 0 ? (
            <div className="empty-state">Loading timeline…</div>
          ) : events.length === 0 ? (
            <div className="empty-state">
              No events yet. Upload evidence and rebuild the timeline.
            </div>
          ) : (
            <div className="timeline-lanes">
              {lanes.map(([lane, laneEvents]) => (
                <div key={lane} className="timeline-lane">
                  <div className="timeline-lane-label">{lane}</div>
                  <div className="timeline-lane-track">
                    {laneEvents.map((event) => (
                      <button
                        key={event.event_id}
                        type="button"
                        className={`timeline-marker${selected?.event_id === event.event_id ? " active" : ""}`}
                        style={{ left: `${positionPercent(event)}%` }}
                        title={`${event.event_type} @ ${formatDateTime(event.corrected_timestamp || event.raw_timestamp)}`}
                        onClick={() => setSelected(event)}
                      />
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {selected && (
        <section className="panel">
          <h2>Selected event</h2>
          <div className="meta-grid">
            <div>
              <span className="meta-label">Type</span>
              <span>{selected.event_type}</span>
            </div>
            <div>
              <span className="meta-label">Corrected time</span>
              <span>{formatDateTime(selected.corrected_timestamp)}</span>
            </div>
            <div>
              <span className="meta-label">Raw time</span>
              <span>{formatDateTime(selected.raw_timestamp)}</span>
            </div>
            <div>
              <span className="meta-label">Temporal confidence</span>
              <span>{selected.temporal_confidence.toFixed(2)}</span>
            </div>
            <div>
              <span className="meta-label">Entity</span>
              <span>{selected.entity_id ?? "—"}</span>
            </div>
            <div>
              <span className="meta-label">Source</span>
              <span>{selected.source_id ?? "—"}</span>
            </div>
          </div>
          <pre className="json-block">{JSON.stringify(selected.attributes, null, 2)}</pre>
        </section>
      )}
    </>
  );
}
