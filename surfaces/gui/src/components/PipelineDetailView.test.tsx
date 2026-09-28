import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PipelineDetailView } from "./PipelineDetailView";
import * as api from "../api";

vi.mock("../api", async () => {
  const actual = await vi.importActual("../api");
  return {
    ...actual,
    getPipelineDetails: vi.fn(),
  };
});

afterEach(cleanup);

const mockPipeline = {
  ok: true,
  session_id: "fp-test-123",
  persona_id: "gastro-worker",
  title: "Food Poisoning & Claims Triage: Case Weber",
  status: "completed",
  stages: [
    {
      stage_id: "intake",
      title: "Intake & Evidence Extraction",
      status: "completed",
      data: {
        case_id: "FP-2026-09-08-WEBER",
        guest_name: "Dr. Maximilian Weber",
        visit_time: "08.09.2026 19:45 Uhr",
        dishes: "Rindertatar mit Trüffelmayo, Frische Austern Fine de Claire",
        incubation_time: "4,0 Stunden",
        symptoms: "Hohes Fieber (39,5°C), unstillbares Erbrechen",
        evidence_files: ["complaint_weber_20260908.txt"],
      },
    },
    {
      stage_id: "severity_scoring",
      title: "Incident Triage & Risk Scoring",
      status: "completed",
      data: {
        severity: "P0-CRITICAL",
        badge_color: "danger",
        justification: "Stationäre Hospitalisierung / Notarzteinsatz bei 2 Gästen.",
        kitchen_safeguards: [
          "Rückstellproben der Charge versiegeln und tiefkühlen (-18°C)",
          "HACCP-Kühldokumentation und Wareneingangstemperaturen sichern",
        ],
      },
    },
    {
      stage_id: "insurance_draft",
      title: "Insurance Draft (§ 105 VVG) & Form",
      status: "completed",
      data: {
        legal_standard: "§ 105 VVG (Kein Schuldanerkenntnis)",
        draft_recipient: "Dr. Maximilian Weber",
        draft_body: "Sehr geehrter Herr Dr. Weber, wir haben Ihre Mitteilung mit großem Bedauern zur Kenntnis genommen.",
        claim_form_pdf: "schadenanzeige_lebensmittelvergiftung.pdf",
        pdf_attached: true,
      },
    },
    {
      stage_id: "approval_gate",
      title: "Human-in-the-Loop Approval Gate",
      status: "completed",
      data: {
        gate_policy: "Hard Floor: Outbound communication requires explicit human supervisor sign-off",
        decision: "approved",
        reviewed_by: "Supervisor",
        can_approve: true,
      },
    },
  ],
};

