import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { CaseWorkspaceBanner } from "../components/CaseWorkspaceBanner";
import { getCase, getCaseGraph, rebuildCaseGraph } from "../services/api";
import { getActiveCaseId, setActiveCaseId } from "../services/workspace";
import type { Case, GraphEdge, GraphNode } from "../types/case";

const LAYER_ORDER = [
  "EVENT",
  "HYPOTHESIS",
  "FACTOR",
  "CONDITION",
  "ACTION",
  "SYSTEM_STATE",
  "OUTCOME",
];

function nodeColor(type: string): string {
  switch (type) {
    case "OUTCOME":
      return "#c0392b";
    case "HYPOTHESIS":
      return "#8e44ad";
    case "FACTOR":
      return "#2980b9";
    case "EVENT":
      return "#27ae60";
    default:
      return "#7f8c8d";
  }
}

export function CausalGraphPage() {
  const [params] = useSearchParams();
  const caseId = params.get("case") || getActiveCaseId();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [loading, setLoading] = useState(false);
  const [rebuilding, setRebuilding] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const load = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    try {
      setActiveCaseId(id);
      const [caseResp, graph] = await Promise.all([
        getCase(id),
        getCaseGraph(id),
      ]);
      setCaseData(caseResp);
      setNodes(graph.nodes);
      setEdges(graph.edges);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load graph");
      setNodes([]);
      setEdges([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (caseId) void load(caseId);
  }, [caseId, load]);

  const layout = useMemo(() => {
    const layers: Record<string, GraphNode[]> = {};
    for (const node of nodes) {
      const layer = LAYER_ORDER.includes(node.node_type)
        ? node.node_type
        : "OTHER";
      layers[layer] = layers[layer] || [];
      layers[layer].push(node);
    }
    const positions: Record<string, { x: number; y: number }> = {};
    const orderedLayers = [
      ...LAYER_ORDER.filter((l) => layers[l]?.length),
      ...(layers.OTHER ? ["OTHER"] : []),
    ];
    const width = 720;
    const rowHeight = 90;
    orderedLayers.forEach((layer, li) => {
      const row = layers[layer] || [];
      row.forEach((node, i) => {
        const x = ((i + 1) / (row.length + 1)) * width;
        positions[node.id] = { x, y: 40 + li * rowHeight };
      });
    });
    return { positions, width, height: orderedLayers.length * rowHeight + 60 };
  }, [nodes]);

  const onRebuild = async () => {
    if (!caseId) return;
    setRebuilding(true);
    setError(null);
    try {
      const graph = await rebuildCaseGraph(caseId);
      setNodes(graph.nodes);
      setEdges(graph.edges);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Graph rebuild failed");
    } finally {
      setRebuilding(false);
    }
  };

  const selected = nodes.find((n) => n.id === selectedId);

  return (
    <>
      <div className="page-header">
        <h1>Causal Graph</h1>
        <p>
          Evidence-linked causal structure — edges materialized only when findings
          cite supporting evidence (Phase 4 Neo4j).
        </p>
      </div>

      <CaseWorkspaceBanner
        caseId={caseId || null}
        title={caseData?.title}
        status={caseData?.status}
        evidenceCount={caseData?.evidence_count}
      />

      {error && <div className="alert alert-error">{error}</div>}

      <section className="panel">
        <div className="panel-toolbar">
          <h2>
            Graph ({nodes.length} nodes · {edges.length} edges)
          </h2>
          <button
            type="button"
            className="btn btn-secondary"
            disabled={!caseId || rebuilding}
            onClick={() => void onRebuild()}
          >
            {rebuilding ? "Rebuilding…" : "Rebuild graph"}
          </button>
        </div>

        {loading ? (
          <div className="empty-state">Loading causal graph…</div>
        ) : !caseId ? null : nodes.length === 0 ? (
          <div className="empty-state">
            No graph yet. Run investigation first, then rebuild if needed.
          </div>
        ) : (
          <div className="graph-layout">
            <svg
              className="graph-canvas"
              width={layout.width}
              height={layout.height}
              viewBox={`0 0 ${layout.width} ${layout.height}`}
            >
              {edges.map((edge) => {
                const from = layout.positions[edge.source];
                const to = layout.positions[edge.target];
                if (!from || !to) return null;
                return (
                  <g key={`${edge.source}-${edge.edge_type}-${edge.target}`}>
                    <line
                      x1={from.x}
                      y1={from.y}
                      x2={to.x}
                      y2={to.y}
                      className="graph-edge"
                    />
                    <text
                      x={(from.x + to.x) / 2}
                      y={(from.y + to.y) / 2 - 4}
                      className="graph-edge-label"
                    >
                      {edge.edge_type}
                    </text>
                  </g>
                );
              })}
              {nodes.map((node) => {
                const pos = layout.positions[node.id];
                if (!pos) return null;
                return (
                  <g
                    key={node.id}
                    className={`graph-node ${selectedId === node.id ? "selected" : ""}`}
                    onClick={() => setSelectedId(node.id)}
                  >
                    <circle
                      cx={pos.x}
                      cy={pos.y}
                      r={18}
                      fill={nodeColor(node.node_type)}
                    />
                    <text x={pos.x} y={pos.y + 32} className="graph-node-label">
                      {node.label.slice(0, 28)}
                    </text>
                    <text x={pos.x} y={pos.y + 44} className="graph-node-type">
                      {node.node_type}
                    </text>
                  </g>
                );
              })}
            </svg>

            {selected && (
              <aside className="graph-detail">
                <h3>{selected.label}</h3>
                <p className="table-muted">
                  <code>{selected.id}</code> · {selected.node_type}
                </p>
                <pre>{JSON.stringify(selected.properties, null, 2)}</pre>
              </aside>
            )}
          </div>
        )}
      </section>
    </>
  );
}
