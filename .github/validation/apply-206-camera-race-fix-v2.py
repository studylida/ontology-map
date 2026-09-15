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
                pendingTransitionRef.current?.request.centerId ??
                (status === "loading" &&
                lastRequestRef.current?.navigation &&
                lastRequestRef.current.centerId !== graphView?.centerId
                  ? lastRequestRef.current.centerId
                  : null)
              }''',
    '''              pendingNodeId={
                status === "loading" && lastRequestRef.current?.navigation
                  ? lastRequestRef.current.centerId
                  : null
              }''',
)

replace_once(
    "web/src/GraphCanvas.tsx",
    '''    if (
      pendingNodeId &&
      pendingNodeId !== centerId &&
      introCompletedRef.current
    ) {''',
    '''    if (pendingNodeId && introCompletedRef.current) {''',
)

replace_once(
    "web/src/GraphCanvas.tsx",
    '''        if (intro && !introCompleted) onIntroRef.current();
        if (intro && designPreview) {''',
    '''        if (intro && !introCompleted) onIntroRef.current();
        if (intro && changed) onTransitionCompleteRef.current(centerId);
        if (intro && designPreview) {''',
)

replace_once(
    "web/src/GraphCanvas.tsx",
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
    '''    } else if (introStarted && changed) {
      animate("center");
    } else if (introStarted && restoring) {''',
)

replace_once(
    "web/src/GraphCanvas.test.tsx",
    '''  act(() => vi.advanceTimersByTime(2200));
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
  );''',
    '''  act(() => vi.advanceTimersByTime(2200));
  expect(callbacks.onIntroComplete).toHaveBeenCalledTimes(1);
  expect(callbacks.onTransitionComplete).toHaveBeenCalledExactlyOnceWith("2");
  rerender(
    <GraphCanvas
      {...callbacks}
      introStarted
      introCompleted
      view={next}
    />,
  );''',
)
