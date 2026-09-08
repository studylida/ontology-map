import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { DetailPanel } from "./DetailPanel";
import { type ExplorationView, fetchInsight } from "./data";

const request = vi.fn();
const list = {
  items: [
    {
      insight_id: "11",
      slot: 1,
      title: "저장된 분석",
      evidence_group_count: 1,
    },
  ],
};
const report = {
  ...list.items[0],
  summary: "분석 개요",
  synthesis: "근거를 종합한 해석",
  caveat: "해석의 한계",
  claims: [1, 2].map((id) => ({
    claim_id: String(id),
    claim_text: `근거 문장 ${id}`,
    role: id === 1 ? "KEY_CLAIM" : "SUPPORTING_CLAIM",
    traces: [
      {
        source: {
          title: "발표 자료",
          publisher_name: "발표자",
          published_at: null,
          published_precision: "UNKNOWN",
          canonical_url: "https://example.com/source",
        },
        quote_text: `인용문 ${id}`,
        locator: { paragraph_number: null, start_char: 0, end_char: 5 },
      },
    ],
  })),
};
const view: ExplorationView = {
  centerId: "1",
  context: "맥락",
  nodes: [
    {
      id: "1",
      name: "중심",
      kind: "기술",
      kindCode: "TECHNOLOGY",
      tier: "center",
      activityEvidenceGroupCount: 1,
    },
  ],
  relations: [],
  recommendations: [],
  followups: [],
};
const props = {
  view,
  timeRange: "90d" as const,
  onClose: vi.fn(),
  onSelect: vi.fn(),
  onEvidence: vi.fn(),
  onFollowup: vi.fn(),
};

beforeEach(() => {
  request.mockImplementation(async (path: string) => ({
    ok: true,
    status: 200,
    json: async () => (path.includes("/nodes/") ? list : report),
  }));
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
  request.mockReset();
  Reflect.deleteProperty(HTMLDialogElement.prototype, "showModal");
  Reflect.deleteProperty(HTMLDialogElement.prototype, "close");
});

it("키보드 tab 이동 뒤 저장 분석을 열고 근거를 함께 펼치며 panel 상태와 focus를 복원한다", async () => {
  render(<DetailPanel {...props} />);
  expect(request).not.toHaveBeenCalled();
  fireEvent.keyDown(screen.getByRole("tab", { name: "탐색" }), {
    key: "ArrowLeft",
  });
  expect(document.activeElement).toBe(
    screen.getByRole("tab", { name: "인사이트" }),
  );
  const opener = await screen.findByRole("button", { name: /저장된 분석/ });
  expect(request).toHaveBeenCalledTimes(1);
  opener.focus();
  fireEvent.click(opener);
  await screen.findByText("근거를 종합한 해석");
  fireEvent.click(screen.getByRole("button", { name: /근거 문장 1.*펼치기/ }));
  fireEvent.click(screen.getByRole("button", { name: /근거 문장 2.*펼치기/ }));
  expect(
    screen.getAllByRole("link", { name: "발표 자료 원문 열기" }),
  ).toHaveLength(2);
  fireEvent.click(screen.getByRole("button", { name: "모두 접기" }));
  expect(screen.queryAllByRole("link")).toHaveLength(0);
  fireEvent(screen.getByRole("dialog"), new Event("cancel", { bubbles: true }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.activeElement).toBe(opener);
  expect(
    screen.getByRole("tab", { name: "인사이트" }).getAttribute("aria-selected"),
  ).toBe("true");
  expect(request).toHaveBeenCalledTimes(2);
});

it("준비 실패를 재시도하고 기간 변경 시 이전 상세를 닫는다", async () => {
  request.mockResolvedValueOnce({
    ok: false,
    status: 503,
    json: async () => ({
      error: { code: "PUBLICATION_NOT_READY", retryable: true },
    }),
  });
  const { rerender } = render(<DetailPanel {...props} />);
  fireEvent.click(screen.getByRole("tab", { name: "인사이트" }));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
  fireEvent.click(await screen.findByRole("button", { name: /저장된 분석/ }));
  await screen.findByText("해석의 한계");
  rerender(<DetailPanel {...props} timeRange="1y" />);
  expect(screen.queryByRole("dialog")).toBeNull();
  await waitFor(() =>
    expect(request.mock.calls.at(-1)?.[0]).toContain("RECENT_1_YEAR"),
  );
});

it("안전하지 않은 원문 URL이 있는 상세를 거부한다", async () => {
  const malformed = structuredClone(report);
  for (const claim of malformed.claims)
    for (const trace of claim.traces)
      trace.source.canonical_url = "javascript:alert(1)";
  request.mockResolvedValueOnce({
    ok: true,
    status: 200,
    json: async () => malformed,
  });
  await expect(
    fetchInsight("11", null, new AbortController().signal),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
});
