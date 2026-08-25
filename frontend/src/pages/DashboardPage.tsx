const RESEARCH_FEATURES = [
  {
    title: "Affine Temporal Reconstruction",
    tag: "live" as const,
    highlight: true,
    description:
      "Reconstructs event timelines across heterogeneous sources using declared clock offsets, drift factors, and anchor-point regression — not naive timestamp sorting.",
  },
  {
    title: "Cross-Source Conflict Detection",
    tag: "live" as const,
    highlight: true,
    description:
      "Deterministic alignment compares signal logs, maintenance records, and sensor telemetry to surface contradictory states within configurable tolerance windows.",
  },
  {
    title: "Rule-Based Anomaly Engine",
    tag: "live" as const,
    highlight: true,
    description:
      "Domain-specific YAML rules flag impossible transitions — clock backward jumps, speed threshold breaches, brake sequence violations, invalid signal states.",
  },
  {
    title: "Chain of Custody Provenance",
    tag: "live" as const,
    highlight: false,
    description:
      "Every evidence artifact carries SHA-256 integrity hashing, custody history entries, and audit-logged state transitions from upload through parse completion.",
  },
  {
    title: "Processing Profile Matching",
    tag: "live" as const,
    highlight: false,
    description:
      "Versioned domain profiles score incoming files against expected schemas, flagging low-confidence matches for investigator review before event extraction.",
  },
  {
    title: "Evidence-Grounded Investigation",
    tag: "planned" as const,
    highlight: false,
    description:
      "Multi-agent hypothesis testing with MCP tool access — every finding must cite supporting or contradicting evidence records (Phase 3).",
  },
  {
    title: "Causal Graph Analysis",
    tag: "research" as const,
    highlight: false,
    description:
      "Neo4j-backed cause-effect path tracing links events, findings, and evidence gaps into explorable investigation graphs (Phase 4).",
  },
  {
    title: "Evidence Gap Detection",
    tag: "research" as const,
    highlight: false,
    description:
      "Identifies known unknowns — missing signal coverage windows, absent maintenance logs, or telemetry gaps that could explain unresolved conflicts.",
  },
];

const TAG_LABELS = {
  live: "Implemented",
  research: "Research",
  planned: "Phase 3",
};

export function DashboardPage() {
  return (
    <>
      <div className="page-header">
        <h1>Investigation Dashboard</h1>
        <p>
          TRACE is a digital forensics workspace for railway accident
          investigation. Start by ingesting case evidence, then explore
          temporally reconstructed timelines, cross-source conflicts, and
          rule-detected anomalies.
        </p>
      </div>

      <div className="feature-grid">
        {RESEARCH_FEATURES.map((feature) => (
          <article
            key={feature.title}
            className={`feature-card${feature.highlight ? " highlight" : ""}`}
          >
            <span className={`feature-tag ${feature.tag}`}>
              {TAG_LABELS[feature.tag]}
            </span>
            <h3>{feature.title}</h3>
            <p>{feature.description}</p>
          </article>
        ))}
      </div>
    </>
  );
}
