import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { ScheduledView } from "./ScheduledView";

vi.mock("../api", () => ({
  announceAutomationsChanged: vi.fn(),
  createAutomation: vi.fn(),
  deleteAutomation: vi.fn(),
  getAutomation: vi.fn(),
  getAutomations: vi.fn().mockResolvedValue([]),
  markAutomationSeen: vi.fn().mockResolvedValue({}),
  getPipelineDetails: vi.fn().mockResolvedValue({ ok: true, stages: [] }),
  updateAutomation: vi.fn(),
}));

vi.mock("./AutomationQuickstart", () => ({
  AutomationQuickstart: () => <div data-testid="automation-quickstart" />,
}));

vi.mock("./IntegrationsView", () => ({
  PanelHead: ({ title, sub }: { title: string; sub: string }) => (
    <header>
      <h1>{title}</h1>
      <p>{sub}</p>
    </header>
  ),
}));

afterEach(cleanup);

describe("ScheduledView empty state", () => {
  it("renders translated emphasis as a strong element, not literal markup", () => {
    const { container } = render(
      <ScheduledView onOpenRun={vi.fn()} onRunNow={vi.fn()} />,
    );

    expect(
      screen.getByText("+ New automation", { selector: "strong" }),
    ).toBeTruthy();
    expect(container.textContent).not.toContain("<strong>");
  });

  it("opens PipelineDetailView when clicking run for food-poisoning-triage automation", async () => {
    const api = await import("../api");
    vi.mocked(api.getAutomation).mockResolvedValue({
      task: {
        id: "auto-fp-1",
        title: "Food Poisoning Triage Daily",
        instructions: "Check complaints",
        agent: "gastro-worker",
        workspace: "/test/workspace",
        enabled: true,
      } as any,
      runs: [
        {
          run_id: "run-1",
          session_id: "sess-fp-1",
          started_at: 1720000000,
          status: "success",
          trigger: "schedule",
          artifacts: [],
        } as any,
      ],
    });

    const onOpenRun = vi.fn();
    const { container } = render(
      <ScheduledView onOpenRun={onOpenRun} onRunNow={vi.fn()} initialOpenId="auto-fp-1" />,
    );

    const { findByText } = screen;
    const runItem = await findByText(/success/);
    expect(runItem).toBeTruthy();

    const runDiv = container.querySelector(".sched-run");
    expect(runDiv).toBeTruthy();
    if (runDiv) {
      const { fireEvent } = await import("@testing-library/react");
      fireEvent.click(runDiv);
    }

    // onOpenRun should NOT be called directly; pipeline view should open instead
    expect(onOpenRun).not.toHaveBeenCalled();
    expect(await screen.findByTestId("pipeline-detail-view")).toBeTruthy();
  });
});
