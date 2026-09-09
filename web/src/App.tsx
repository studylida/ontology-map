import {
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import styles from "./App.module.css";
import { DetailPanel } from "./DetailPanel";
import {
  APIRequestError,
  type ExplorationView,
  fetchExploration,
  type KnowledgeNode,
  type TimeRange,
} from "./data";
import { GraphCanvas } from "./GraphCanvas";
import { NodeSearch } from "./NodeSearch";
import {
  EvidenceDialog,
  type EvidenceSelection,
  PageNotice,
} from "./RelationPanel";
import { useInitialLoading } from "./useInitialLoading";
import { usePeripheral } from "./usePeripheral";

interface LocationState {
  centerId: string | null;
  range: TimeRange;
}

interface Navigation {
  trailIndex: number | null;
  historyMode: "push" | "none";
}

interface ExplorationRequest {
  centerId: string;
  range: TimeRange;
  navigation: Navigation | null;
}

interface PendingTransition {
  view: ExplorationView;
  request: ExplorationRequest;
}

type LoadStatus = "idle" | "loading" | "empty" | "error";

const maxTrailLength = 4;

function appendTrail(trail: string[], nodeId: string): string[] {
  if (trail.at(-1) === nodeId) return trail;
  return [...trail, nodeId].slice(-maxTrailLength);
}

function readLocation(): LocationState {
  const params = new URLSearchParams(window.location.search);
  const configuredCenter = import.meta.env.VITE_DEFAULT_CENTER_NODE_ID?.trim();
  return {
    centerId: params.get("center") || configuredCenter || null,
    range: params.get("range") === "1y" ? "1y" : "90d",
  };
}

function writeLocation(
  centerId: string,
  range: TimeRange,
  mode: "push" | "replace",
) {
  const params = new URLSearchParams({ center: centerId, range });
  window.history[`${mode}State`](
    {},
    "",
    `${window.location.pathname}?${params.toString()}`,
  );
}

function errorCopy(error: APIRequestError | null): {
  title: string;
  detail: string;
} {
  if (error?.code === "NODE_NOT_FOUND" || error?.status === 404) {
    return {
      title: "요청한 node를 찾을 수 없습니다.",
      detail: "중심 node ID를 확인한 뒤 다시 열어 주세요.",
    };
  }
  if (error?.code === "PUBLICATION_NOT_READY" || error?.status === 503) {
    return {
      title: "공개 데이터를 준비하고 있습니다.",
      detail:
        "이전에 공개된 탐색 결과가 아직 없습니다. 잠시 후 다시 시도해 주세요.",
    };
  }
  if (error?.code === "MISSING_DEFAULT_CENTER") {
    return {
      title: "기본 중심 node가 설정되지 않았습니다.",
      detail:
        "VITE_DEFAULT_CENTER_NODE_ID에 HBF fixture가 출력한 node ID를 설정해 주세요.",
    };
  }
  return {
    title: "탐색 데이터를 불러오지 못했습니다.",
    detail: "네트워크 연결을 확인한 뒤 다시 시도해 주세요.",
  };
}

function TrailHeader({
  trail,
  currentId,
  nodes,
  onSelect,
  children,
}: {
  trail: string[];
  currentId: string | undefined;
  nodes: Map<string, KnowledgeNode>;
  onSelect: (nodeId: string, trailIndex: number) => void;
  children?: ReactNode;
}) {
  return (
    <header className={styles.header}>
      <div className={styles.brand}>
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="6" cy="7" r="3" />
          <circle cx="17.5" cy="16.5" r="2" />
          <path d="M8.5 9.2 16 15" />
        </svg>
        <strong>ontology-map</strong>
      </div>
      <nav className={styles.trail} aria-label="최근 탐색 경로">
        <ol>
          {trail.map((trailId, index) => {
            const trailNode = nodes.get(trailId);
            const current = currentId === trailId && index === trail.length - 1;
            return (
              // biome-ignore lint/suspicious/noArrayIndexKey: 같은 node가 경로에 반복될 수 있고 항목 내부 상태가 없습니다.
              <li className={styles.trailItem} key={`${trailId}-${index}`}>
                {index > 0 && <span className={styles.trailSeparator}>/</span>}
                {current ? (
                  <span aria-current="page">{trailNode?.name ?? trailId}</span>
                ) : (
                  <button
                    type="button"
                    aria-label={`탐색 경로에서 ${trailNode?.name ?? trailId} 선택`}
                    onClick={() => onSelect(trailId, index)}
                  >
                    {trailNode?.name ?? trailId}
                  </button>
                )}
              </li>
            );
          })}
        </ol>
      </nav>
      {children}
    </header>
  );
}

function MapLegend({
  designPreview,
  open,
  onToggle,
  nodeTypes,
  hiddenKinds,
  onFilter,
}: {
  designPreview: boolean;
  open: boolean;
  onToggle: () => void;
  nodeTypes: Map<string, string>;
  hiddenKinds: readonly string[];
  onFilter: (hidden: string[]) => void;
}) {
  return (
    <aside className={styles.legend} aria-label="지식맵 범례">
      <button
        type="button"
        className={styles.legendToggle}
        aria-expanded={open}
        onClick={onToggle}
      >
        <span className={styles.legendDots} aria-hidden="true">
          {[...nodeTypes].map(([code, name]) => (
            <i
              key={code}
              data-kind={name}
              data-hidden={hiddenKinds.includes(code)}
            />
          ))}
        </span>
        <strong>범례{hiddenKinds.length > 0 && " · 필터 적용 중"}</strong>
        <span aria-hidden="true">{open ? "⌄" : "⌃"}</span>
      </button>
      {open && (
        <div className={styles.legendContent}>
          <h2>노드 유형</h2>
          <div className={styles.nodeTypes}>
            {[...nodeTypes].map(([code, name]) => (
              <button
                type="button"
                key={code}
                data-kind={name}
                aria-pressed={!hiddenKinds.includes(code)}
                onClick={() =>
                  onFilter(
                    hiddenKinds.includes(code)
                      ? hiddenKinds.filter((kind) => kind !== code)
                      : [...hiddenKinds, code],
                  )
                }
              >
                <i aria-hidden="true" />
                {name}
              </button>
            ))}
          </div>
          <div className={styles.legendActions}>
            <button type="button" onClick={() => onFilter([])}>
              전체 표시
            </button>
            <button
              type="button"
              onClick={() => onFilter([...nodeTypes.keys()])}
            >
              전체 해제
            </button>
          </div>
          <div className={styles.legendLine}>
            {designPreview && (
              <span>
                <i className={styles.connectedLine} />
                중심·선택 연결
              </span>
            )}
            <span>
              <i className={styles.line1} />
              근거 1개
            </span>
            <span>
              <i className={styles.line3} />
              근거 3개
            </span>
            <span>
              <i className={styles.line6} />
              근거 6개
            </span>
            <span>
              <i className={styles.conflictLine} />
              충돌 관계
            </span>
          </div>
        </div>
      )}
    </aside>
  );
}

function LoadNotice({
  status,
  hasView,
  error,
  onRetry,
}: {
  status: LoadStatus;
  hasView: boolean;
  error: APIRequestError | null;
  onRetry: () => void;
}) {
  const copy = errorCopy(error);
  if (status === "loading" && hasView) {
    return (
      <div className={styles.requestStatus} role="status">
        선택한 탐색 데이터를 불러오는 중입니다.
      </div>
    );
  }
  if (status === "error" && hasView) {
    return (
      <div className={styles.requestStatus} role="alert">
        <strong>{copy.title}</strong>
        <span>{copy.detail}</span>
        {error?.retryable && (
          <button type="button" onClick={onRetry}>
            다시 시도
          </button>
        )}
      </div>
    );
  }
  if (!hasView && (status === "error" || status === "empty")) {
    const empty = status === "empty";
    return (
      <div className={styles.fullStatus} role={empty ? "status" : "alert"}>
        <strong>{empty ? "표시할 탐색 데이터가 없습니다." : copy.title}</strong>
        <span>{empty ? "다른 중심 node를 선택해 주세요." : copy.detail}</span>
        {!empty && error?.retryable && (
          <button type="button" onClick={onRetry}>
            다시 시도
          </button>
        )}
      </div>
    );
  }
  return null;
}

export function App({ designPreview = true }: { designPreview?: boolean }) {
  const initial = useMemo(readLocation, []);
  const [hiddenKinds, setHiddenKinds] = useState<string[]>([]);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [loadingTip] = useState(() => {
    const tips = [
      "노드를 누르면 그 주제를 중심으로 지도를 탐색할 수 있어요.",
      "빈 공간을 끌어 지도를 움직이고, 휠로 확대하거나 축소해 보세요.",
      "간선을 누르면 두 노드가 연결된 이유와 근거를 볼 수 있어요.",
      "노드에 마우스를 올리면 연결된 관계가 강조돼요.",
    ];
    return tips[Math.floor(Math.random() * tips.length)];
  });
  useEffect(() => {
    if (!designPreview) return;
    document.documentElement.dataset.theme = theme;
    return () => {
      delete document.documentElement.dataset.theme;
    };
  }, [designPreview, theme]);
  const [currentView, setCurrentView] = useState<ExplorationView | null>(null);
  const [graphView, setGraphView] = useState<ExplorationView | null>(null);
  const [timeRange, setTimeRange] = useState(initial.range);
  const [trail, setTrail] = useState<string[]>(
    initial.centerId ? [initial.centerId] : [],
  );
  const [panelOpen, setPanelOpen] = useState(true);
  const [evidence, setEvidence] = useState<EvidenceSelection | null>(null);
  const [legendOpen, setLegendOpen] = useState(false);
  const [graphReady, setGraphReady] = useState(false);
  const [introComplete, setIntroComplete] = useState(false);
  const [status, setStatus] = useState<LoadStatus>("loading");
  const [requestError, setRequestError] = useState<APIRequestError | null>(
    null,
  );
  const [announcement, setAnnouncement] = useState(
    "탐색 데이터를 불러오는 중입니다.",
  );
  const abortRef = useRef<AbortController | null>(null);
  const currentViewRef = useRef<ExplorationView | null>(null);
  const lastRequestRef = useRef<ExplorationRequest | null>(null);
  const pendingTransitionRef = useRef<PendingTransition | null>(null);
  const nodeCacheRef = useRef(new Map<string, KnowledgeNode>());

  const cacheView = useCallback((view: ExplorationView) => {
    for (const node of view.nodes) nodeCacheRef.current.set(node.id, node);
    for (const recommendation of view.recommendations) {
      nodeCacheRef.current.set(recommendation.node.id, recommendation.node);
    }
  }, []);

  const commitView = useCallback(
    (view: ExplorationView, request: ExplorationRequest) => {
      currentViewRef.current = view;
      setCurrentView(view);
      setGraphView(view);
      setTimeRange(request.range);
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
  );

  const loadExploration = useCallback(
    async (request: ExplorationRequest) => {
      setEvidence(null);
      abortRef.current?.abort();
      pendingTransitionRef.current = null;
      if (currentViewRef.current) setGraphView(currentViewRef.current);
      const controller = new AbortController();
      abortRef.current = controller;
      lastRequestRef.current = request;
      setStatus("loading");
      setRequestError(null);

      try {
        const view = await fetchExploration(
          request.centerId,
          request.range,
          controller.signal,
        );
        if (controller.signal.aborted) return;
        cacheView(view);
        if (!view.nodes.length) {
          setStatus("empty");
          return;
        }
        setStatus("idle");
        const current = currentViewRef.current;
        if (
          request.navigation &&
          current &&
          request.centerId !== current.centerId
        ) {
          pendingTransitionRef.current = { view, request };
          setGraphView(view);
          setTimeRange(request.range);
          return;
        }
        commitView(view, request);
      } catch (error) {
        if (controller.signal.aborted) return;
        const normalized =
          error instanceof APIRequestError
            ? error
            : new APIRequestError("NETWORK_ERROR", 0, true);
        setRequestError(normalized);
        setStatus("error");
      }
    },
    [cacheView, commitView],
  );

  useEffect(() => {
    if (initial.centerId) {
      void loadExploration({
        centerId: initial.centerId,
        range: initial.range,
        navigation: null,
      });
    } else {
      setRequestError(new APIRequestError("MISSING_DEFAULT_CENTER", 0, false));
      setStatus("error");
    }

    const onPopState = () => {
      const location = readLocation();
      if (!location.centerId) return;
      void loadExploration({
        centerId: location.centerId,
        range: location.range,
        navigation: {
          trailIndex: null,
          historyMode: "none",
        },
      });
    };
    window.addEventListener("popstate", onPopState);
    return () => {
      window.removeEventListener("popstate", onPopState);
      abortRef.current?.abort();
    };
  }, [initial, loadExploration]);

  const selectNode = (targetId: string, trailIndex: number | null = null) => {
    void loadExploration({
      centerId: targetId,
      range: timeRange,
      navigation: { trailIndex, historyMode: "push" },
    });
  };

  const finishNodeTransition = (completedCenterId: string) => {
    const pending = pendingTransitionRef.current;
    if (!pending || pending.view.centerId !== completedCenterId) return;
    pendingTransitionRef.current = null;
    commitView(pending.view, pending.request);
  };

  const changeRange = (range: TimeRange) => {
    if (!currentView || range === timeRange) return;
    void loadExploration({
      centerId: currentView.centerId,
      range,
      navigation: null,
    });
  };

  const retry = () => {
    const request = lastRequestRef.current;
    if (request) void loadExploration(request);
  };

  const currentNode = currentView?.nodes.find(
    (node) => node.id === currentView.centerId,
  );
  const loading = useInitialLoading(
    graphReady,
    status === "error" || status === "empty",
  );
  const initialLoading = loading.phase !== "hidden";
  const peripheral = usePeripheral(
    graphView,
    timeRange,
    status === "idle" && !pendingTransitionRef.current,
    initialLoading || introComplete,
  );

  const loadedNodes = peripheral.graphView?.nodes ?? [];
  const filteredNodeCount = loadedNodes.filter(
    (node) => !hiddenKinds.includes(node.kindCode),
  ).length;
  const nodeTypes = new Map([
    ["PERSON", "사람"],
    ["COMPANY", "회사"],
    ["TECHNOLOGY", "기술"],
    ["TOPIC", "주제"],
    ["EVENT", "사건"],
  ]);
  for (const node of peripheral.graphView?.nodes ?? [])
    nodeTypes.set(node.kindCode, node.kind);

  return (
    <>
      <main
        className={styles.app}
        data-design-preview={designPreview || undefined}
        inert={initialLoading ? true : undefined}
      >
        <TrailHeader
          trail={trail}
          currentId={currentView?.centerId}
          nodes={nodeCacheRef.current}
          onSelect={selectNode}
        >
          {designPreview && (
            <div className={styles.themeControl}>
              <button
                type="button"
                aria-label="라이트 모드"
                aria-pressed={theme === "light"}
                onClick={() =>
                  setTheme((current) => (current === "dark" ? "light" : "dark"))
                }
              >
                {theme === "dark" ? "☀ 라이트 모드" : "☾ 다크 모드"}
              </button>
            </div>
          )}
        </TrailHeader>
        <section className={styles.workspace}>
          {peripheral.graphView && (
            <GraphCanvas
              designPreview={designPreview}
              theme={theme}
              hiddenKinds={hiddenKinds}
              pendingNodeId={
                status === "loading" && lastRequestRef.current?.navigation
                  ? lastRequestRef.current.centerId
                  : null
              }
              panelOpen={panelOpen}
              onIntroComplete={() => setIntroComplete(true)}
              view={peripheral.graphView}
              onPanBoundary={peripheral.trigger}
              introStarted={graphReady && !initialLoading}
              introCompleted={introComplete}
              onReady={() => setGraphReady(true)}
              onSelect={selectNode}
              onEvidence={setEvidence}
              onTransitionComplete={finishNodeTransition}
            />
          )}

          {currentView && currentNode && (
            <>
              <div className={styles.controls}>
                <label htmlFor="node-search">노드 검색</label>
                <NodeSearch onSelect={selectNode} />
                <div className={styles.scopeSummary}>
                  <strong>
                    {currentNode.name} 주변 · 노드 {filteredNodeCount}개
                  </strong>
                </div>
                <fieldset
                  className={styles.rangeControl}
                  disabled={status === "loading"}
                >
                  <legend>시간 범위</legend>
                  <button
                    type="button"
                    aria-pressed={timeRange === "90d"}
                    onClick={() => changeRange("90d")}
                  >
                    최근 90일
                  </button>
                  <button
                    type="button"
                    aria-pressed={timeRange === "1y"}
                    onClick={() => changeRange("1y")}
                  >
                    최근 1년
                  </button>
                </fieldset>
              </div>

              <MapLegend
                designPreview={designPreview}
                open={legendOpen}
                nodeTypes={nodeTypes}
                hiddenKinds={hiddenKinds}
                onFilter={setHiddenKinds}
                onToggle={() => setLegendOpen((open) => !open)}
              />

              {panelOpen ? (
                <DetailPanel
                  key={`${currentView.centerId}:${timeRange}`}
                  timeRange={timeRange}
                  view={currentView}
                  onClose={() => setPanelOpen(false)}
                  onSelect={selectNode}
                />
              ) : (
                <button
                  type="button"
                  className={styles.openPanel}
                  onClick={() => setPanelOpen(true)}
                >
                  상세 패널 열기
                </button>
              )}
            </>
          )}

          {(peripheral.loading || peripheral.error || peripheral.exhausted) && (
            <aside
              className={styles.peripheralStatus}
              aria-label="주변부 조회 상태"
            >
              <PageNotice
                loading={peripheral.loading}
                error={peripheral.error}
                empty={false}
                onRetry={peripheral.retry}
              />
              {peripheral.exhausted && !peripheral.error && (
                <span role="status">추가 주변부 결과가 없습니다.</span>
              )}
            </aside>
          )}
          <LoadNotice
            status={status}
            hasView={Boolean(currentView)}
            error={requestError}
            onRetry={retry}
          />
        </section>
        <div className={styles.liveRegion} aria-live="polite">
          {announcement}
        </div>
      </main>

      {evidence && (
        <EvidenceDialog
          key={evidence.id}
          selection={evidence}
          onClose={() => setEvidence(null)}
        />
      )}

      {initialLoading && (
        <div
          className={styles.loadingOverlay}
          data-leaving={loading.phase === "leaving"}
          role="status"
          aria-label="탐색 데이터 불러오는 중"
        >
          <div className={styles.loadingContent}>
            <strong>Loading</strong>
            <span>-- {loading.progress}% --</span>
            <div
              className={styles.loadingTrack}
              role="progressbar"
              aria-label="지도 준비"
              aria-valuemin={0}
              aria-valuemax={99}
              aria-valuenow={loading.progress}
            >
              <i style={{ width: `${loading.progress}%` }} />
            </div>
            {designPreview && <p className={styles.loadingTip}>{loadingTip}</p>}
          </div>
        </div>
      )}
    </>
  );
}
