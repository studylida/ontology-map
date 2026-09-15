from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text()
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one match in {path}, found {count}")
    file.write_text(text.replace(old, new, 1))


def replace_section(path: str, start: str, end: str, replacement: str) -> None:
    file = Path(path)
    text = file.read_text()
    start_index = text.find(start)
    end_index = text.find(end, start_index)
    if start_index < 0 or end_index < 0:
        if replacement in text:
            return
        raise SystemExit(f"section markers not found in {path}: {start!r} -> {end!r}")
    file.write_text(text[:start_index] + replacement + text[end_index:])


replace_once(
    "web/src/App.tsx",
    '''interface ExplorationRequest {
  centerId: string;
  range: TimeRange;
  navigation: Navigation | null;
  panelTab?: 0 | 1 | 2;
}''',
    '''interface ExplorationRequest {
  centerId: string;
  range: TimeRange;
  navigation: Navigation | null;
  panelTab?: 0 | 1 | 2;
  retry?: boolean;
}''',
)

replace_once(
    "web/src/App.tsx",
    'type LoadStatus = "idle" | "loading" | "empty" | "error";',
    'type LoadStatus = "idle" | "loading" | "start" | "empty" | "error";',
)

replace_once(
    "web/src/App.tsx",
    '''function readLocation(): LocationState {
  const params = new URLSearchParams(window.location.search);
  const configuredCenter = import.meta.env.VITE_DEFAULT_CENTER_NODE_ID?.trim();
  return {
    centerId: params.get("center") || configuredCenter || null,
    range: params.get("range") === "1y" ? "1y" : "90d",
  };
}''',
    '''function readConfiguredCenter(): string | null {
  return import.meta.env.VITE_DEFAULT_CENTER_NODE_ID?.trim() || null;
}

function readLocation(): LocationState {
  const params = new URLSearchParams(window.location.search);
  return {
    centerId: params.get("center") || readConfiguredCenter(),
    range: params.get("range") === "1y" ? "1y" : "90d",
  };
}''',
)

new_error_copy = '''function errorCopy(error: APIRequestError | null): {
  title: string;
  detail: string;
} {
  if (
    error?.code === "NODE_NOT_FOUND" ||
    error?.code === "TOPIC_NOT_FOUND" ||
    error?.status === 404
  ) {
    return {
      title: "요청한 Node를 찾을 수 없습니다.",
      detail: "다른 Node를 검색하거나 주제를 선택해 주세요.",
    };
  }
  if (error?.code === "INVALID_REQUEST" || error?.status === 422) {
    return {
      title:
        "요청을 확인할 수 없습니다. 다른 Node를 검색하거나 주제를 선택해 주세요.",
      detail: "",
    };
  }
  if (error?.code === "PUBLICATION_NOT_READY" || error?.status === 503) {
    return {
      title: "현재 이 Node의 공개 탐색 자료를 불러올 수 없습니다.",
      detail: "다른 Node를 검색하거나 주제를 선택할 수 있습니다.",
    };
  }
  return {
    title:
      "탐색 데이터를 불러오지 못했습니다. 네트워크 연결을 확인한 뒤 다시 시도해 주세요.",
    detail: "",
  };
}

'''
replace_section(
    "web/src/App.tsx",
    "function errorCopy(",
    "function TrailHeader(",
    new_error_copy,
)

