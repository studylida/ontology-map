from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    if new in text:
        return
    if text.count(old) != 1:
        raise SystemExit(f"expected one match in {path}, found {text.count(old)}")
    file.write_text(text.replace(old, new, 1))


replace_once(
    "web/src/App.tsx",
    '''              pendingNodeId={
                status === "loading" && lastRequestRef.current?.navigation
                  ? lastRequestRef.current.centerId
                  : null
              }''',
    '''              pendingNodeId={
                pendingTransitionRef.current?.request.centerId ??
                (status === "loading" &&
                lastRequestRef.current?.navigation &&
                lastRequestRef.current.centerId !== graphView?.centerId
                  ? lastRequestRef.current.centerId
                  : null)
              }''',
)

replace_once(
    "web/src/GraphCanvas.tsx",
    '''    if (pendingNodeId && introCompletedRef.current) {''',
    '''    if (
      pendingNodeId &&
      pendingNodeId !== centerId &&
      introCompletedRef.current
    ) {''',
)

replace_once(
    "web/src/GraphCanvas.tsx",
    '''    } else if (introStarted && changed) {
      animate("center");
    } else if (introStarted && restoring) {''',
    '''    } else if (introStarted && changed) {
      animate("center");
    } else if (
      introStarted &&
      pendingNodeId === centerId &&
      introCompletedRef.current
    ) {
      paint(1, false);
      removeOutgoing();
      graph.enableNavigationControls(true).enablePointerInteraction(true);
      setBusy(false);
      onTransitionCompleteRef.current(centerId);
    } else if (introStarted && restoring) {''',
)

marker = '''it("대기 중 재선택·오류 종료는 떠 움직임을 정리하고 reduced motion에서는 움직이지 않는다", () => {'''
new_test = '''it("초기 연출 중 새 중심 응답이 도착해도 intro 종료 후 전환 completion을 잃지 않는다", () => {
  const callbacks = props();
  const { rerender } = render(<GraphCanvas {...callbacks} />);
  act(() => vi.advanceTimersByTime(16));
  rerender(<GraphCanvas {...callbacks} introStarted />);
  act(() => vi.advanceTimersByTime(800));
  const next = {
    ...view,
    centerId: "2",
    nodes: [node("2", "center"), node("1", "direct")],
  };
  rerender(
    <GraphCanvas
      {...callbacks}
      introStarted
      view={next}
      pendingNodeId="2"
    />,
  );
  act(() => vi.advanceTimersByTime(2200));
  expect(callbacks.onIntroComplete).toHaveBeenCalledTimes(1);
  expect(callbacks.onTransitionComplete).not.toHaveBeenCalled();
  rerender(
    <GraphCanvas
      {...callbacks}
      introStarted
      introCompleted
      view={next}
      pendingNodeId="2"
    />,
  );
  expect(callbacks.onTransitionComplete).toHaveBeenCalledExactlyOnceWith("2");
  rerender(
    <GraphCanvas
      {...callbacks}
      introStarted
      introCompleted
      view={next}
    />,
  );
  expect(callbacks.onTransitionComplete).toHaveBeenCalledTimes(1);
});

'''
replace_once("web/src/GraphCanvas.test.tsx", marker, new_test + marker)
