import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { KnowledgeNode } from "./data";
import { TopicPanel } from "./TopicPanel";
import type { TopicExplorationView } from "./topicData";

function node(
  id: string,
  name: string,
  kind: string,
  kindCode: string,
  evidence: number,
): KnowledgeNode {
  return {
    id,
    name,
    kind,
    kindCode,
    tier: "direct",
    activityEvidenceGroupCount: evidence,
  };
}

function topicView(members: KnowledgeNode[]): TopicExplorationView {
  return {
    centerId: "77",
    context: "",
    nodes: [
      {
        id: "77",
        name: "반도체",
        kind: "주제",
        kindCode: "TOPIC",
        tier: "center",
        activityEvidenceGroupCount: 0,
      },
      ...members,
    ],
    relations: [],
    recommendations: [],
    followups: [],
    topic: { nodeId: "77", name: "반도체", isActive: true },
    totalPublicMembershipCount: members.length,
  };
}

function emptyReportResponse() {
  return new Response(JSON.stringify({ items: [] }), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("TopicPanel", () => {
  it("shows only the top three recent-evidence members as rich cards without evidence counts", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn<typeof fetch>()
        .mockImplementation(async () => emptyReportResponse()),
    );
    const view = topicView([
      node("1", "가 회사", "회사", "COMPANY", 8),
      node("2", "나 기술", "기술", "TECHNOLOGY", 6),
      node("3", "다 사람", "사람", "PERSON", 4),
      node("4", "라 회사", "회사", "COMPANY", 2),
      node("5", "마 기술", "기술", "TECHNOLOGY", 0),
    ]);

    render(
      <TopicPanel
        view={view}
        timeRange="90d"
        onClose={() => undefined}
        onSelect={() => undefined}
        onSelectInsight={() => undefined}
      />,
    );

    const richSection = screen.getByRole("heading", {
      name: "최근 근거가 많은 연결",
    }).parentElement;
    expect(richSection).not.toBeNull();
    const rich = within(richSection as HTMLElement);
    expect(rich.getByText("가 회사")).toBeTruthy();
    expect(rich.getByText("나 기술")).toBeTruthy();
    expect(rich.getByText("다 사람")).toBeTruthy();
    expect(rich.queryByText("라 회사")).toBeNull();
    expect(richSection?.textContent).not.toMatch(/근거\s*\d|\d+개/);

    const recentSection = screen.getByRole("heading", {
      name: "최근 근거가 있는 연결",
    }).parentElement;
    expect(
      within(recentSection as HTMLElement).getByText("라 회사"),
    ).toBeTruthy();
    expect(
      within(recentSection as HTMLElement).queryByText("가 회사"),
    ).toBeNull();

    const otherSection = screen.getByRole("heading", {
      name: "그 외 연결",
    }).parentElement;
    expect(
      within(otherSection as HTMLElement).getByText("마 기술"),
    ).toBeTruthy();
  });

  it("distinguishes no membership from no selected-period evidence", () => {
    const { rerender } = render(
      <TopicPanel
        view={topicView([])}
        timeRange="90d"
        onClose={() => undefined}
        onSelect={() => undefined}
        onSelectInsight={() => undefined}
      />,
    );
    expect(screen.getByText("아직 공개된 연결 대상이 없습니다.")).toBeTruthy();

    rerender(
      <TopicPanel
        view={topicView([node("5", "마 기술", "기술", "TECHNOLOGY", 0)])}
        timeRange="1y"
        onClose={() => undefined}
        onSelect={() => undefined}
        onSelectInsight={() => undefined}
      />,
    );
    expect(
      screen.getByText("최근 1년에 새로 확인된 연결 근거가 없습니다."),
    ).toBeTruthy();
    expect(screen.getByText("마 기술")).toBeTruthy();
  });

  it("uses an available public report title to enter the member Insight tab", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [
            {
              report_id: "501",
              title: "반도체 공급망 변화",
              summary: "요약",
              as_of_at: "2026-09-15T00:00:00Z",
              evidence_group_count: 3,
              conclusion: null,
              caveat: null,
              sections: [],
            },
          ],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const onSelectInsight = vi.fn();

    render(
      <TopicPanel
        view={topicView([node("1", "가 회사", "회사", "COMPANY", 8)])}
        timeRange="90d"
        onClose={() => undefined}
        onSelect={() => undefined}
        onSelectInsight={onSelectInsight}
      />,
    );

    const title = await screen.findByRole("button", {
      name: /반도체 공급망 변화/,
    });
    fireEvent.click(title);
    expect(onSelectInsight).toHaveBeenCalledWith("1");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/v1/nodes/1/insight-report?time_window=RECENT_90_DAYS&detail=false",
      expect.any(Object),
    );
  });
});
