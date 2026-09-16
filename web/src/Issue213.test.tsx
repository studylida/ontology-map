import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { ExplorationView } from "./data";
import { PanelEvidence } from "./PanelEvidence";
import { EvidenceDialog, RelationList } from "./RelationPanel";
import { TopicPanel } from "./TopicPanel";
import type { TopicExplorationView } from "./topicData";

const request = vi.fn();
const response = (body: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => body,
});

const center = {
  node_id: "1",
  name: "중심 회사",
  node_type: { code: "COMPANY", display_name: "회사" },
};
const technology = {
  node_id: "2",
  name: "HBF",
  node_type: { code: "TECHNOLOGY", display_name: "기술" },
};
const person = {
  node_id: "3",
  name: "연결 인물",
  node_type: { code: "PERSON", display_name: "사람" },
};

function relationConnection(
  id: string,
  other: typeof technology | typeof person,
  stance: "SUPPORT" | "DISPUTE",
) {
  return {
    kind: "RELATION",
    target_id: id,
    position: stance,
    label: `${center.name} · 관련 · ${other.name}`,
    relation: {
      relation_id: id,
      display_name: "관련",
      directionality: "DIRECTED",
      source_node: center,
      target_node: other,
      other_node: other,
      stance,
    },
  };
}

const claim = {
  claim_id: "10",
  claim_text: "계획 성격의 비교 근거",
  modality: "PLAN_OR_TARGET",
  knowledge_state: "EVIDENCE_VERIFIED",
  evidence_group_count: 2,
  as_of_at: "2026-09-15T00:00:00Z",
  role: "CONTRASTING_CLAIM",
  connections: [
    relationConnection("100", technology, "SUPPORT"),
    relationConnection("101", person, "DISPUTE"),
  ],
};

const relationRow = {
  source_node_id: "1",
  target_node_id: "2",
  directionality: "DIRECTED",
  relation_id: "100",
  relation_type_display_name: "관련",
  other_node: technology,
  supporting_evidence_group_count: 2,
  has_conflict: false,
};

const loadedGraph: ExplorationView = {
  centerId: "1",
  context: "",
  nodes: [
    {
      id: "1",
      name: center.name,
      kind: "회사",
      kindCode: "COMPANY",
      tier: "center",
      activityEvidenceGroupCount: 2,
    },
    {
      id: "2",
      name: technology.name,
      kind: "기술",
      kindCode: "TECHNOLOGY",
      tier: "direct",
      activityEvidenceGroupCount: 2,
    },
  ],
  relations: [
    {
      id: "100",
      source: "1",
      target: "2",
      label: "관련",
      directionality: "DIRECTED",
      evidenceGroupCount: 2,
      conflict: false,
      tier: "direct",
    },
  ],
  recommendations: [],
  followups: [],
};

beforeEach(() => {
  request.mockReset();
  vi.stubGlobal("fetch", request);
  Object.defineProperties(HTMLDialogElement.prototype, {
    showModal: {
      configurable: true,
      value: function (this: HTMLDialogElement) {
        this.setAttribute("open", "");
      },
    },
    close: {
      configurable: true,
      value: function (this: HTMLDialogElement) {
        this.removeAttribute("open");
      },
    },
  });
});

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  Reflect.deleteProperty(HTMLDialogElement.prototype, "showModal");
  Reflect.deleteProperty(HTMLDialogElement.prototype, "close");
});

