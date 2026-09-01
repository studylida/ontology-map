import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

vi.mock("./GraphCanvas", () => ({
  GraphCanvas: ({ onSelect }: { onSelect: (nodeId: string) => void }) => (
    <section aria-label="동적 지식맵">
      <button type="button" onClick={() => onSelect("isolated")}>
        관계없는 node 선택
      </button>
    </section>
  ),
}));

describe("desktop exploration", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", "/?center=sk&range=90d");
  });

  afterEach(() => cleanup());

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
});
