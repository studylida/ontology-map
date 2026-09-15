from pathlib import Path


def replace(path: str, old: str, new: str, count: int = -1) -> None:
    file = Path(path)
    text = file.read_text()
    if new in text:
        return
    if old not in text:
        raise SystemExit(f"missing test marker in {path}: {old[:80]!r}")
    file.write_text(text.replace(old, new, count))


# Existing regressions now assert the approved #208 copy while preserving the tests.
replace(
    "web/src/App.test.tsx",
    '"요청한 node를 찾을 수 없습니다.",',
    '"요청한 Node를 찾을 수 없습니다.",',
)
replace(
    "web/src/App.test.tsx",
    '"공개 데이터를 준비하고 있습니다.",',
    '"현재 이 Node의 공개 탐색 자료를 불러올 수 없습니다.",',
)
# Only the exploration retry tests change button copy; NodeSearch owns a separate existing retry contract.
replace(
    "web/src/App.test.tsx",
    'fireEvent.click(screen.getByRole("button", { name: "다시 시도" }));\n    expect(\n      await screen.findByRole("heading", { name: "SK하이닉스" }),',
    'fireEvent.click(screen.getByRole("button", { name: "다시 조회" }));\n    expect(\n      await screen.findByRole("heading", { name: "SK하이닉스" }),',
    2,
)
replace(
    "web/src/App.test.tsx",
    'expect(screen.queryByRole("button", { name: "다시 시도" })).toBeNull();',
    'expect(screen.queryByRole("button", { name: "다시 조회" })).toBeNull();\n    expect(\n      screen.queryByRole("button", { name: "기본 탐색으로 이동" }),\n    ).toBeNull();',
    1,
)
replace(
    "web/src/RelationPanel.test.tsx",
    'screen.getByRole("button", { name: "다시 시도" })',
    'screen.getByRole("button", { name: "다시 조회" })',
)
replace(
    "web/src/RelationPanel.test.tsx",
    'screen.queryByRole("button", { name: "다시 시도" })',
    'screen.queryByRole("button", { name: "다시 조회" })',
)
replace(
    "web/src/InsightPanel.test.tsx",
    'screen.getByRole("button", { name: "다시 시도" })',
    'screen.getByRole("button", { name: "다시 조회" })',
)

