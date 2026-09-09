import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { DetailPanel } from "./DetailPanel";
import {
  type ExplorationView,
  fetchPanelTraces,
  type PanelClaim,
} from "./data";

const request = vi.fn();
const claim = (id: number) => ({
  claim_id: String(id),
  claim_text: `근거 문장 ${id}`,
  modality: "FACT",
  knowledge_state: "EVIDENCE_VERIFIED",
  evidence_group_count: 1,
  as_of_at: "2026-09-08T00:00:00Z",
  role: "KEY_CLAIM",
  connections: [],
});
const report = {
  report_id: "11",
  node_id: "1",
  title: "저장된 분석",
  summary: "분석 개요",
  as_of_at: "2026-09-08T00:00:00Z",
  time_window: "RECENT_90_DAYS",
  evidence_group_count: 2,
  conclusion: "종합 결론",
  caveat: "해석의 한계",
  sections: [
    {
      section_id: "21",
      title: "첫 번째 발견",
      synthesis: "근거를 종합한 해석",
      caveat: null,
      claims: [claim(1), claim(2)],
    },
  ],
};
const trace = {
  trace_id: "1",
  source: {
    title: "발표 자료",
    publisher_name: "발표자",
    published_at: null,
    published_precision: "UNKNOWN",
    canonical_url: "https://example.com/source",
  },
  quote_text: "인용문",
  locator: { paragraph_number: null, start_char: 0, end_char: 5 },
  period_role: "UNKNOWN",
};
const questions = {
  items: [{ question_id: "31", question_text: "이 노드를 이해하려면?" }],
  next_cursor: null,
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
};
function result(path: string) {
  if (path.includes("/insight-report"))
    return { items: [report], next_cursor: null };
  if (path.includes("/evidence?")) return { items: [trace], next_cursor: null };
  if (path.includes("/questions/31"))
    return {
      ...questions.items[0],
      answer: "질문의 짧은 답변",
      caveat: null,
      node_id: "1",
      time_window: "RECENT_90_DAYS",
      as_of_at: report.as_of_at,
      section_id: "21",
      claims: [claim(1)],
    };
  return questions;
}
beforeEach(() => {
  request.mockImplementation(async (path: string) => ({
    ok: true,
    status: 200,
    json: async () => result(path),
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
  props.onSelect.mockReset();
  Reflect.deleteProperty(HTMLDialogElement.prototype, "showModal");
  Reflect.deleteProperty(HTMLDialogElement.prototype, "close");
});

it("목차에서 보고서를 열고 복수 근거를 비교한 뒤 원래 초점으로 돌아온다", async () => {
  render(<DetailPanel {...props} />);
  fireEvent.keyDown(screen.getByRole("tab", { name: "탐색" }), {
    key: "ArrowLeft",
  });
  expect(document.activeElement).toBe(
    screen.getByRole("tab", { name: "인사이트" }),
  );
  const opener = await screen.findByRole("button", { name: /첫 번째 발견/ });
  opener.focus();
  fireEvent.click(opener);
  await screen.findByText("근거를 종합한 해석");
  expect(
    [...screen.getByRole("dialog").querySelectorAll("h4")].map(
      (heading) => heading.textContent,
    ),
  ).toEqual(["해석과 판단", "이 해석의 근거"]);
  fireEvent.click(screen.getByRole("button", { name: /근거 문장 1/ }));
  fireEvent.click(screen.getByRole("button", { name: /근거 문장 2/ }));
  await waitFor(() =>
    expect(
      screen.getAllByRole("link", { name: "발표 자료 원문 열기" }),
    ).toHaveLength(2),
  );
  fireEvent.click(screen.getByRole("button", { name: "모두 접기" }));
  expect(
    screen.queryAllByRole("link", { name: "발표 자료 원문 열기" }),
  ).toHaveLength(0);
  fireEvent(screen.getByRole("dialog"), new Event("cancel", { bubbles: true }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.activeElement).toBe(opener);
  fireEvent.click(opener);
  await screen.findByText("근거를 종합한 해석");
  const dialog = screen.getByRole("dialog");
  vi.spyOn(dialog, "getBoundingClientRect").mockReturnValue(
    new DOMRect(100, 100, 400, 300),
  );
  fireEvent.click(dialog, { clientX: 150, clientY: 150 });
  expect(screen.getByRole("dialog")).toBe(dialog);
  fireEvent.click(dialog, { clientX: 90, clientY: 150 });
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.activeElement).toBe(opener);
});

it("질문은 답변만 펼치며 연결된 보고서 절도 중심을 바꾸지 않는다", async () => {
  render(<DetailPanel {...props} />);
  const question = await screen.findByRole("button", {
    name: "이 노드를 이해하려면?",
  });
  fireEvent.click(question);
  await screen.findByText("질문의 짧은 답변");
  fireEvent.click(screen.getByRole("button", { name: "관련 분석 읽기" }));
  await screen.findByText("근거를 종합한 해석");
  expect(props.onSelect).not.toHaveBeenCalled();
  expect(
    request.mock.calls.every(([path]) => !path.includes("/exploration/")),
  ).toBe(true);
});

it("준비 실패를 재시도하고 기간 변경 시 이전 상세와 요청을 초기화한다", async () => {
  const { rerender } = render(<DetailPanel {...props} />);
  await screen.findByRole("button", { name: /이 노드를 이해하려면/ });
  request.mockResolvedValueOnce({
    ok: false,
    status: 503,
    json: async () => ({ error: { code: "PANEL_NOT_READY", retryable: true } }),
  });
  fireEvent.click(screen.getByRole("tab", { name: "인사이트" }));
  await screen.findByRole("alert");
  fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
  fireEvent.click(await screen.findByRole("button", { name: /첫 번째 발견/ }));
  await screen.findByText("해석의 한계");
  rerender(<DetailPanel {...props} timeRange="1y" />);
  expect(screen.queryByRole("dialog")).toBeNull();
  await waitFor(() =>
    expect(request.mock.calls.at(-1)?.[0]).toContain("RECENT_1_YEAR"),
  );
});

it("안전하지 않은 원문 URL은 표시 전에 거부한다", async () => {
  const malformed = structuredClone(trace);
  malformed.source.canonical_url = "javascript:alert(1)";
  request.mockResolvedValueOnce({
    ok: true,
    status: 200,
    json: async () => ({ items: [malformed], next_cursor: null }),
  });
  const basis: PanelClaim = {
    id: "1",
    text: "근거",
    modality: "FACT",
    state: "EVIDENCE_VERIFIED",
    evidenceGroupCount: 1,
    asOf: report.as_of_at,
    role: null,
    connections: [],
  };
  await expect(
    fetchPanelTraces("1", basis, "90d", null, new AbortController().signal),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
});