new_load_notice = '''function LoadNotice({
  status,
  hasView,
  error,
  failedRequest,
  currentCenterId,
  currentName,
  currentRange,
  failedTargetName,
  defaultCenterId,
  onRetry,
  onDefault,
}: {
  status: LoadStatus;
  hasView: boolean;
  error: APIRequestError | null;
  failedRequest: ExplorationRequest | null;
  currentCenterId: string | null;
  currentName: string | null;
  currentRange: TimeRange;
  failedTargetName: string | null;
  defaultCenterId: string | null;
  onRetry: () => void;
  onDefault: () => void;
}) {
  const copy = errorCopy(error);
  const canOpenDefault =
    status === "error" &&
    defaultCenterId !== null &&
    failedRequest !== null &&
    failedRequest.centerId !== defaultCenterId;
  const moving =
    hasView &&
    failedRequest !== null &&
    currentCenterId !== null &&
    failedRequest.centerId !== currentCenterId;
  const changingRange =
    hasView &&
    failedRequest !== null &&
    currentCenterId !== null &&
    failedRequest.centerId === currentCenterId &&
    failedRequest.range !== currentRange;
  const actions = (
    <>
      {error?.retryable && (
        <button type="button" onClick={onRetry}>
          다시 조회
        </button>
      )}
      {canOpenDefault && (
        <button type="button" onClick={onDefault}>
          기본 탐색으로 이동
        </button>
      )}
    </>
  );

  if (status === "loading" && hasView) {
    return (
      <div className={styles.requestStatus} role="status">
        선택한 탐색 데이터를 불러오는 중입니다.
      </div>
    );
  }
  if (status === "start" && !hasView) {
    return (
      <div className={styles.fullStatus} role="status">
        <strong>탐색할 Node를 검색하거나 주제를 선택해 주세요.</strong>
      </div>
    );
  }
  if (status === "error" && hasView) {
    return (
      <div className={styles.requestStatus} role="alert">
        <strong>
          {moving
            ? `${failedTargetName ?? "선택한 Node"}를 열 수 없습니다.`
            : copy.title}
        </strong>
        {moving ? (
          <>
            <span>{`현재 ${currentName ?? "열려 있던 Node"} 화면을 계속 표시합니다.`}</span>
            <span>{copy.title}</span>
          </>
        ) : changingRange ? (
          <span>{`현재 ${currentName ?? "열려 있던 Node"}의 ${
            currentRange === "90d" ? "최근 90일" : "최근 1년"
          } 화면을 계속 표시합니다.`}</span>
        ) : (
          copy.detail && <span>{copy.detail}</span>
        )}
        {actions}
      </div>
    );
  }
  if (!hasView && (status === "error" || status === "empty")) {
    const empty = status === "empty";
    return (
      <div className={styles.fullStatus} role={empty ? "status" : "alert"}>
        <strong>{empty ? "표시할 탐색 데이터가 없습니다." : copy.title}</strong>
        <span>
          {empty
            ? "다른 Node를 검색하거나 주제를 선택해 주세요."
            : copy.detail}
        </span>
        {!empty && actions}
      </div>
    );
  }
  return null;
}

'''
replace_section(
    "web/src/App.tsx",
    "function LoadNotice(",
    "export function App(",
    new_load_notice,
)

replace_once(
    "web/src/App.tsx",
    '''export function App({ designPreview = true }: { designPreview?: boolean }) {
  const initial = useMemo(readLocation, []);''',
    '''export function App({ designPreview = true }: { designPreview?: boolean }) {
  const initial = useMemo(readLocation, []);
  const defaultCenterId = useMemo(readConfiguredCenter, []);''',
)

replace_once(
    "web/src/App.tsx",
    '''  const [trail, setTrail] = useState<string[]>(
    initial.centerId ? [initial.centerId] : [],
  );''',
    '''  const [trail, setTrail] = useState<string[]>([]);''',
)

old_commit = '''  const commitView = useCallback(
    (view: ExplorationView, request: ExplorationRequest) => {
      currentViewRef.current = view;
      setCurrentView(view);
      setGraphView(view);
      setTimeRange(request.range);
      setPanelTab(request.panelTab ?? 0);
      setPanelOpen(true);
      const navigation = request.navigation;
      if (navigation) {
        setTrail((current) =>
          navigation.trailIndex === null
            ? appendTrail(current, view.centerId)
            : current.slice(0, navigation.trailIndex + 1),
        );
        if (navigation.historyMode === "push") {
          writeLocation(view.centerId, request.range, "push");
        }
        setAnnouncement(
          `${nodeCacheRef.current.get(view.centerId)?.name ?? "선택한 node"} 중심으로 이동했습니다.`,
        );
      } else {
        writeLocation(view.centerId, request.range, "replace");
        setTrail((current) => (current.length ? current : [view.centerId]));
        setAnnouncement(
          request.range === "90d"
            ? "최근 90일 탐색 데이터를 표시합니다."
            : "최근 1년 탐색 데이터를 표시합니다.",
        );
      }
    },
    [],
  );'''
