import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

vi.mock("./GraphCanvas", () => ({
  GraphCanvas: ({
    view,
    onReady,
    onSelect,
    onTransitionComplete,
  }: {
    view: { centerId: string; nodes: { id: string }[] };
    onReady: () => void;
    onSelect: (nodeId: string) => void;
    onTransitionComplete: (nodeId: string) => void;
  }) => (
    <section aria-label="동적 지식맵">
      <span>{`요청 중심: ${view.centerId}`}</span>
      <button type="button" onClick={onReady}>
        그래프 준비 완료
      </button>
      <button
        type="button"
        onClick={() =>
          onSelect(
            view.nodes.find((node) => node.id !== view.centerId)?.id ??
              view.centerId,
          )
        }
      >
        다른 graph node 선택
      </button>
      <button type="button" onClick={() => onTransitionComplete(view.centerId)}>
        중심 전환 완료
      </button>
    </section>
  ),
}));

const names: Record<string, string> = {
  "9223372036854775807": "SK하이닉스",
  "9223372036854775806": "HBF",
  "9223372036854775805": "UCIe",
};

function exploration(centerId = "9223372036854775807") {
  const neighborId =
    centerId === "9223372036854775807"
      ? "9223372036854775806"
      : "9223372036854775807";
  return {
    center_node_id: centerId,
    context_text: `${names[centerId]} 중심의 공개 관계입니다.`,
    graph: {
      nodes: [
        {
          node_id: centerId,
          name: names[centerId],
          node_type: { code: "TECHNOLOGY", display_name: "기술" },
          tier: "CENTER",
          activity_evidence_group_count: 6,
        },
        {
          node_id: neighborId,
          name: names[neighborId],
          node_type: { code: "TECHNOLOGY", display_name: "기술" },
          tier: "DIRECT",
          activity_evidence_group_count: 3,
        },
      ],
      relations: [
        {
          relation_id: `relation-${centerId}`,
          source_node_id: centerId,
          target_node_id: neighborId,
          relation_type_display_name: "관련 기술",
          supporting_evidence_group_count: 3,
          has_conflict: false,
        },
      ],
    },
    recommendations: [
      {
        target_node: {
          node_id: neighborId,
          name: names[neighborId],
          node_type: { code: "TECHNOLOGY", display_name: "기술" },
        },
        reason_code: "DIRECT",
        via_node_id: null,
        supporting_evidence_group_count: 3,
      },
    ],
    followup_questions: [
      {
        slot: 1,
        question_text: `${names[neighborId]} 중심으로 보기`,
        target_node_id: neighborId,
      },
      {
        slot: 2,
        question_text: `${names[centerId]} 다시 보기`,
        target_node_id: centerId,
      },
    ],
  };
}

