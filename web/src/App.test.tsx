import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

vi.mock("./GraphCanvas", () => ({
  GraphCanvas: ({
    introStarted,
    onReady,
    onSelect,
  }: {
    introStarted: boolean;
    onReady: () => void;
    onSelect: (nodeId: string) => void;
  }) => (
    <section aria-label="동적 지식맵">
      <button type="button" onClick={() => onSelect("isolated")}>
        관계없는 node 선택
      </button>
      <button type="button" onClick={onReady}>
        그래프 준비 완료
      </button>
      {introStarted && <span>초기 확대 시작</span>}
    </section>
  ),
}));

describe("desktop exploration", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/?center=sk&range=90d");
    Object.defineProperty(window, "matchMedia", {
      configurable: true,
      value: () => ({ matches: false }),
    });
    HTMLDialogElement.prototype.showModal = function showModal() {
      this.setAttribute("open", "");
    };
    HTMLDialogElement.prototype.close = function close() {
      this.removeAttribute("open");
      this.dispatchEvent(new Event("close"));
    };
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("잘못된 URL 상태를 기본 중심과 최근 90일로 정규화한다", () => {
    window.history.replaceState({}, "", "/?center=missing&range=invalid");
    render(<App />);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "SK하이닉스",
    );
    expect(
      screen
        .getByRole("button", { name: "최근 90일" })
        .getAttribute("aria-pressed"),
    ).toBe("true");
    expect(window.location.search).toContain("center=sk");
  });

  it("검색 후보를 키보드로 선택하고 관계없는 node 상세를 연다", () => {
    render(<App />);
    const search = screen.getByRole("combobox");
    fireEvent.focus(search);
    fireEvent.change(search, { target: { value: "미연결" } });
    fireEvent.keyDown(search, { key: "Enter" });
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "미연결 공개 기술",
    );
    expect(screen.getByText("현재 공개된 Relation이 없습니다.")).toBeTruthy();
  });

  it("Evidence Trace를 같은 상세 패널에서 펼친다", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /Evidence Trace/ }));
    expect(screen.getByText("원문 인용")).toBeTruthy();
    expect(screen.getByText("데스크톱 핵심 탐색 fixture")).toBeTruthy();
  });

  it("시간 범위를 전체 1년으로 바꾸고 URL에 반영한다", () => {
    render(<App />);
    const yearButton = screen.getByRole("button", { name: "전체 1년" });
    fireEvent.click(yearButton);
    expect(yearButton.getAttribute("aria-pressed")).toBe("true");
    expect(window.location.search).toContain("range=1y");
    expect(
      screen.getByText("최근 1년 전체 관측 활동량을 표시합니다."),
    ).toBeTruthy();
  });

  it("외부 대상 후속 질문은 중심을 옮기고 자기 대상은 중심을 유지한다", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /SanDisk로 이동하기/ }));
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "SanDisk",
    );
    fireEvent.click(
      screen.getByRole("button", { name: /SK하이닉스로 이동하기/ }),
    );
    fireEvent.click(screen.getByRole("button", { name: "김천성" }));
    fireEvent.click(
      screen.getByRole("button", { name: /현재 근거를 더 확인하기/ }),
    );
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "김천성",
    );
    expect(
      screen.getByText(/추가 모델 호출은 실행하지 않았습니다/),
    ).toBeTruthy();
  });

  it("상세 패널에 후속 질문을 정확히 두 개 표시한다", () => {
    render(<App />);
    const section = screen.getByRole("heading", {
      name: "후속 질문",
    }).parentElement;
    expect(section).not.toBeNull();
    expect(within(section as HTMLElement).getAllByRole("button")).toHaveLength(
      2,
    );
  });

  it("최근 탐색 경로에서 이전 node로 돌아가면 이후 경로를 제거한다", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "관계없는 node 선택" }));

    const trail = screen.getByRole("navigation", { name: "최근 탐색 경로" });
    expect(within(trail).getAllByRole("listitem")).toHaveLength(2);
    expect(
      within(trail).getByText("미연결 공개 기술").getAttribute("aria-current"),
    ).toBe("page");

    fireEvent.click(
      within(trail).getByRole("button", {
        name: "탐색 경로에서 SK하이닉스 선택",
      }),
    );
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "SK하이닉스",
    );
    expect(within(trail).getAllByRole("listitem")).toHaveLength(1);
    expect(within(trail).queryByRole("button")).toBeNull();
  });

  it("최근 탐색 경로는 현재 node를 포함해 네 개까지만 유지한다", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: /SanDisk로 이동하기/ }));
    fireEvent.click(screen.getByRole("button", { name: "SK하이닉스" }));
    fireEvent.click(screen.getByRole("button", { name: "김천성" }));
    fireEvent.click(screen.getByRole("button", { name: "SK하이닉스" }));
    fireEvent.click(screen.getByRole("button", { name: "강욱성" }));

    const trail = screen.getByRole("navigation", { name: "최근 탐색 경로" });
    expect(within(trail).getAllByRole("listitem")).toHaveLength(4);
    expect(within(trail).getByText("강욱성").getAttribute("aria-current")).toBe(
      "page",
    );
  });

  it("인사이트 제목에서 상세 분석을 열고 닫은 뒤 focus를 복원한다", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("tab", { name: "인사이트" }));
    const trigger = screen.getByRole("button", {
      name: "HBF 표준화 참여가 AI 메모리 협상력을 넓힐 수 있다",
    });
    fireEvent.click(trigger);

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText("확인된 사실")).toBeTruthy();
    expect(within(dialog).getByText("종합 해석")).toBeTruthy();
    expect(within(dialog).getByText("해석 시 유의점")).toBeTruthy();

    fireEvent.click(within(dialog).getByRole("button", { name: "분석 닫기" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("인사이트가 없는 node에는 준비되지 않은 상태를 표시한다", () => {
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "관계없는 node 선택" }));
    fireEvent.click(screen.getByRole("tab", { name: "인사이트" }));
    expect(
      screen.getByText("이 node의 종합 분석 데모는 아직 준비되지 않았습니다."),
    ).toBeTruthy();
  });

  it("그래프가 준비되면 90, 95, 99를 거쳐 초기 확대를 시작한다", () => {
    vi.useFakeTimers();
    render(<App />);
    fireEvent.click(screen.getByRole("button", { name: "그래프 준비 완료" }));

    act(() => vi.advanceTimersByTime(1400));
    expect(screen.getByText("-- 90% --")).toBeTruthy();
    act(() => vi.advanceTimersByTime(120));
    expect(screen.getByText("-- 95% --")).toBeTruthy();
    act(() => vi.advanceTimersByTime(120));
    expect(screen.getByText("-- 99% --")).toBeTruthy();
    act(() => vi.advanceTimersByTime(360));
    expect(screen.queryByLabelText("지식맵 준비 중")).toBeNull();
    expect(screen.getByText("초기 확대 시작")).toBeTruthy();
  });
});