new_commit = '''  const commitView = useCallback(
    (view: ExplorationView, request: ExplorationRequest) => {
      currentViewRef.current = view;
      setCurrentView(view);
      setGraphView(view);
      setTimeRange(request.range);
      setPanelTab(request.panelTab ?? 0);
      setPanelOpen(true);
      setEvidence(null);
      const navigation = request.navigation;
      if (navigation) {
        setTrail((current) =>
          navigation.trailIndex === null
            ? appendTrail(current, view.centerId)
            : current.slice(0, navigation.trailIndex + 1),
        );
        if (navigation.historyMode === "push") {
          writeLocation(view.centerId, request.range, "push");
        }
      } else {
        writeLocation(view.centerId, request.range, "replace");
        setTrail((current) => (current.length ? current : [view.centerId]));
      }
      if (request.retry) {
        setAnnouncement("최신 공개 상태로 다시 불러왔습니다.");
      } else if (navigation) {
        setAnnouncement(
          `${nodeCacheRef.current.get(view.centerId)?.name ?? "선택한 Node"} 중심으로 이동했습니다.`,
        );
      } else {
        setAnnouncement(
          request.range === "90d"
            ? "최근 90일 탐색 데이터를 표시합니다."
            : "최근 1년 탐색 데이터를 표시합니다.",
        );
      }
    },
    [],
  );'''
replace_once("web/src/App.tsx", old_commit, new_commit)

replace_once(
    "web/src/App.tsx",
    '''    async (request: ExplorationRequest) => {
      setEvidence(null);
      abortRef.current?.abort();''',
    '''    async (request: ExplorationRequest) => {
      abortRef.current?.abort();''',
)

replace_once(
    "web/src/App.tsx",
    '''          pendingTransitionRef.current = { view, request };
          setGraphView(view);
          setTimeRange(request.range);
          return;''',
    '''          pendingTransitionRef.current = { view, request };
          setGraphView(view);
          return;''',
)

replace_once(
    "web/src/App.tsx",
    '''    } else {
      setRequestError(new APIRequestError("MISSING_DEFAULT_CENTER", 0, false));
      setStatus("error");
    }''',
    '''    } else {
      setRequestError(null);
      setStatus("start");
      setAnnouncement("탐색할 Node를 검색하거나 주제를 선택해 주세요.");
    }''',
)

replace_once(
    "web/src/App.tsx",
    '''  const retry = () => {
    const request = lastRequestRef.current;
    if (request) void loadExploration(request);
  };''',
    '''  const retry = () => {
    const request = lastRequestRef.current;
    if (request) void loadExploration({ ...request, retry: true });
  };

  const openDefault = () => {
    if (!defaultCenterId) return;
    const current = currentViewRef.current;
    if (current?.centerId === defaultCenterId) {
      setRequestError(null);
      setStatus("idle");
      setAnnouncement("기본 탐색 화면을 계속 표시합니다.");
      return;
    }
    void loadExploration({
      centerId: defaultCenterId,
      range: timeRange,
      navigation: current
        ? { trailIndex: null, historyMode: "push" }
        : null,
    });
  };''',
)

replace_once(
    "web/src/App.tsx",
    '''  const loading = useInitialLoading(
    graphReady,
    status === "error" || status === "empty",
  );''',
    '''  const loading = useInitialLoading(
    graphReady,
    status === "error" || status === "empty" || status === "start",
  );''',
)

replace_once(
    "web/src/App.tsx",
    '''  for (const node of peripheral.graphView?.nodes ?? []) {
    nodeTypes.set(node.kindCode, node.kind);
  }

  return (''',
    '''  for (const node of peripheral.graphView?.nodes ?? []) {
    nodeTypes.set(node.kindCode, node.kind);
  }
  const failedRequest = status === "error" ? lastRequestRef.current : null;
  const failedTargetName = failedRequest
    ? nodeCacheRef.current.get(failedRequest.centerId)?.name ?? null
    : null;

  return (''',
)

replace_once(
    "web/src/App.tsx",
    '''          {currentView && currentNode && (
            <>''',
    '''          {!currentView && status !== "loading" && (
            <div className={styles.controls}>
              <label htmlFor="node-search">Node 검색</label>
              <div className={styles.searchWithTopics}>
                <NodeSearch onSelect={selectNode} />
                <TopicPicker onSelect={selectNode} />
              </div>
            </div>
          )}

          {currentView && currentNode && (
            <>''',
)