describe("Issue #213 relation verification UX", () => {
  it("keeps Claim disclosure separate from multiple Relation and Node actions", async () => {
    request.mockImplementation(async (path: string) => {
      if (path.includes("/claims/10/evidence")) {
        return response({
          items: [
            {
              trace_id: "900",
              source: {
                title: "Claim 원문",
                publisher_name: "출처",
                published_at: "2026-09-10T00:00:00Z",
                published_precision: "DAY",
                canonical_url: "https://example.com/claim",
              },
              quote_text: "Claim 직접 근거",
              locator: { paragraph_number: 1, start_char: 0, end_char: 10 },
              period_role: "IN_WINDOW",
            },
          ],
          next_cursor: null,
        });
      }
      if (path.includes("/relations")) {
        return response({ items: [relationRow], next_cursor: null });
      }
      return response({ items: [claim], next_cursor: null });
    });
    const onEvidence = vi.fn();
    const onSelect = vi.fn();
    render(
      <PanelEvidence
        nodeId="1"
        nodeName={center.name}
        range="90d"
        onEvidence={onEvidence}
        onSelect={onSelect}
        loadedGraph={loadedGraph}
        hiddenKinds={[]}
      />,
    );

    const disclosure = await screen.findByRole("button", {
      name: /계획 성격의 비교 근거/,
    });
    expect(disclosure.textContent).toContain("비교 근거");
    expect(disclosure.textContent).toContain("계획·목표");
    expect(disclosure.textContent).not.toContain("충돌");
    expect(screen.getByText("지지")).toBeTruthy();
    expect(screen.getByText("반박")).toBeTruthy();
    const relationEvidenceButtons = screen.getAllByRole("button", {
      name: "관계 근거",
    });
    expect(relationEvidenceButtons).toHaveLength(2);
    const secondEvidenceButton = relationEvidenceButtons.at(1);
    if (!secondEvidenceButton)
      throw new Error("second relation evidence action missing");

    fireEvent.click(secondEvidenceButton);
    expect(onEvidence).toHaveBeenCalledWith(
      expect.objectContaining({ id: "101" }),
    );
    fireEvent.click(screen.getByRole("button", { name: /HBF · Node 보기/ }));
    expect(onSelect).toHaveBeenCalledWith("2");

    fireEvent.click(disclosure);
    await screen.findByText("Claim 직접 근거");
    const relationSubviewOpener = screen.getByRole("button", {
      name: "전체 관계 보기",
    });
    relationSubviewOpener.focus();
    fireEvent.click(relationSubviewOpener);
    expect(
      await screen.findByRole("heading", { name: "전체 관계" }),
    ).toBeTruthy();
    expect(screen.getByText("현재 지도에 포함됨")).toBeTruthy();
    fireEvent.click(
      screen.getByRole("button", { name: "주장과 근거로 돌아가기" }),
    );
    await waitFor(() =>
      expect(document.activeElement).toBe(relationSubviewOpener),
    );
    expect(screen.getByText("Claim 직접 근거")).toBeTruthy();
  });

  it("derives graph badges from loaded graph membership and type filters only", async () => {
    request.mockResolvedValue(
      response({ items: [relationRow], next_cursor: null }),
    );
    const { rerender } = render(
      <RelationList
        nodeId="1"
        nodeName={center.name}
        onEvidence={vi.fn()}
        loadedGraph={loadedGraph}
        hiddenKinds={[]}
      />,
    );
    expect(await screen.findByText("현재 지도에 포함됨")).toBeTruthy();

    rerender(
      <RelationList
        nodeId="1"
        nodeName={center.name}
        onEvidence={vi.fn()}
        loadedGraph={loadedGraph}
        hiddenKinds={["TECHNOLOGY"]}
      />,
    );
    expect(screen.getByText("지도 유형 필터로 숨김")).toBeTruthy();

    rerender(
      <RelationList
        nodeId="1"
        nodeName={center.name}
        onEvidence={vi.fn()}
        loadedGraph={{ ...loadedGraph, relations: [] }}
        hiddenKinds={[]}
      />,
    );
    expect(screen.queryByText("현재 지도에 포함됨")).toBeNull();
    expect(screen.queryByText("지도 유형 필터로 숨김")).toBeNull();
  });

  it("preserves source-to-target direction in incoming Relation Evidence actions", async () => {
    request.mockResolvedValue(
      response({
        items: [
          {
            ...relationRow,
            source_node_id: "2",
            target_node_id: "1",
          },
        ],
        next_cursor: null,
      }),
    );
    const onEvidence = vi.fn();
    render(
      <RelationList
        nodeId="1"
        nodeName={center.name}
        onEvidence={onEvidence}
      />,
    );

    fireEvent.click(
      await screen.findByRole("button", { name: "HBF 관계 근거 보기" }),
    );
    expect(onEvidence).toHaveBeenCalledWith({
      id: "100",
      label: "HBF · 관련 · 중심 회사",
    });
  });

  it("uses opaque Evidence item identity so same source and locator keeps separate Claim/stance items", async () => {
    const source = {
      title: "공유 출처",
      publisher_name: "공개 출처",
      published_at: "2026-09-01T00:00:00Z",
      published_precision: "DAY",
      canonical_url: "https://example.com/shared",
    };
    const locator = { paragraph_number: 1, start_char: 0, end_char: 5 };
    const consoleError = vi
      .spyOn(console, "error")
      .mockImplementation(() => undefined);
    request.mockResolvedValue(
      response({
        items: [
          {
            item_key: "opaque-support",
            claim_text: "서로 다른 지지 Claim",
            modality: "FACT",
            stance: "SUPPORT",
            source,
            quote_text: "같은 인용",
            locator,
          },
          {
            item_key: "opaque-dispute",
            claim_text: "서로 다른 반박 Claim",
            modality: "PREDICTION_OR_ESTIMATE",
            stance: "DISPUTE",
            source,
            quote_text: "같은 인용",
            locator,
          },
        ],
        trace_count: 2,
        next_cursor: null,
      }),
    );
    render(
      <EvidenceDialog
        selection={{ id: "100", label: "검토 관계" }}
        onClose={vi.fn()}
      />,
    );
    expect(await screen.findByText("서로 다른 지지 Claim")).toBeTruthy();
    expect(screen.getByText("서로 다른 반박 Claim")).toBeTruthy();
    expect(screen.getByText("지지 근거")).toBeTruthy();
    expect(screen.getByText("반박 근거")).toBeTruthy();
    expect(screen.getByText("예측·추정")).toBeTruthy();
    expect(
      consoleError.mock.calls.some((call) =>
        String(call[0]).includes("same key"),
      ),
    ).toBe(false);
  });

  it("opens the common HAS_TOPIC Evidence action without changing Topic center", async () => {
    request.mockResolvedValue(response({ items: [], next_cursor: null }));
    const topicView: TopicExplorationView = {
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
        {
          id: "1",
          name: center.name,
          kind: "회사",
          kindCode: "COMPANY",
          tier: "direct",
          activityEvidenceGroupCount: 3,
        },
      ],
      relations: [
        {
          id: "700",
          source: "1",
          target: "77",
          label: "주제 분류",
          directionality: "DIRECTED",
          evidenceGroupCount: 3,
          conflict: false,
          tier: "direct",
        },
      ],
      recommendations: [],
      followups: [],
      topic: { nodeId: "77", name: "반도체", isActive: false },
      totalPublicMembershipCount: 1,
    };
    const onEvidence = vi.fn();
    const onSelect = vi.fn();
    render(
      <TopicPanel
        view={topicView}
        timeRange="90d"
        onClose={vi.fn()}
        onSelect={onSelect}
        onSelectInsight={vi.fn()}
        onEvidence={onEvidence}
      />,
    );
    fireEvent.click(await screen.findByRole("button", { name: "관계 근거" }));
    expect(onEvidence).toHaveBeenCalledWith(
      expect.objectContaining({ id: "700" }),
    );
    expect(onSelect).not.toHaveBeenCalled();
  });
});
