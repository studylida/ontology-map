import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { TopicPicker } from "./TopicPicker";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("TopicPicker", () => {
  it("loads a separate Korean-sorted Topic list and keeps inactive rows selectable", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          items: [
            {
              node_id: "9",
              topic_code: "INVESTMENT",
              canonical_display_name: "투자",
              is_active: false,
            },
            {
              node_id: "7",
              topic_code: "SEMICONDUCTOR",
              canonical_display_name: "반도체",
              is_active: true,
            },
          ],
        }),
        { status: 200, headers: { "content-type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    const onSelect = vi.fn();

    render(<TopicPicker onSelect={onSelect} />);
    fireEvent.click(screen.getByRole("button", { name: "주제" }));

    const list = await screen.findByRole("listbox", { name: "주제 목록" });
    const options = within(list).getAllByRole("option");
    expect(options.map((option) => option.textContent)).toEqual([
      "반도체",
      "투자신규 연결 중단",
    ]);

    fireEvent.click(options[1] as HTMLElement);
    expect(onSelect).toHaveBeenCalledWith("9");
    expect(fetchMock).toHaveBeenCalledWith("/api/v1/topics", expect.any(Object));
  });
});