app_tests = r'''

  it("center가 없어도 오류가 아니며 Node 검색과 주제로 재진입할 수 있다", async () => {
    vi.stubEnv("VITE_DEFAULT_CENTER_NODE_ID", "");
    window.history.replaceState({}, "", "/?range=90d");
    render(<App />);
    expect(
      await screen.findByText("탐색할 Node를 검색하거나 주제를 선택해 주세요."),
    ).toBeTruthy();
    expect(searchInput().disabled).toBe(false);
    expect(screen.getByRole("button", { name: "주제 목록 열기" })).toBeTruthy();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("초기 INVALID_REQUEST는 retry 없는 요청 오류로 남고 재진입 동선을 유지한다", async () => {
    fetchMock.mockResolvedValue(
      response({ error: { code: "INVALID_REQUEST", retryable: false } }, 422),
    );
    render(<App />);
    expect((await screen.findByRole("alert")).textContent).toContain(
      "요청을 확인할 수 없습니다. 다른 Node를 검색하거나 주제를 선택해 주세요.",
    );
    expect(screen.queryByRole("button", { name: "다시 조회" })).toBeNull();
    expect(searchInput().disabled).toBe(false);
    expect(screen.getByRole("button", { name: "주제 목록 열기" })).toBeTruthy();
  });

  it("실패 center와 다른 배포 기본 center가 있을 때만 기본 탐색 escape를 제공한다", async () => {
    window.history.replaceState(
      {},
      "",
      "/?center=9223372036854775806&range=90d",
    );
    fetchMock
      .mockResolvedValueOnce(
        response({ error: { code: "NODE_NOT_FOUND", retryable: false } }, 404),
      )
      .mockResolvedValueOnce(response(exploration("9223372036854775807")));
    render(<App />);
    const escape = await screen.findByRole("button", {
      name: "기본 탐색으로 이동",
    });
    fireEvent.click(escape);
    expect(
      await screen.findByRole("heading", { name: "SK하이닉스" }),
    ).toBeTruthy();
    expect(new URL(window.location.href).searchParams.get("center")).toBe(
      "9223372036854775807",
    );
  });

  it("A에서 B network read가 실패하면 A와 trail을 유지하고 B를 commit하지 않는다", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "SK하이닉스" });
    fetchMock.mockRejectedValueOnce(new TypeError("offline"));
    fireEvent.click(screen.getByRole("button", { name: "다른 graph node 선택" }));
    expect((await screen.findByRole("alert")).textContent).toContain(
      "HBF를 열 수 없습니다.",
    );
    expect(screen.getByRole("heading", { name: "SK하이닉스" })).toBeTruthy();
    expect(
      within(screen.getByRole("navigation", { name: "최근 탐색 경로" })).queryByRole(
        "button",
        { name: "HBF" },
      ),
    ).toBeNull();
    expect(screen.getByRole("button", { name: "다시 조회" })).toBeTruthy();
  });

  it("A에서 B 503 read가 실패해도 A를 유지하고 공개 상태를 추측하지 않는다", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "SK하이닉스" });
    fetchMock.mockResolvedValueOnce(
      response(
        { error: { code: "PUBLICATION_NOT_READY", retryable: true } },
        503,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "다른 graph node 선택" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("HBF를 열 수 없습니다.");
    expect(alert.textContent).toContain(
      "현재 이 Node의 공개 탐색 자료를 불러올 수 없습니다.",
    );
    expect(alert.textContent).not.toMatch(/준비 중|복구 중|생성 중|곧 제공/);
    expect(screen.getByRole("heading", { name: "SK하이닉스" })).toBeTruthy();
  });

  it("기간 read 실패는 성공한 기간을 유지하고 retry 성공 뒤에만 새 기간을 commit한다", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "SK하이닉스" });
    fetchMock.mockResolvedValueOnce(
      response(
        { error: { code: "PUBLICATION_NOT_READY", retryable: true } },
        503,
      ),
    );
    fireEvent.click(screen.getByRole("button", { name: "최근 1년" }));
    await screen.findByRole("alert");
    expect(
      screen.getByRole("button", { name: "최근 90일" }).getAttribute("aria-pressed"),
    ).toBe("true");
    expect(
      screen.getByRole("button", { name: "최근 1년" }).getAttribute("aria-pressed"),
    ).toBe("false");
    expect(new URL(window.location.href).searchParams.get("range")).toBe("90d");

    fetchMock.mockResolvedValueOnce(response(exploration()));
    fireEvent.click(screen.getByRole("button", { name: "다시 조회" }));
    await waitFor(() =>
      expect(
        screen.getByRole("button", { name: "최근 1년" }).getAttribute("aria-pressed"),
      ).toBe("true"),
    );
    expect(new URL(window.location.href).searchParams.get("range")).toBe("1y");
    expect(
      await screen.findByText("최신 공개 상태로 다시 불러왔습니다."),
    ).toBeTruthy();
  });

  it("popstate target read 실패는 현재 화면과 history 의미를 유지하고 retry 성공 때만 target을 반영한다", async () => {
    render(<App />);
    await screen.findByRole("heading", { name: "SK하이닉스" });
    fireEvent.click(screen.getByRole("button", { name: "다른 graph node 선택" }));
    await screen.findByText("요청 중심: 9223372036854775806");
    fireEvent.click(screen.getByRole("button", { name: "중심 전환 완료" }));
    await screen.findByRole("heading", { name: "HBF" });

    const push = vi.spyOn(window.history, "pushState");
    fetchMock.mockResolvedValueOnce(
      response(
        { error: { code: "PUBLICATION_NOT_READY", retryable: true } },
        503,
      ),
    );
    window.history.replaceState(
      {},
      "",
      "/?center=9223372036854775807&range=90d",
    );
    window.dispatchEvent(new PopStateEvent("popstate"));
    await screen.findByRole("alert");
    expect(screen.getByRole("heading", { name: "HBF" })).toBeTruthy();
    expect(push).not.toHaveBeenCalled();

    fetchMock.mockResolvedValueOnce(response(exploration("9223372036854775807")));
    fireEvent.click(screen.getByRole("button", { name: "다시 조회" }));
    await screen.findByText("요청 중심: 9223372036854775807");
    fireEvent.click(screen.getByRole("button", { name: "중심 전환 완료" }));
    expect(
      await screen.findByRole("heading", { name: "SK하이닉스" }),
    ).toBeTruthy();
    expect(push).not.toHaveBeenCalled();
  });
'''
replace(
    "web/src/App.test.tsx",
    '\n});\n\nit("중심에 닿은 간선만 직접 관계로 강조하고 직접 이웃끼리의 선은 구분한다",',
    app_tests + '\n});\n\nit("중심에 닿은 간선만 직접 관계로 강조하고 직접 이웃끼리의 선은 구분한다",',
)

