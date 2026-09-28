import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { getPipelineDetails, type PipelineRunDetail } from "../api";
import { Icon } from "./Icon";

const CARD = "rounded-xl2 border border-line bg-panel";

interface Props {
  sessionId: string;
  workspace?: string;
  taskTitle?: string;
  onBack: () => void;
  onOpenChat: (sessionId: string) => void;
}

export function PipelineDetailView({
  sessionId,
  workspace,
  taskTitle,
  onBack,
  onOpenChat,
}: Props) {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);
  const [pipeline, setPipeline] = useState<PipelineRunDetail | null>(null);
  const [activeStage, setActiveStage] = useState<string>("intake");
  const [approvalStatus, setApprovalStatus] = useState<string>("pending");
  const [approving, setApproving] = useState(false);
  const [viewMode, setViewMode] = useState<"stages" | "nodes">("stages");
  const [expandedNodes, setExpandedNodes] = useState<Record<string, boolean>>({});

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getPipelineDetails(sessionId)
      .then((data) => {
        if (!cancelled) {
          setPipeline(data);
          if (data.pipeline_type === "dynamic" || (!data.stages?.length && data.nodes?.length)) {
            setViewMode("nodes");
          }
          if (data.stages && data.stages.length > 0) {
            setActiveStage(data.stages[0].stage_id);
          }
          const gateStage = data.stages?.find((s) =>
            s.stage_id === "approval_gate" || s.stage_id === "human_gate"
          );
          if (gateStage?.data?.decision === "allowed" || gateStage?.data?.decision === "approved") {
            setApprovalStatus("approved");
          } else if (gateStage?.status === "waiting_approval") {
            setApprovalStatus("waiting");
          } else {
            setApprovalStatus("approved");
          }
          setLoading(false);
        }
      })
      .catch(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId]);

  const toggleNodeExpand = (nodeId: string) => {
    setExpandedNodes((prev) => ({
      ...prev,
      [nodeId]: !prev[nodeId],
    }));
  };

  const handleApprove = () => {
    setApproving(true);
    setTimeout(() => {
      setApprovalStatus("approved");
      setApproving(false);
    }, 400);
  };

  const handleReject = () => {
    setApprovalStatus("rejected");
  };

  const intakeStage = pipeline?.stages?.find((s) => s.stage_id === "intake");
  const scoringStage = pipeline?.stages?.find((s) => s.stage_id === "severity_scoring");
  const draftStage = pipeline?.stages?.find((s) => s.stage_id === "insurance_draft");
  const gateStage = pipeline?.stages?.find((s) =>
    s.stage_id === "approval_gate" || s.stage_id === "human_gate"
  );
  const nodes = pipeline?.nodes || [];

  const severity = scoringStage?.data?.severity || "P0-CRITICAL";
  const isP0 = severity.includes("P0");
  const isP1 = severity.includes("P1");
  const isFoodPoisoning =
    pipeline?.workflow !== "physical_document_processing" &&
    (pipeline?.persona_id === "food-poisoning-triage" || pipeline?.persona_id === "gastro-worker");

  return (
    <main className="flex-1 min-w-0 flex bg-paper" data-testid="pipeline-detail-view">
      <div className="flex-1 min-w-0 overflow-y-auto hairline-scroll">
        <div className="max-w-4xl mx-auto px-7 py-6 space-y-6">
          {/* Top navigation actions */}
          <div className="flex items-center justify-between gap-4">
            <button
              onClick={onBack}
              className="inline-flex items-center gap-1.5 text-sm text-muted hover:text-ink transition-colors font-medium"
              data-testid="pipeline-back-btn"
            >
              <Icon name="arrowLeft" size={14} />
              {t("pipeline.back_to_runs", "Back to runs")}
            </button>
            <div className="flex items-center gap-2">
              {/* View mode toggle */}
              {pipeline?.stages && pipeline.stages.length > 0 && nodes.length > 0 && (
                <div className="flex items-center rounded-lg border border-line bg-panel p-0.5 text-xs font-medium">
                  <button
                    onClick={() => setViewMode("stages")}
                    className={`px-3 py-1 rounded-md transition-colors ${
                      viewMode === "stages"
                        ? "bg-paper text-ink shadow-xs font-semibold"
                        : "text-muted hover:text-ink"
                    }`}
                    data-testid="toggle-stages-view"
                  >
                    {t("pipeline.view_stages", "Stages View")}
                  </button>
                  <button
                    onClick={() => setViewMode("nodes")}
                    className={`px-3 py-1 rounded-md transition-colors ${
                      viewMode === "nodes"
                        ? "bg-paper text-ink shadow-xs font-semibold"
                        : "text-muted hover:text-ink"
                    }`}
                    data-testid="toggle-nodes-view"
                  >
                    {t("pipeline.view_nodes", "Execution Graph")} ({nodes.length})
                  </button>
                </div>
              )}
              <button
                onClick={() => onOpenChat(sessionId)}
                className="inline-flex items-center gap-2 px-3 py-1.5 rounded-lg border border-line bg-panel hover:bg-hover text-ink text-sm font-medium transition-colors shadow-xs"
                data-testid="pipeline-open-chat-btn"
              >
                <Icon name="chat" size={15} />
                {t("pipeline.view_chat_log", "View chat log")}
              </button>
            </div>
          </div>

          {loading ? (
            <div className={`${CARD} p-8 text-center text-muted`}>
              {t("pipeline.loading", "Loading pipeline details...")}
            </div>
          ) : !pipeline || !pipeline.ok ? (
            <div className={`${CARD} p-8 text-center space-y-3`}>
              <div className="text-danger font-medium">
                {pipeline?.error || t("pipeline.error_load", "Failed to load pipeline")}
              </div>
              <button
                onClick={() => onOpenChat(sessionId)}
                className="btn text-sm"
              >
                {t("pipeline.view_chat_log", "View chat log")}
              </button>
            </div>
          ) : (
            <>
              {/* Header Card */}
              <div className={`${CARD} p-5 space-y-3`}>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-muted">
                      <Icon name="shield" size={14} className="text-accent" />
                      <span>{pipeline.persona_id || "automation"}</span>
                      <span>·</span>
                      <span>{intakeStage?.data?.case_id || sessionId}</span>
                    </div>
                    <h1 className="text-xl font-semibold text-ink mt-1">
                      {pipeline.title || taskTitle || t("pipeline.default_title", "Automation Pipeline Details")}
                    </h1>
                  </div>
                  <div className="flex items-center gap-2">
                    {isFoodPoisoning && scoringStage?.data?.severity && (
                      <span
                        className={`inline-flex items-center px-2.5 py-1 rounded-full text-xs font-semibold ${
                          isP0
                            ? "bg-red-500/15 text-red-600 dark:text-red-400 border border-red-500/20"
                            : isP1
                            ? "bg-amber-500/15 text-amber-600 dark:text-amber-400 border border-amber-500/20"
                            : "bg-blue-500/15 text-blue-600 dark:text-blue-400 border border-blue-500/20"
                        }`}
                        data-testid="pipeline-severity-badge"
                      >
                        {severity}
                      </span>
                    )}
                    <span className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-line/50 text-muted">
                      {pipeline.status === "completed"
                        ? t("pipeline.status_completed", "Completed")
                        : pipeline.status === "waiting_approval"
                        ? t("pipeline.status_waiting", "Awaiting Approval")
                        : t("pipeline.status_running", "Running")}
                    </span>
                  </div>
                </div>

                <div className="text-xs text-muted">
                  Session ID: <code className="text-ink font-mono">{sessionId}</code>
                  {workspace && <span> · Workspace: <code className="text-ink">{workspace}</code></span>}
                </div>
              </div>

              {/* No Incident Banner (if detected) */}
              {pipeline.has_incident === false && (
                <div className="p-4 rounded-xl2 border border-emerald-500/20 bg-emerald-500/10 text-emerald-800 dark:text-emerald-200 text-sm space-y-1">
                  <div className="font-semibold flex items-center gap-1.5">
                    <Icon name="shield" size={15} />
                    <span>{t("pipeline.no_incident_title", "All Clear: No Complaints Detected")}</span>
                  </div>
                  <div className="text-xs text-muted leading-relaxed">
                    {intakeStage?.data?.summary || t("pipeline.no_incident_desc", "No unread food poisoning complaints found in this run. Routine operations continue safely.")}
                  </div>
                </div>
              )}

              {/* VIEW MODE 1: EXECUTION GRAPH / NODES */}
              {viewMode === "nodes" && (
                <div className="space-y-3" data-testid="pipeline-nodes-container">
                  <div className="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-muted px-1">
                    <span>{t("pipeline.execution_trace", "Execution Trace & Node Graph")} ({nodes.length} Nodes)</span>
                    <span>Chronological Flow</span>
                  </div>

                  <div className="space-y-2.5">
                    {nodes.map((n, i) => {
                      const isExpanded = !!expandedNodes[n.node_id];
                      const isGate = n.type === "human_gate";
                      const isTool = n.type === "tool";
                      const isScript = n.type === "script";
                      const isArtifact = n.type === "artifact";
                      const isTrigger = n.type === "trigger";

                      return (
                        <div
                          key={n.node_id}
                          className={`${CARD} p-4 transition-all hover:border-lineStrong`}
                          data-testid={`node-card-${n.node_id}`}
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="flex items-start gap-3 min-w-0">
                              <span
                                className={`w-6 h-6 rounded-lg text-xs flex items-center justify-center font-bold flex-shrink-0 mt-0.5 ${
                                  isTrigger
                                    ? "bg-blue-500/15 text-blue-600 dark:text-blue-400"
                                    : isScript
                                    ? "bg-purple-500/15 text-purple-600 dark:text-purple-400"
                                    : isTool
                                    ? "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400"
                                    : isArtifact
                                    ? "bg-amber-500/15 text-amber-600 dark:text-amber-400"
                                    : isGate
                                    ? "bg-rose-500/15 text-rose-600 dark:text-rose-400"
                                    : "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                                }`}
                              >
                                {i + 1}
                              </span>
                              <div className="min-w-0">
                                <div className="flex items-center gap-2">
                                  <span className="text-xs uppercase font-mono px-1.5 py-0.5 rounded bg-line/40 text-muted">
                                    {n.type}
                                  </span>
                                  {n.tool_name && (
                                    <span className="text-xs font-mono text-ink">
                                      {n.tool_name}
                                    </span>
                                  )}
                                </div>
                                <h3 className="text-sm font-semibold text-ink mt-1 truncate">
                                  {n.title}
                                </h3>
                                {n.description && (
                                  <p className="text-xs text-muted mt-0.5">
                                    {n.description}
                                  </p>
                                )}
                              </div>
                            </div>

                            <div className="flex items-center gap-2 flex-shrink-0">
                              <span
                                className={`text-[11px] font-semibold px-2 py-0.5 rounded-full ${
                                  n.status === "completed"
                                    ? "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400"
                                    : n.status === "waiting_approval"
                                    ? "bg-amber-500/15 text-amber-600 dark:text-amber-400 animate-pulse"
                                    : "bg-line/60 text-muted"
                                }`}
                              >
                                {n.status}
                              </span>
                              {(n.inputs || n.outputs) && (
                                <button
                                  onClick={() => toggleNodeExpand(n.node_id)}
                                  className="text-xs text-muted hover:text-ink px-2 py-1 rounded border border-line bg-paper"
                                  data-testid={`toggle-node-${n.node_id}`}
                                >
                                  {isExpanded ? t("pipeline.hide_payload", "Hide") : t("pipeline.inspect_payload", "Inspect")}
                                </button>
                              )}
                            </div>
                          </div>

                          {/* Expanded Input / Output Payload Viewer */}
                          {isExpanded && (
                            <div className="mt-3 pt-3 border-t border-line grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
                              {n.inputs && Object.keys(n.inputs).length > 0 && (
                                <div className="space-y-1">
                                  <div className="text-[11px] font-semibold text-muted uppercase font-sans">
                                    {t("pipeline.inputs", "Node Inputs")}
                                  </div>
                                  <pre className="p-2.5 rounded-lg bg-paper border border-line text-ink whitespace-pre-wrap max-h-48 overflow-y-auto hairline-scroll">
                                    {typeof n.inputs === "string" ? n.inputs : JSON.stringify(n.inputs, null, 2)}
                                  </pre>
                                </div>
                              )}
                              {n.outputs && (
                                <div className="space-y-1">
                                  <div className="text-[11px] font-semibold text-muted uppercase font-sans">
                                    {t("pipeline.outputs", "Node Outputs / Results")}
                                  </div>
                                  <pre className="p-2.5 rounded-lg bg-paper border border-line text-ink whitespace-pre-wrap max-h-48 overflow-y-auto hairline-scroll">
                                    {typeof n.outputs === "string" ? n.outputs : JSON.stringify(n.outputs, null, 2)}
                                  </pre>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* VIEW MODE 2: STAGES VIEW */}
              {viewMode === "stages" && pipeline.stages && (
                <>
                  {/* Stepper Header */}
                  <div className={`${CARD} p-3`}>
                    <div className="grid grid-cols-1 sm:grid-cols-4 gap-2">
                      {pipeline.stages.map((st, idx) => {
                        const isSelected = activeStage === st.stage_id;
                        const isCompleted = st.status === "completed";
                        const isWaiting = st.status === "waiting_approval";
                        return (
                          <button
                            key={st.stage_id}
                            onClick={() => setActiveStage(st.stage_id)}
                            className={`text-left p-3 rounded-xl transition-all border ${
                              isSelected
                                ? "bg-paper border-accent/60 shadow-xs ring-1 ring-accent/30"
                                : "border-transparent hover:bg-hover/60"
                            }`}
                            data-testid={`stage-tab-${st.stage_id}`}
                          >
                            <div className="flex items-center justify-between gap-1 text-xs text-muted mb-1">
                              <span className="font-semibold">{t("pipeline.stage_prefix", "Stage")} {idx + 1}</span>
                              <span
                                className={`inline-block w-2 h-2 rounded-full ${
                                  isCompleted
                                    ? "bg-emerald-500"
                                    : isWaiting
                                    ? "bg-amber-500 animate-pulse"
                                    : "bg-muted"
                                }`}
                              />
                            </div>
                            <div className="text-xs font-semibold text-ink truncate">
                              {st.title}
                            </div>
                            <div className="text-[11px] text-muted capitalize mt-0.5">
                              {isCompleted
                                ? t("pipeline.completed", "Completed")
                                : isWaiting
                                ? t("pipeline.awaiting_review", "Action Required")
                                : st.status}
                            </div>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {/* Food Poisoning Specialized Cards */}
                  {isFoodPoisoning ? (
                    <>
                      {/* Stage 1: Intake */}
                      {(activeStage === "intake" || !activeStage) && intakeStage && (
                        <div className={`${CARD} p-6 space-y-4`} data-testid="stage-card-intake">
                          <div className="flex items-center justify-between">
                            <h2 className="text-base font-semibold text-ink flex items-center gap-2">
                              <span className="w-5 h-5 rounded-full bg-accent/15 text-accent text-xs flex items-center justify-center font-bold">1</span>
                              {intakeStage.title}
                            </h2>
                            <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded">
                              {t("pipeline.verified", "Verified")}
                            </span>
                          </div>

                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                            <div className="p-3.5 rounded-lg bg-paper border border-line space-y-1">
                              <div className="text-xs text-muted">{t("pipeline.guest_name", "Affected Guest / Claimant")}</div>
                              <div className="font-medium text-ink">{intakeStage.data.guest_name}</div>
                            </div>
                            <div className="p-3.5 rounded-lg bg-paper border border-line space-y-1">
                              <div className="text-xs text-muted">{t("pipeline.visit_time", "Dining Date & Time")}</div>
                              <div className="font-medium text-ink">{intakeStage.data.visit_time}</div>
                            </div>
                            <div className="p-3.5 rounded-lg bg-paper border border-line space-y-1 md:col-span-2">
                              <div className="text-xs text-muted">{t("pipeline.consumed_dishes", "Dishes Consumed")}</div>
                              <div className="font-medium text-ink">{intakeStage.data.dishes}</div>
                            </div>
                            <div className="p-3.5 rounded-lg bg-paper border border-line space-y-1">
                              <div className="text-xs text-muted">{t("pipeline.incubation_time", "Incubation Window")}</div>
                              <div className="font-medium text-ink">{intakeStage.data.incubation_time}</div>
                            </div>
                            <div className="p-3.5 rounded-lg bg-paper border border-line space-y-1">
                              <div className="text-xs text-muted">{t("pipeline.symptoms", "Primary Symptoms")}</div>
                              <div className="font-medium text-ink">{intakeStage.data.symptoms}</div>
                            </div>
                          </div>

                          {intakeStage.data.evidence_files && intakeStage.data.evidence_files.length > 0 && (
                            <div className="pt-2 border-t border-line">
                              <div className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">
                                {t("pipeline.evidence_docs", "Evidence & Documentation")}
                              </div>
                              <div className="flex flex-wrap gap-2">
                                {intakeStage.data.evidence_files.map((f: string, i: number) => (
                                  <div
                                    key={i}
                                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-paper border border-line text-xs font-mono text-ink"
                                  >
                                    <Icon name="file" size={13} className="text-muted" />
                                    <span>{f}</span>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}

                      {/* Stage 2: Risk Scoring */}
                      {(activeStage === "severity_scoring" || !activeStage) && scoringStage && (
                        <div className={`${CARD} p-6 space-y-4`} data-testid="stage-card-scoring">
                          <div className="flex items-center justify-between">
                            <h2 className="text-base font-semibold text-ink flex items-center gap-2">
                              <span className="w-5 h-5 rounded-full bg-accent/15 text-accent text-xs flex items-center justify-center font-bold">2</span>
                              {scoringStage.title}
                            </h2>
                            <span
                              className={`text-xs font-bold px-2.5 py-0.5 rounded ${
                                isP0
                                  ? "bg-red-500/20 text-red-600 dark:text-red-400"
                                  : "bg-amber-500/20 text-amber-600 dark:text-amber-400"
                              }`}
                            >
                              {scoringStage.data.severity}
                            </span>
                          </div>

                          <div className="p-4 rounded-xl border border-line bg-paper space-y-2">
                            <div className="text-xs font-semibold uppercase tracking-wider text-muted">
                              {t("pipeline.triage_rationale", "Medical & Timeline Rationale")}
                            </div>
                            <div className="text-sm text-ink leading-relaxed">
                              {scoringStage.data.justification}
                            </div>
                          </div>

                          <div className="space-y-2.5">
                            <div className="text-xs font-semibold uppercase tracking-wider text-muted">
                              {t("pipeline.kitchen_safeguards", "Internal Kitchen Safeguards & HACCP Directives")}
                            </div>
                            <div className="space-y-1.5">
                              {scoringStage.data.kitchen_safeguards?.map((dir: string, i: number) => (
                                <div
                                  key={i}
                                  className="flex items-start gap-2.5 p-3 rounded-lg border border-line bg-paper text-sm text-ink"
                                >
                                  <span className="w-4 h-4 rounded-full bg-emerald-500/20 text-emerald-600 dark:text-emerald-400 text-xs flex items-center justify-center mt-0.5 flex-shrink-0">
                                    ✓
                                  </span>
                                  <span>{dir}</span>
                                </div>
                              ))}
                            </div>
                          </div>
                        </div>
                      )}

                      {/* Stage 3: Insurance Draft */}
                      {(activeStage === "insurance_draft" || !activeStage) && draftStage && (
                        <div className={`${CARD} p-6 space-y-4`} data-testid="stage-card-draft">
                          <div className="flex items-center justify-between">
                            <h2 className="text-base font-semibold text-ink flex items-center gap-2">
                              <span className="w-5 h-5 rounded-full bg-accent/15 text-accent text-xs flex items-center justify-center font-bold">3</span>
                              {draftStage.title}
                            </h2>
                            <span className="text-xs font-medium text-muted bg-paper px-2.5 py-1 rounded border border-line">
                              {draftStage.data.legal_standard || "§ 105 VVG"}
                            </span>
                          </div>

                          <div className="space-y-2">
                            <div className="flex items-center justify-between text-xs text-muted">
                              <span>{t("pipeline.draft_preview", "Formal Liability Correspondence Draft (Without Admission of Liability)")}</span>
                              <span>{t("pipeline.recipient", "Recipient")}: {draftStage.data.draft_recipient}</span>
                            </div>
                            <pre className="p-4 rounded-xl bg-paper border border-line text-xs font-sans text-ink whitespace-pre-wrap leading-relaxed max-h-72 overflow-y-auto hairline-scroll">
                              {draftStage.data.draft_body}
                            </pre>
                          </div>

                          <div className="p-3.5 rounded-xl bg-paper border border-line flex items-center justify-between gap-3">
                            <div className="flex items-center gap-3 min-w-0">
                              <div className="w-9 h-9 rounded-lg bg-red-500/10 text-red-600 dark:text-red-400 flex items-center justify-center flex-shrink-0">
                                <Icon name="file" size={18} />
                              </div>
                              <div className="min-w-0">
                                <div className="text-xs font-semibold text-ink truncate">
                                  {draftStage.data.claim_form_pdf}
                                </div>
                                <div className="text-[11px] text-muted">
                                  {t("pipeline.claim_form_desc", "Official Incident Claim Form (PDF Attachment)")}
                                </div>
                              </div>
                            </div>
                            <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2.5 py-1 rounded">
                              {t("pipeline.attached", "Attached")}
                            </span>
                          </div>
                        </div>
                      )}

                      {/* Stage 4: Human Gate */}
                      {(activeStage === "approval_gate" || !activeStage) && gateStage && (
                        <div className={`${CARD} p-6 space-y-4`} data-testid="stage-card-gate">
                          <div className="flex items-center justify-between">
                            <h2 className="text-base font-semibold text-ink flex items-center gap-2">
                              <span className="w-5 h-5 rounded-full bg-accent/15 text-accent text-xs flex items-center justify-center font-bold">4</span>
                              {gateStage.title}
                            </h2>
                            <span
                              className={`text-xs font-bold px-2.5 py-0.5 rounded ${
                                approvalStatus === "approved"
                                  ? "bg-emerald-500/20 text-emerald-600 dark:text-emerald-400"
                                  : approvalStatus === "rejected"
                                  ? "bg-red-500/20 text-red-600 dark:text-red-400"
                                  : "bg-amber-500/20 text-amber-600 dark:text-amber-400"
                              }`}
                            >
                              {approvalStatus === "approved"
                                ? t("pipeline.approved", "Approved by Human Supervisor")
                                : approvalStatus === "rejected"
                                ? t("pipeline.revision_requested", "Revision Requested")
                                : t("pipeline.pending_approval", "Pending Sign-off")}
                            </span>
                          </div>

                          <div className="p-4 rounded-xl bg-paper border border-line space-y-2">
                            <div className="text-xs font-semibold uppercase tracking-wider text-muted">
                              {t("pipeline.gate_policy", "Human-in-the-Loop Governance Policy")}
                            </div>
                            <div className="text-xs text-muted leading-relaxed">
                              {gateStage.data.gate_policy}
                            </div>
                          </div>

                          <div className="flex items-center justify-end gap-3 pt-2">
                            <button
                              onClick={handleReject}
                              disabled={approvalStatus === "rejected"}
                              className="px-4 py-2 rounded-lg border border-line bg-panel hover:bg-hover text-sm font-medium text-ink transition-colors disabled:opacity-50"
                              data-testid="pipeline-reject-btn"
                            >
                              {t("pipeline.request_changes", "Request Changes")}
                            </button>
                            <button
                              onClick={handleApprove}
                              disabled={approvalStatus === "approved" || approving}
                              className="px-5 py-2 rounded-lg bg-accent text-accent-contrast text-sm font-medium hover:opacity-90 transition-opacity disabled:opacity-50 shadow-xs"
                              data-testid="pipeline-approve-btn"
                            >
                              {approving
                                ? t("pipeline.approving", "Submitting...")
                                : approvalStatus === "approved"
                                ? t("pipeline.dispatched", "Approved & Ready")
                                : t("pipeline.approve_dispatch", "Approve & Dispatch Claim")}
                            </button>
                          </div>
                        </div>
                      )}
                    </>
                  ) : (
                    /* Generic Stage View for any other persona */
                    <div className="space-y-4">
                      {pipeline.stages
                        .filter((s) => !activeStage || s.stage_id === activeStage)
                        .map((st, i) => (
                          <div key={st.stage_id} className={`${CARD} p-6 space-y-3`}>
                            <div className="flex items-center justify-between">
                              <h2 className="text-base font-semibold text-ink flex items-center gap-2">
                                <span className="w-5 h-5 rounded-full bg-accent/15 text-accent text-xs flex items-center justify-center font-bold">{i + 1}</span>
                                {st.title}
                              </h2>
                              <span className="text-xs font-semibold px-2.5 py-0.5 rounded bg-line/50 text-muted">
                                {st.status}
                              </span>
                            </div>
                            {st.data && Object.keys(st.data).length > 0 && (
                              <dl className="grid grid-cols-1 md:grid-cols-2 gap-2" data-testid={`stage-data-${st.stage_id}`}>
                                {Object.entries(st.data).map(([key, value]) => (
                                  <div key={key} className="p-3 rounded-lg border border-line bg-paper min-w-0">
                                    <dt className="text-[11px] uppercase tracking-wide text-muted">{key.replace(/_/g, " ")}</dt>
                                    <dd className="mt-1 text-sm text-ink break-words">
                                      {typeof value === "string" ? value : JSON.stringify(value)}
                                    </dd>
                                  </div>
                                ))}
                              </dl>
                            )}
                            {st.description && (
                              <p className="text-xs text-muted">{st.description}</p>
                            )}
                          </div>
                        ))}
                    </div>
                  )}
                </>
              )}
            </>
          )}
        </div>
      </div>
    </main>
  );
}