describe("PipelineDetailView", () => {
  it("renders pipeline details and 4 stages correctly", async () => {
    vi.mocked(api.getPipelineDetails).mockResolvedValue(mockPipeline as any);
    const onBack = vi.fn();
    const onOpenChat = vi.fn();

    render(
      <PipelineDetailView
        sessionId="fp-test-123"
        onBack={onBack}
        onOpenChat={onOpenChat}
      />,
    );

    expect(screen.getByText(/Loading pipeline details/i)).toBeTruthy();

    await waitFor(() => {
      expect(screen.getByTestId("pipeline-detail-view")).toBeTruthy();
    });

    // Check title and badges
    expect(screen.getByText("Food Poisoning & Claims Triage: Case Weber")).toBeTruthy();
    expect(screen.getByTestId("pipeline-severity-badge").textContent).toContain("P0-CRITICAL");

    // Check Stage 1 content
    expect(screen.getByText("Dr. Maximilian Weber")).toBeTruthy();
    expect(screen.getByText("08.09.2026 19:45 Uhr")).toBeTruthy();

    // Check click to Stage 2
    fireEvent.click(screen.getByTestId("stage-tab-severity_scoring"));
    expect(screen.getByTestId("stage-card-scoring")).toBeTruthy();
    expect(screen.getByText(/Stationäre Hospitalisierung/i)).toBeTruthy();
    expect(screen.getByText(/Rückstellproben der Charge versiegeln/i)).toBeTruthy();

    // Check click to Stage 3
    fireEvent.click(screen.getByTestId("stage-tab-insurance_draft"));
    expect(screen.getByTestId("stage-card-draft")).toBeTruthy();
    expect(screen.getByText("schadenanzeige_lebensmittelvergiftung.pdf")).toBeTruthy();

    // Check click to Stage 4
    fireEvent.click(screen.getByTestId("stage-tab-approval_gate"));
    expect(screen.getByTestId("stage-card-gate")).toBeTruthy();

    // Check Back button
    fireEvent.click(screen.getByTestId("pipeline-back-btn"));
    expect(onBack).toHaveBeenCalledTimes(1);

    // Check View Chat Log button
    fireEvent.click(screen.getByTestId("pipeline-open-chat-btn"));
    expect(onOpenChat).toHaveBeenCalledWith("fp-test-123");
  });

  it("supports switching to Execution Graph mode and inspecting node inputs and outputs", async () => {
    const pipelineWithNodes = {
      ...mockPipeline,
      nodes: [
        {
          node_id: "node-trigger",
          type: "trigger",
          title: "Trigger: Scheduled Run",
          status: "completed",
          description: "Cron execution started",
        },
        {
          node_id: "node-tool-1",
          type: "tool",
          title: "Tool: read_file",
          status: "completed",
          tool_name: "read_file",
          inputs: { path: "complaint_weber_20260908.txt" },
          outputs: { content: "Sample guest complaint text" },
          duration_ms: 120,
        },
      ],
    };
    vi.mocked(api.getPipelineDetails).mockResolvedValue(pipelineWithNodes as any);

    render(
      <PipelineDetailView
        sessionId="fp-test-123"
        onBack={vi.fn()}
        onOpenChat={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("toggle-nodes-view")).toBeTruthy();
    });

    // Switch to Graph mode
    fireEvent.click(screen.getByTestId("toggle-nodes-view"));

    expect(screen.getByTestId("pipeline-nodes-container")).toBeTruthy();
    expect(screen.getByTestId("node-card-node-trigger")).toBeTruthy();
    expect(screen.getByTestId("node-card-node-tool-1")).toBeTruthy();

    // Toggle inspect tool node to view input / output payload
    fireEvent.click(screen.getByTestId("toggle-node-node-tool-1"));
    expect(screen.getByText(/complaint_weber_20260908\.txt/)).toBeTruthy();
  });

  it("renders generic pipeline correctly when stages are empty", async () => {
    const genericPipeline = {
      ok: true,
      session_id: "generic-run-456",
      persona_id: "code-audit",
      pipeline_type: "trace_driven",
      title: "Code Audit Automation Run",
      status: "completed",
      stages: [],
      nodes: [
        {
          node_id: "node-script-1",
          type: "script",
          title: "Script: run_command",
          status: "completed",
          tool_name: "run_command",
          inputs: { command: "pytest" },
          outputs: { returncode: 0 },
        },
      ],
    };
    vi.mocked(api.getPipelineDetails).mockResolvedValue(genericPipeline as any);

    render(
      <PipelineDetailView
        sessionId="generic-run-456"
        onBack={vi.fn()}
        onOpenChat={vi.fn()}
      />,
    );

    await waitFor(() => {
      expect(screen.getByTestId("pipeline-nodes-container")).toBeTruthy();
    });

    expect(screen.getByTestId("node-card-node-script-1")).toBeTruthy();
  });

  it("renders GastroWorker physical-document stages as document data", async () => {
    vi.mocked(api.getPipelineDetails).mockResolvedValue({
      ok: true,
      session_id: "doc-vision-01",
      persona_id: "gastro-worker",
      workflow: "physical_document_processing",
      pipeline_type: "schema",
      title: "Process invoice 101",
      status: "waiting_approval",
      stages: [
        {
          stage_id: "document_intake",
          title: "Document Intake & Quality Check",
          status: "completed",
          data: { document_id: "DOC-2026-000101", source_file: "invoice-101.jpg" },
        },
        {
          stage_id: "vision_analysis",
          title: "Native Vision Classification & Extraction",
          status: "completed",
          data: {
            document_type: "sales_invoice",
            validation: "subtotal + tax equals total",
            ocr_used_as_primary: false,
          },
        },
        {
          stage_id: "human_gate",
          title: "Human Approval Gate",
          status: "waiting_approval",
          data: { decision: "pending" },
        },
      ],
    } as any);

    render(
      <PipelineDetailView
        sessionId="doc-vision-01"
        onBack={vi.fn()}
        onOpenChat={vi.fn()}
      />,
    );

    await waitFor(() => expect(screen.getByText("DOC-2026-000101")).toBeTruthy());
    expect(screen.queryByTestId("pipeline-severity-badge")).toBeNull();

    fireEvent.click(screen.getByTestId("stage-tab-vision_analysis"));
    expect(screen.getByTestId("stage-data-vision_analysis").textContent).toContain("sales_invoice");
    expect(screen.getByTestId("stage-data-vision_analysis").textContent).toContain("false");

    fireEvent.click(screen.getByTestId("stage-tab-human_gate"));
    expect(screen.getByTestId("stage-data-human_gate").textContent).toContain("pending");
  });
});