relation_tests = r'''

it("Evidence dialog 첫 read 실패가 dialog를 닫지 않고 retry와 사용자 close를 유지한다", async () => {
  request.mockResolvedValueOnce(
    response({ error: { code: "PANEL_NOT_READY", retryable: true } }, 503),
  );
  render(
    <EvidenceDialog
      selection={{ id: "1", label: "검토 관계" }}
      onClose={vi.fn()}
    />,
  );
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.getByRole("dialog").getAttribute("open")).toBe("");
  expect(screen.getByRole("button", { name: "다시 조회" })).toBeTruthy();
  expect(screen.getByRole("button", { name: "근거 창 닫기" })).toBeTruthy();
});

it("Relation next page 404에서도 이미 읽은 item을 유지하고 추가 read 위치에 안내한다", async () => {
  request
    .mockResolvedValueOnce(response({ items: [relation], next_cursor: "next" }))
    .mockResolvedValueOnce(
      response({ error: { code: "PANEL_NOT_FOUND", retryable: false } }, 404),
    );
  render(<RelationList nodeId="1" nodeName="SK하이닉스" onEvidence={vi.fn()} />);
  expect(await screen.findByRole("button", { name: /HBF.*근거 보기/ })).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "관계 더 보기" }));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "추가 자료를 불러올 수 없습니다. 이미 불러온 내용은 계속 볼 수 있습니다.",
  );
  expect(screen.getByRole("button", { name: /HBF.*근거 보기/ })).toBeTruthy();
  expect(screen.queryByRole("button", { name: "다시 조회" })).toBeNull();
});

it("Trace page1 성공 뒤 next page 404에서도 page1과 dialog를 유지한다", async () => {
  request
    .mockResolvedValueOnce(
      response({ items: [trace], next_cursor: "next", trace_count: 1 }),
    )
    .mockResolvedValueOnce(
      response({ error: { code: "PANEL_NOT_FOUND", retryable: false } }, 404),
    );
  render(
    <EvidenceDialog
      selection={{ id: "1", label: "검토 관계" }}
      onClose={vi.fn()}
    />,
  );
  await screen.findByText("원문 인용");
  fireEvent.click(screen.getByRole("button", { name: "근거 더 보기" }));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "추가 자료를 불러올 수 없습니다. 이미 불러온 내용은 계속 볼 수 있습니다.",
  );
  expect(screen.getByText("원문 인용")).toBeTruthy();
  expect(screen.getByRole("dialog").getAttribute("open")).toBe("");
});
'''
replace(
    "web/src/RelationPanel.test.tsx",
    '\nit("근거 URL의 실행 가능한 scheme을 거부하고 날짜 정밀도를 확대하지 않는다",',
    relation_tests + '\n\nit("근거 URL의 실행 가능한 scheme을 거부하고 날짜 정밀도를 확대하지 않는다",',
)

# Use the actual panel error codes in the existing status matrix.
replace(
    "web/src/RelationPanel.test.tsx",
    '{ error: { code: "REQUEST_FAILED", retryable: status === 503 } },',
    '''{
            error: {
              code:
                status === 503
                  ? "PANEL_NOT_READY"
                  : status === 404
                    ? "PANEL_NOT_FOUND"
                    : "INVALID_REQUEST",
              retryable: status === 503,
            },
          },''',
)

insight_tests = r'''

it("FOLLOWUP 성공 0건은 error가 아니라 승인된 normal empty를 표시한다", async () => {
  request.mockImplementation(async (path: string) => ({
    ok: true,
    status: 200,
    json: async () =>
      path.includes("/questions") || path.includes("/relations")
        ? { items: [], next_cursor: null }
        : result(path),
  }));
  render(<DetailPanel {...props} />);
  expect(
    await screen.findByText("이 기간에는 공개된 후속 질문이 없습니다."),
  ).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
});

it("NODE_INSIGHT 성공 empty는 error가 아니라 승인된 normal empty를 표시한다", async () => {
  request.mockImplementation(async (path: string) => ({
    ok: true,
    status: 200,
    json: async () =>
      path.includes("/insight-report")
        ? { items: [], next_cursor: null }
        : path.includes("/relations")
          ? { items: [], next_cursor: null }
          : result(path),
  }));
  render(<DetailPanel {...props} />);
  fireEvent.click(screen.getByRole("tab", { name: "인사이트" }));
  expect(
    await screen.findByText("이 기간에는 공개된 인사이트가 없습니다."),
  ).toBeTruthy();
  expect(screen.queryByRole("alert")).toBeNull();
});
'''
replace(
    "web/src/InsightPanel.test.tsx",
    '\nit("안전하지 않은 원문 URL은 표시 전에 거부한다",',
    insight_tests + '\n\nit("안전하지 않은 원문 URL은 표시 전에 거부한다",',
)

replace(
    "web/src/usePeripheral.test.tsx",
    '''  expect(result.current.error).not.toBeNull();
  await act(async () => result.current.trigger());''',
    '''  expect(result.current.error).not.toBeNull();
  expect(result.current.graphView?.nodes).toHaveLength(2);
  await act(async () => result.current.trigger());''',
)
replace(
    "web/src/usePeripheral.test.tsx",
    '''  expect(result.current.graphView?.nodes).toHaveLength(2);
  expect(result.current.exhausted).toBe(true);''',
    '''  expect(result.current.graphView?.nodes).toHaveLength(2);
  expect(result.current.retrySuccess).toBe(true);
  expect(result.current.exhausted).toBe(true);''',
)

replace(
    "web/src/TopicPanel.test.tsx",
    '''    expect(screen.getByText("아직 공개된 연결 대상이 없습니다.")).toBeTruthy();''',
    '''    expect(screen.getByText("아직 공개된 연결 대상이 없습니다.")).toBeTruthy();
    expect(screen.queryByRole("tab")).toBeNull();
    expect(
      screen.queryByText("이 기간에는 공개된 후속 질문이 없습니다."),
    ).toBeNull();
    expect(
      screen.queryByText("이 기간에는 공개된 인사이트가 없습니다."),
    ).toBeNull();''',
)