replace_once(
    "web/src/App.tsx",
    '''                <PageNotice
                  loading={peripheral.loading}
                  error={peripheral.error}
                  empty={false}
                  onRetry={peripheral.retry}
                />''',
    '''                <PageNotice
                  loading={peripheral.loading}
                  error={peripheral.error}
                  empty={false}
                  additional={Boolean(peripheral.graphView)}
                  retrySuccess={peripheral.retrySuccess}
                  onRetry={peripheral.retry}
                />''',
)

replace_once(
    "web/src/App.tsx",
    '''          <LoadNotice
            status={status}
            hasView={Boolean(currentView)}
            error={requestError}
            onRetry={retry}
          />''',
    '''          <LoadNotice
            status={status}
            hasView={Boolean(currentView)}
            error={requestError}
            failedRequest={failedRequest}
            currentCenterId={currentView?.centerId ?? null}
            currentName={currentNode?.name ?? null}
            currentRange={timeRange}
            failedTargetName={failedTargetName}
            defaultCenterId={defaultCenterId}
            onRetry={retry}
            onDefault={openDefault}
          />''',
)

new_page_notice = '''export function PageNotice({
  loading,
  error,
  empty,
  onRetry,
  emptyMessage = "현재 공개된 자료가 없습니다.",
  additional = false,
  kind = "panel",
  retrySuccess = false,
}: {
  loading: boolean;
  error: APIRequestError | null;
  empty: boolean;
  onRetry: () => void;
  emptyMessage?: string;
  additional?: boolean;
  kind?: "panel" | "relationTrace";
  retrySuccess?: boolean;
}) {
  if (loading) return <p role="status">불러오는 중입니다.</p>;
  if (error) {
    const message = additional
      ? "추가 자료를 불러올 수 없습니다. 이미 불러온 내용은 계속 볼 수 있습니다."
      : error.status === 404
        ? kind === "relationTrace"
          ? "이 연결의 공개 근거를 현재 불러올 수 없습니다."
          : "요청한 자료를 찾을 수 없습니다."
        : error.status === 422
          ? "요청을 확인할 수 없습니다."
          : error.code === "PANEL_NOT_READY" || error.status === 503
            ? "현재 이 영역의 공개 자료를 불러올 수 없습니다."
            : "자료를 불러오지 못했습니다. 네트워크 연결을 확인한 뒤 다시 시도해 주세요.";
    return (
      <div role="alert">
        <p>{message}</p>
        {error.retryable && (
          <button type="button" onClick={onRetry}>
            다시 조회
          </button>
        )}
      </div>
    );
  }
  return (
    <>
      {retrySuccess && (
        <p role="status">최신 공개 상태로 다시 불러왔습니다.</p>
      )}
      {empty && (
        <p className={styles.empty} role="status">
          {emptyMessage}
        </p>
      )}
    </>
  );
}

'''
replace_section(
    "web/src/RelationPanel.tsx",
    "export function PageNotice(",
    "export function RelationList(",
    new_page_notice,
)

replace_once(
    "web/src/RelationPanel.tsx",
    '''      <PageNotice {...page} empty={!page.items.length} onRetry={page.retry} />''',
    '''      <PageNotice
        {...page}
        empty={!page.items.length}
        additional={page.items.length > 0}
        onRetry={page.retry}
      />''',
)
replace_once(
    "web/src/RelationPanel.tsx",
    '''      <PageNotice {...page} empty={!page.items.length} onRetry={page.retry} />''',
    '''      <PageNotice
        {...page}
        empty={!page.items.length}
        additional={page.items.length > 0}
        kind="relationTrace"
        onRetry={page.retry}
      />''',
)