function response(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function searchResults(
  items = [
    {
      node_id: "9223372036854775806",
      name: "HBF",
      node_type: { code: "TECHNOLOGY", display_name: "기술" },
      match_reasons: ["EXACT_ALIAS", "FULL_TEXT"],
    },
    {
      node_id: "9223372036854775805",
      name: "UCIe",
      node_type: { code: "TECHNOLOGY", display_name: "기술" },
      match_reasons: ["FULL_TEXT"],
    },
  ],
) {
  return { items };
}

function searchInput(): HTMLInputElement {
  return screen.getByRole("combobox") as HTMLInputElement;
}

async function enterSearch(query: string) {
  fireEvent.change(searchInput(), { target: { value: query } });
  expect(screen.getByText("검색 결과를 불러오는 중입니다.")).toBeTruthy();
  await screen.findByRole("listbox");
}

const fetchMock = vi.fn();

describe("exploration API 화면", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_DEFAULT_CENTER_NODE_ID", "9223372036854775807");
    vi.stubGlobal("fetch", fetchMock);
    fetchMock.mockReset();
    fetchMock.mockImplementation(async (input: string) => {
      if (input.startsWith("/api/v1/nodes/search?")) {
        return response(searchResults());
      }
      const centerId = input.match(/exploration\/([^?]+)/)?.[1];
      return response(exploration(centerId));
    });
    window.history.replaceState({}, "", "/?range=90d");
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: () => ({ matches: true }),
    });
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("기본 중심을 한 번 요청하고 문자열 bigint ID 응답을 표시한다", async () => {
    render(<App />);
    expect(screen.getByLabelText("탐색 데이터 불러오는 중")).toBeTruthy();
    expect(
      await screen.findByRole("heading", { name: "SK하이닉스" }),
    ).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/v1/exploration/9223372036854775807?time_window=RECENT_90_DAYS",
    );
    expect(searchInput().disabled).toBe(false);
    expect(screen.queryByText("Evidence Trace")).toBeNull();
    expect(screen.queryByText("인사이트")).toBeNull();
  });

  it("graph node를 선택하면 aggregate 한 번으로 새 중심을 전환한다", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "SK하이닉스" });
    fireEvent.click(
      screen.getByRole("button", { name: "다른 graph node 선택" }),
    );
    await screen.findByText("요청 중심: 9223372036854775806");
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(screen.getByRole("heading", { name: "SK하이닉스" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "중심 전환 완료" }));
    expect(await screen.findByRole("heading", { name: "HBF" })).toBeTruthy();
  });

  it("추천과 후속 질문은 선택할 때마다 aggregate를 한 번 요청한다", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "SK하이닉스" });
    fireEvent.click(screen.getByRole("button", { name: /HBF.*확인된 관계/ }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    fireEvent.click(screen.getByRole("button", { name: "중심 전환 완료" }));
    await screen.findByRole("heading", { name: "HBF" });
    fireEvent.click(
      screen.getByRole("button", { name: "SK하이닉스 중심으로 보기" }),
    );
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(3));
  });

  it("시간 범위를 바꾸면 같은 중심의 1년 aggregate를 한 번 요청한다", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "SK하이닉스" });
    fireEvent.click(screen.getByRole("button", { name: "최근 1년" }));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(2));
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      "/api/v1/exploration/9223372036854775807?time_window=RECENT_1_YEAR",
    );
    await waitFor(() =>
      expect(
        screen
          .getByRole("button", { name: "최근 1년" })
          .getAttribute("aria-pressed"),
      ).toBe("true"),
    );
  });

  it("404를 재시도 불가 상태로 표시한다", async () => {
    fetchMock.mockResolvedValue(
      response({ error: { code: "NODE_NOT_FOUND", retryable: false } }, 404),
    );
    render(<App />);
    expect((await screen.findByRole("alert")).textContent).toContain(
      "요청한 node를 찾을 수 없습니다.",
    );
    expect(screen.queryByRole("button", { name: "다시 시도" })).toBeNull();
  });

  it("503 PUBLICATION_NOT_READY에서 재시도해 성공한다", async () => {
    fetchMock
      .mockResolvedValueOnce(
        response(
          { error: { code: "PUBLICATION_NOT_READY", retryable: true } },
          503,
        ),
      )
      .mockResolvedValueOnce(response(exploration()));
    render(<App />);
    expect((await screen.findByRole("alert")).textContent).toContain(
      "공개 데이터를 준비하고 있습니다.",
    );
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(
      await screen.findByRole("heading", { name: "SK하이닉스" }),
    ).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("network error에서 재시도해 성공한다", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("offline"));
    render(<App />);
    expect((await screen.findByRole("alert")).textContent).toContain(
      "탐색 데이터를 불러오지 못했습니다.",
    );
    fetchMock.mockResolvedValueOnce(response(exploration()));
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(
      await screen.findByRole("heading", { name: "SK하이닉스" }),
    ).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("성공 응답에 graph node가 없으면 empty 상태를 표시한다", async () => {
    const empty = exploration();
    empty.graph.nodes = [];
    empty.graph.relations = [];
    empty.recommendations = [];
    empty.followup_questions = [];
    fetchMock.mockResolvedValue(response(empty));
    render(<App />);
    expect(
      await screen.findByText("표시할 탐색 데이터가 없습니다."),
    ).toBeTruthy();
  });

  it("별칭 검색을 limit 5로 요청하고 응답 순서와 문자열 ID를 유지한다", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "SK하이닉스" });

    await enterSearch("HBF");

    const searchCall = fetchMock.mock.calls.find(([input]) =>
      input.startsWith("/api/v1/nodes/search?"),
    );
    expect(searchCall?.[0]).toBe("/api/v1/nodes/search?q=HBF&limit=5");
    const options = screen.getAllByRole("option");
    expect(options.map((option) => option.textContent)).toEqual([
      "HBF기술별칭 정확 일치 · 공개 지식 일치",
      "UCIe기술공개 지식 일치",
    ]);
    expect(searchInput().getAttribute("aria-activedescendant")).toContain(
      "9223372036854775806",
    );
    fireEvent.keyDown(searchInput(), { key: "Escape" });
    expect(screen.queryByRole("listbox")).toBeNull();
  });

  it("방향키와 Enter로 후보를 선택해 exploration을 한 번 요청한다", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "SK하이닉스" });
    await enterSearch("HBF");

    fireEvent.keyDown(searchInput(), { key: "ArrowDown" });
    expect(
      screen
        .getByRole("option", { name: /UCIe/ })
        .getAttribute("aria-selected"),
    ).toBe("true");
    fireEvent.keyDown(searchInput(), { key: "ArrowUp" });
    fireEvent.keyDown(searchInput(), { key: "Enter" });

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([input]) =>
          input.includes("/exploration/"),
        ),
      ).toHaveLength(2),
    );
    expect(searchInput().value).toBe("HBF");
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(fetchMock.mock.calls.at(-1)?.[0]).toContain(
      "/api/v1/exploration/9223372036854775806",
    );
  });

  it("마우스로 후보를 선택해 preferred name을 남기고 exploration을 한 번 요청한다", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "SK하이닉스" });
    await enterSearch("interconnect");

    fireEvent.click(screen.getByRole("option", { name: /UCIe/ }));

    await waitFor(() =>
      expect(
        fetchMock.mock.calls.filter(([input]) =>
          input.includes("/exploration/"),
        ),
      ).toHaveLength(2),
    );
    expect(searchInput().value).toBe("UCIe");
    expect(fetchMock.mock.calls.at(-1)?.[0]).toContain(
      "/api/v1/exploration/9223372036854775805",
    );
  });

  it("공백 검색은 요청하지 않고 결과를 지운다", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "SK하이닉스" });
    await enterSearch("HBF");
    const callsBeforeBlank = fetchMock.mock.calls.length;

    fireEvent.change(searchInput(), { target: { value: "   " } });

    expect(screen.queryByRole("listbox")).toBeNull();
    await new Promise((resolve) => window.setTimeout(resolve, 300));
    expect(fetchMock).toHaveBeenCalledTimes(callsBeforeBlank);
  });

  it("검색 빈 결과와 재시도 가능한 오류를 표시하고 다시 요청한다", async () => {
    let searchAttempt = 0;
    fetchMock.mockImplementation(async (input: string) => {
      if (!input.startsWith("/api/v1/nodes/search?")) {
        const centerId = input.match(/exploration\/([^?]+)/)?.[1];
        return response(exploration(centerId));
      }
      searchAttempt += 1;
      if (searchAttempt === 1) return response(searchResults([]));
      if (searchAttempt === 2) throw new TypeError("offline");
      return response(searchResults());
    });
    render(<App />);
    await screen.findByRole("heading", { name: "SK하이닉스" });

    fireEvent.change(searchInput(), { target: { value: "없음" } });
    expect(await screen.findByText("검색 결과가 없습니다.")).toBeTruthy();
    fireEvent.change(searchInput(), { target: { value: "HBF" } });
    expect(
      await screen.findByText("검색 결과를 불러오지 못했습니다."),
    ).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));
    expect(await screen.findByRole("listbox")).toBeTruthy();
    expect(searchAttempt).toBe(3);
  });

  it("늦게 도착한 이전 검색 응답이 최신 결과를 덮지 않는다", async () => {
    let resolveFirst: ((value: Response) => void) | undefined;
    let resolveSecond: ((value: Response) => void) | undefined;
    let searchAttempt = 0;
    fetchMock.mockImplementation((input: string) => {
      if (!input.startsWith("/api/v1/nodes/search?")) {
        const centerId = input.match(/exploration\/([^?]+)/)?.[1];
        return Promise.resolve(response(exploration(centerId)));
      }
      searchAttempt += 1;
      return new Promise<Response>((resolve) => {
        if (searchAttempt === 1) resolveFirst = resolve;
        else resolveSecond = resolve;
      });
    });
    render(<App />);
    await screen.findByRole("heading", { name: "SK하이닉스" });

    fireEvent.change(searchInput(), { target: { value: "old" } });
    await waitFor(() => expect(searchAttempt).toBe(1));
    fireEvent.change(searchInput(), { target: { value: "new" } });
    await waitFor(() => expect(searchAttempt).toBe(2));
    await act(async () => {
      resolveSecond?.(response(searchResults(searchResults().items.slice(1))));
    });
    expect(await screen.findByRole("option", { name: /UCIe/ })).toBeTruthy();

    await act(async () => {
      resolveFirst?.(
        response(searchResults(searchResults().items.slice(0, 1))),
      );
    });
    expect(screen.queryByRole("option", { name: /HBF/ })).toBeNull();
    expect(screen.getByRole("option", { name: /UCIe/ })).toBeTruthy();
  });
});
