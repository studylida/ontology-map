import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { useState } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { type EvidenceTrace, fetchRelationEvidence } from "./data";
import {
  EvidenceDialog,
  type EvidenceSelection,
  publicationLabel,
  RelationList,
} from "./RelationPanel";

const request = vi.fn();
const response = (body: unknown, status = 200) => ({
  ok: status < 400,
  status,
  json: async () => body,
});
const relation = {
  source_node_id: "1",
  target_node_id: "2",
  directionality: "DIRECTED",
  relation_id: "9223372036854775807",
  relation_type_display_name: "관련 기술",
  other_node: {
    node_id: "2",
    name: "HBF",
    node_type: { code: "TECHNOLOGY", display_name: "기술" },
  },
  supporting_evidence_group_count: 3,
  has_conflict: false,
};
const trace = {
  claim_text: "확인한 기술 관계",
  stance: "SUPPORT",
  source: {
    title: "발표 자료",
    publisher_name: "공개 출처",
    published_at: "2026-08-01T00:00:00Z",
    published_precision: "MONTH",
    canonical_url: "https://example.com/source",
  },
  quote_text: "원문 인용",
  locator: { paragraph_number: null, start_char: 0, end_char: 5 },
};

beforeEach(() => {
  request.mockReset();
  vi.stubGlobal("fetch", request);
  // jsdom에는 native dialog 메서드가 없어 열림 상태만 흉내 낸다. 실제 focus trap은 브라우저에서 검증한다.
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
  Reflect.deleteProperty(HTMLDialogElement.prototype, "showModal");
  Reflect.deleteProperty(HTMLDialogElement.prototype, "close");
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

function Flow() {
  const [selection, setSelection] = useState<EvidenceSelection | null>(null);
  return (
    <>
      <RelationList
        nodeId="1"
        nodeName="SK하이닉스"
        onEvidence={setSelection}
      />
      {selection && (
        <EvidenceDialog
          key={selection.id}
          selection={selection}
          onClose={() => setSelection(null)}
        />
      )}
    </>
  );
}

it("Relation 선택 때만 공용 근거 창을 열고 cursor를 그대로 전달하며 닫은 뒤 focus를 복귀한다", async () => {
  request.mockImplementation(async (path: string) => {
    if (path.includes("/nodes/"))
      return response({ items: [relation], next_cursor: null });
    return response({
      items: path.includes("cursor=") ? [] : [trace],
      next_cursor: path.includes("cursor=") ? null : "opaque +/?",
      trace_count: 1,
    });
  });
  render(<Flow />);
  const opener = await screen.findByRole("button", { name: /HBF.*근거 보기/ });
  expect(request).toHaveBeenCalledTimes(1);
  opener.focus();
  fireEvent.click(opener);
  await screen.findByText("원문 인용");
  expect(screen.getByRole("dialog").getAttribute("open")).toBe("");
  expect(screen.getByText("공개 출처 · 2026-08")).toBeTruthy();
  expect(screen.queryByText("9223372036854775807")).toBeNull();
  expect(
    screen
      .getByRole("link", { name: "발표 자료 원문 열기" })
      .getAttribute("href"),
  ).toBe("https://example.com/source");
  fireEvent.click(screen.getByRole("button", { name: "근거 더 보기" }));
  await waitFor(() => expect(request).toHaveBeenCalledTimes(3));
  expect(
    new URL(request.mock.calls[2]?.[0], "https://example.com").searchParams.get(
      "cursor",
    ),
  ).toBe("opaque +/?");
  fireEvent.click(screen.getByRole("button", { name: "근거 창 닫기" }));
  expect(screen.queryByRole("dialog")).toBeNull();
  expect(document.activeElement).toBe(opener);
});

it.each([404, 422, 503, 0])(
  "오류 %s를 빈 결과와 구분하고 retry 정책을 따른다",
  async (status) => {
    if (status === 0) request.mockRejectedValueOnce(new TypeError("offline"));
    else
      request.mockResolvedValueOnce(
        response(
          { error: { code: "REQUEST_FAILED", retryable: status === 503 } },
          status,
        ),
      );
    request.mockResolvedValue(
      response({ items: [relation], next_cursor: null }),
    );
    render(<Flow />);
    await screen.findByRole("alert");
    expect(screen.queryByText("현재 공개된 자료가 없습니다.")).toBeNull();
    if (status === 503 || status === 0) {
      fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
      expect(
        await screen.findByRole("button", { name: /HBF.*근거 보기/ }),
      ).toBeTruthy();
    } else
      expect(screen.queryByRole("button", { name: "다시 시도" })).toBeNull();
  },
);

it("중심이 바뀌면 진행 중 요청을 취소하고 이전 결과를 표시하지 않는다", async () => {
  let finish: (value: unknown) => void = () => {};
  request.mockImplementationOnce(
    () =>
      new Promise((resolve) => {
        finish = resolve;
      }),
  );
  request.mockResolvedValue(response({ items: [], next_cursor: null }));
  const props = { nodeName: "중심", onEvidence: vi.fn() };
  const { rerender } = render(<RelationList key="1" nodeId="1" {...props} />);
  const signal = request.mock.calls[0]?.[1]?.signal as AbortSignal;
  rerender(<RelationList key="2" nodeId="2" {...props} />);
  await screen.findByText("현재 공개된 자료가 없습니다.");
  expect(signal.aborted).toBe(true);
  await act(async () =>
    finish(response({ items: [relation], next_cursor: null })),
  );
  expect(screen.queryByRole("button", { name: /HBF.*근거 보기/ })).toBeNull();
});

it("근거 URL의 실행 가능한 scheme을 거부하고 날짜 정밀도를 확대하지 않는다", async () => {
  request.mockResolvedValue(
    response({
      items: [
        {
          ...trace,
          source: { ...trace.source, canonical_url: "javascript:alert(1)" },
        },
      ],
      next_cursor: null,
    }),
  );
  await expect(
    fetchRelationEvidence("1", null, new AbortController().signal),
  ).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  const value = {
    publishedAt: "2026-08-01T00:00:00Z",
    precision: "YEAR",
  } as EvidenceTrace;
  expect(publicationLabel(value)).toBe("2026");
  expect(publicationLabel({ ...value, publishedAt: null })).toBe(
    "발행 시점 미상",
  );
});