replace_once(
    "web/src/useCursorPage.ts",
    '''  const [error, setError] = useState<APIRequestError | null>(null);
  const controllerRef = useRef<AbortController | null>(null);''',
    '''  const [error, setError] = useState<APIRequestError | null>(null);
  const [retrySuccess, setRetrySuccess] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);''',
)
replace_once(
    "web/src/useCursorPage.ts",
    '''    async (cursor: string | null) => {
      if (pendingRef.current) return;
      pendingRef.current = true;''',
    '''    async (cursor: string | null, retryAttempt = false) => {
      if (pendingRef.current) return;
      pendingRef.current = true;
      setRetrySuccess(false);''',
)
replace_once(
    "web/src/useCursorPage.ts",
    '''        setNextCursor(page.nextCursor);
      } catch (cause) {''',
    '''        setNextCursor(page.nextCursor);
        if (retryAttempt) setRetrySuccess(true);
      } catch (cause) {''',
)
replace_once(
    "web/src/useCursorPage.ts",
    '''    setNextCursor(null);
    pendingRef.current = false;''',
    '''    setNextCursor(null);
    setRetrySuccess(false);
    pendingRef.current = false;''',
)
replace_once(
    "web/src/useCursorPage.ts",
    '''    error,
    nextCursor,''',
    '''    error,
    retrySuccess,
    nextCursor:''',
)
replace_once(
    "web/src/useCursorPage.ts",
    '''    retry: () => {
      void load(lastCursorRef.current);
    },''',
    '''    retry: () => {
      void load(lastCursorRef.current, true);
    },''',
)

replace_once(
    "web/src/usePeripheral.ts",
    '''  const [error, setError] = useState<APIRequestError | null>(null);
  const nextRef = useRef<string | null | undefined>(undefined);''',
    '''  const [error, setError] = useState<APIRequestError | null>(null);
  const [retrySuccess, setRetrySuccess] = useState(false);
  const nextRef = useRef<string | null | undefined>(undefined);''',
)
replace_once(
    "web/src/usePeripheral.ts",
    '''    setError(null);
    setLoading(false);''',
    '''    setError(null);
    setRetrySuccess(false);
    setLoading(false);''',
)
replace_once(
    "web/src/usePeripheral.ts",
    '''      pendingRef.current = true;
      setLoading(true);
      setError(null);''',
    '''      pendingRef.current = true;
      setLoading(true);
      setError(null);
      setRetrySuccess(false);''',
)
replace_once(
    "web/src/usePeripheral.ts",
    '''        setResult((current) => ({
          ...page,''',
    '''        if (retry) setRetrySuccess(true);
        setResult((current) => ({
          ...page,''',
)
replace_once(
    "web/src/usePeripheral.ts",
    '''    error,
    exhausted:''',
    '''    error,
    retrySuccess,
    exhausted:''',
)

replace_once(
    "web/src/QuestionPanel.tsx",
    '''      {page.items.map((question) => (
        <Question key={question.id} question={question} {...props} />
      ))}
      <PageNotice {...page} empty={!page.items.length} onRetry={page.retry} />''',
    '''      {page.items.map((question) => (
        <Question key={question.id} question={question} {...props} />
      ))}
      <PageNotice
        {...page}
        empty={!page.items.length}
        additional={page.items.length > 0}
        emptyMessage="이 기간에는 공개된 후속 질문이 없습니다."
        onRetry={page.retry}
      />''',
)

replace_once(
    "web/src/InsightPanel.tsx",
    '''        <PageNotice {...page} empty={!report} onRetry={page.retry} />''',
    '''        <PageNotice
          {...page}
          empty={!report}
          emptyMessage="이 기간에는 공개된 인사이트가 없습니다."
          onRetry={page.retry}
        />''',
)
replace_once(
    "web/src/InsightPanel.tsx",
    '''      <PageNotice {...page} empty={!report} onRetry={page.retry} />''',
    '''      <PageNotice
        {...page}
        empty={!report}
        emptyMessage="이 기간에는 공개된 인사이트가 없습니다."
        onRetry={page.retry}
      />''',
)

replace_once(
    "web/src/PanelEvidence.tsx",
    '''      <PageNotice {...page} empty={!page.items.length} onRetry={page.retry} />''',
    '''      <PageNotice
        {...page}
        empty={!page.items.length}
        additional={page.items.length > 0}
        onRetry={page.retry}
      />''',
)
replace_once(
    "web/src/PanelEvidence.tsx",
    '''      <PageNotice {...page} empty={!page.items.length} onRetry={page.retry} />''',
    '''      <PageNotice
        {...page}
        empty={!page.items.length}
        additional={page.items.length > 0}
        onRetry={page.retry}
      />''',
)
