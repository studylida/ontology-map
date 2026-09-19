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
  type KnowledgeNode,
  type TimeRange,
  timeRangeLabel,
} from "./data";
import {
  GraphCanvas,
  type GraphFocusRequest,
  type GraphOverviewRequest,
} from "./GraphCanvas";
import { NodeSearch } from "./NodeSearch";
import {
  EvidenceDialog,
  type EvidenceSelection,
  PageNotice,
} from "./RelationPanel";
import { TopicPanel } from "./TopicPanel";
import { TopicPicker } from "./TopicPicker";
import { fetchCenterExploration, isTopicExploration } from "./topicData";
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
  panelTab?: 0 | 1 | 2;
  retry?: boolean;
}

interface PendingTransition {
  view: ExplorationView;
  request: ExplorationRequest;
}

type LoadStatus = "idle" | "loading" | "start" | "empty" | "error";

const maxTrailLength = 4;

function appendTrail(trail: string[], nodeId: string): string[] {
  if (trail.at(-1) === nodeId) return trail;
  return [...trail, nodeId].slice(-maxTrailLength);
}

function readConfiguredCenter(): string | null {
  return import.meta.env.VITE_DEFAULT_CENTER_NODE_ID?.trim() || null;
}

function readLocation(): LocationState {
  const params = new URLSearchParams(window.location.search);
  return {
    centerId: params.get("center") || readConfiguredCenter(),
    range:
      params.get("range") === "1y" || params.get("range") === "all"
        ? (params.get("range") as "1y" | "all")
        : "90d",
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
  if (
    error?.code === "NODE_NOT_FOUND" ||
    error?.code === "TOPIC_NOT_FOUND" ||
    error?.status === 404
  ) {
    return {
      title: "요청한 대상을 찾을 수 없습니다.",
      detail: "다른 대상을 검색하거나 주제를 선택해 주세요.",
    };
  }
  if (error?.code === "INVALID_REQUEST" || error?.status === 422) {
    return {
      title:
        "요청을 확인할 수 없습니다. 다른 대상을 검색하거나 주제를 선택해 주세요.",
      detail: "",
    };
  }
  if (error?.code === "PUBLICATION_NOT_READY" || error?.status === 503) {
    return {
      title: "현재 이 대상의 공개 탐색 자료를 불러올 수 없습니다.",
      detail: "다른 대상을 검색하거나 주제를 선택할 수 있습니다.",
    };
  }
  return {
    title:
      "탐색 데이터를 불러오지 못했습니다. 네트워크 연결을 확인한 뒤 다시 시도해 주세요.",
    detail: "",
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
        <strong>탐색할 대상을 검색하거나 주제를 선택해 주세요.</strong>
      </div>
    );
  }
  if (status === "error" && hasView) {
    return (
      <div className={styles.requestStatus} role="alert">
        <strong>
          {moving
            ? `${failedTargetName ?? "선택한 대상"} 대상을 열 수 없습니다.`
            : copy.title}
        </strong>
        {moving ? (
          <>
            <span>{`현재 ${currentName ?? "열려 있던 대상"} 화면을 계속 표시합니다.`}</span>
            <span>{copy.title}</span>
          </>
        ) : changingRange ? (
          <span>{`현재 ${currentName ?? "열려 있던 대상"}의 ${timeRangeLabel(currentRange)} 화면을 계속 표시합니다.`}</span>
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
          {empty ? "다른 대상을 검색하거나 주제를 선택해 주세요." : copy.detail}
        </span>
        {!empty && actions}
      </div>
    );
  }
  return null;
}

export function App({ designPreview = true }: { designPreview?: boolean }) {
  const initial = useMemo(readLocation, []);
  const defaultCenterId = useMemo(readConfiguredCenter, []);
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
  const [trail, setTrail] = useState<string[]>([]);
  const [panelOpen, setPanelOpen] = useState(true);
  const [panelTab, setPanelTab] = useState<0 | 1 | 2>(0);
  const [evidence, setEvidence] = useState<EvidenceSelection | null>(null);
  const [focusRequest, setFocusRequest] = useState<GraphFocusRequest | null>(
    null,
  );
  const focusSequenceRef = useRef(0);
  const [overviewRequest, setOverviewRequest] =
    useState<GraphOverviewRequest | null>(null);
  const [mapOverviewActive, setMapOverviewActive] = useState(false);
  const overviewSequenceRef = useRef(0);
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
      setPanelTab(request.panelTab ?? 0);
      setPanelOpen(true);
      setEvidence(null);
      setFocusRequest(null);
      setOverviewRequest(null);
      setMapOverviewActive(false);
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
          `${nodeCacheRef.current.get(view.centerId)?.name ?? "선택한 대상"} 중심으로 이동했습니다.`,
        );
      } else {
        setAnnouncement(
          `${timeRangeLabel(request.range)} 탐색 데이터를 표시합니다.`,
        );
      }
    },
    [],
  );

  const loadExploration = useCallback(
    async (request: ExplorationRequest) => {
      abortRef.current?.abort();
      pendingTransitionRef.current = null;
      if (currentViewRef.current) setGraphView(currentViewRef.current);
      const controller = new AbortController();
      abortRef.current = controller;
      lastRequestRef.current = request;
      setStatus("loading");
      setRequestError(null);

      try {
        const view = await fetchCenterExploration(
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
      setRequestError(null);
      setStatus("start");
      setAnnouncement("탐색할 대상을 검색하거나 주제를 선택해 주세요.");
    }

    const onPopState = () => {
      const location = readLocation();
      if (!location.centerId) {
        abortRef.current?.abort();
        abortRef.current = null;
        pendingTransitionRef.current = null;
        currentViewRef.current = null;
        lastRequestRef.current = null;
        setCurrentView(null);
        setGraphView(null);
        setTimeRange(location.range);
        setTrail([]);
        setEvidence(null);
        setOverviewRequest(null);
        setMapOverviewActive(false);
        setRequestError(null);
        setStatus("start");
        setAnnouncement("탐색할 대상을 검색하거나 주제를 선택해 주세요.");
        return;
      }
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

  const selectNodeInsight = (targetId: string) => {
    void loadExploration({
      centerId: targetId,
      range: timeRange,
      navigation: { trailIndex: null, historyMode: "push" },
      panelTab: 2,
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
      navigation: current ? { trailIndex: null, historyMode: "push" } : null,
    });
  };

  const currentNode = currentView?.nodes.find(
    (node) => node.id === currentView.centerId,
  );
  const loading = useInitialLoading(
    graphReady,
    status === "error" || status === "empty" || status === "start",
  );
  const initialLoading = loading.phase !== "hidden";
  const peripheral = usePeripheral(
    graphView,
    timeRange,
    status === "idle" &&
      !pendingTransitionRef.current &&
      !isTopicExploration(graphView),
    initialLoading || introComplete,
  );

  const loadedNodes = peripheral.graphView?.nodes ?? [];
  const allNodesFiltered =
    loadedNodes.length > 0 &&
    loadedNodes.every((node) => hiddenKinds.includes(node.kindCode));
  const nodeTypes = new Map([
    ["PERSON", "사람"],
    ["COMPANY", "회사"],
    ["TECHNOLOGY", "기술"],
    ["TOPIC", "주제"],
    ["EVENT", "사건"],
  ]);
  for (const node of peripheral.graphView?.nodes ?? []) {
    nodeTypes.set(node.kindCode, node.kind);
  }
  const failedRequest = status === "error" ? lastRequestRef.current : null;
  const failedTargetName = failedRequest
    ? (nodeCacheRef.current.get(failedRequest.centerId)?.name ?? null)
    : null;

  const locateOnMap = (nodeId: string, relationId?: string) => {
    const map = peripheral.graphView;
    const node = map?.nodes.find((item) => item.id === nodeId);
    const relation = relationId
      ? map?.relations.find((item) => item.id === relationId)
      : undefined;
    if (!map || !node || (relationId && !relation)) {
      setAnnouncement("현재 지도 범위에서는 이 연결을 강조할 수 없습니다.");
      return;
    }
    const visibleNodeIds = relation
      ? [relation.source, relation.target]
      : [nodeId];
    const neededKinds = new Set(
      map.nodes
        .filter((item) => visibleNodeIds.includes(item.id))
        .map((item) => item.kindCode),
    );
    setHiddenKinds((current) =>
      current.filter((kind) => !neededKinds.has(kind)),
    );
    const key = ++focusSequenceRef.current;
    setFocusRequest({
      key,
      nodeIds: visibleNodeIds,
      ...(relationId ? { relationIds: [relationId] } : {}),
    });
    setAnnouncement(
      relation
        ? `지도에서 ${node.name}의 해당 연결을 강조합니다.`
        : `지도에서 ${node.name} 주변 연결을 강조합니다.`,
    );
  };

  const locateManyOnMap = (nodeIds: string[], relationIds: string[]) => {
    const map = peripheral.graphView;
    if (!map) return;
    const validRelations = map.relations.filter((relation) =>
      relationIds.includes(relation.id),
    );
    const visibleNodeIds = [
      ...new Set([
        ...nodeIds.filter((id) => map.nodes.some((node) => node.id === id)),
        ...validRelations.flatMap((relation) => [
          relation.source,
          relation.target,
        ]),
      ]),
    ];
    if (!visibleNodeIds.length) {
      setAnnouncement("현재 지도 범위에서는 추천 대상을 강조할 수 없습니다.");
      return;
    }
    const neededKinds = new Set(
      map.nodes
        .filter((node) => visibleNodeIds.includes(node.id))
        .map((node) => node.kindCode),
    );
    setHiddenKinds((current) =>
      current.filter((kind) => !neededKinds.has(kind)),
    );
    setFocusRequest({
      key: ++focusSequenceRef.current,
      nodeIds: visibleNodeIds,
      relationIds: validRelations.map((relation) => relation.id),
    });
    setAnnouncement(
      `추천 대상 ${nodeIds.length}개와 확인된 연결 경로를 지도에서 강조합니다.`,
    );
  };

  const toggleMapOverview = () => {
    setOverviewRequest({
      key: ++overviewSequenceRef.current,
      action: mapOverviewActive ? "restore" : "show",
    });
  };

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
              focusRequest={focusRequest}
              overviewRequest={overviewRequest}
              onOverviewActiveChange={setMapOverviewActive}
              onIntroComplete={() => setIntroComplete(true)}
              view={peripheral.graphView}
              onPanBoundary={
                isTopicExploration(peripheral.graphView)
                  ? () => undefined
                  : peripheral.trigger
              }
              introStarted={graphReady && !initialLoading}
              introCompleted={introComplete}
              onReady={() => setGraphReady(true)}
              onSelect={selectNode}
              onEvidence={setEvidence}
              onTransitionComplete={finishNodeTransition}
            />
          )}

          {!currentView && status !== "loading" && (
            <div className={styles.controls}>
              <label htmlFor="node-search">대상 검색</label>
              <div className={styles.searchWithTopics}>
                <NodeSearch onSelect={selectNode} />
                <TopicPicker onSelect={selectNode} />
              </div>
            </div>
          )}

          {currentView && currentNode && (
            <>
              <div className={styles.controls}>
                <label htmlFor="node-search">대상 검색</label>
                <div className={styles.searchWithTopics}>
                  <NodeSearch onSelect={selectNode} />
                  <TopicPicker onSelect={selectNode} />
                </div>
                <div className={styles.scopeSummary}>
                  <strong>{currentNode.name} 주변</strong>
                  <button
                    type="button"
                    aria-pressed={mapOverviewActive}
                    onClick={toggleMapOverview}
                  >
                    {mapOverviewActive ? "원래 보기" : "전체 지도 보기"}
                  </button>
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
                  <button
                    type="button"
                    aria-pressed={timeRange === "all"}
                    onClick={() => changeRange("all")}
                  >
                    전체 기간
                  </button>
                </fieldset>
                {allNodesFiltered && (
                  <div className={styles.filterNotice} role="status">
                    <span>유형 필터로 노드가 숨겨져 있습니다.</span>
                    <button type="button" onClick={() => setHiddenKinds([])}>
                      전체 표시
                    </button>
                  </div>
                )}
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
                isTopicExploration(currentView) ? (
                  <TopicPanel
                    key={`${currentView.centerId}:${timeRange}`}
                    timeRange={timeRange}
                    view={currentView}
                    onClose={() => setPanelOpen(false)}
                    onSelect={selectNode}
                    onLocate={locateOnMap}
                    onSelectInsight={selectNodeInsight}
                    onEvidence={setEvidence}
                  />
                ) : (
                  <DetailPanel
                    key={`${currentView.centerId}:${timeRange}:${panelTab}`}
                    timeRange={timeRange}
                    view={currentView}
                    initialTab={panelTab}
                    onClose={() => setPanelOpen(false)}
                    onSelect={selectNode}
                    onLocate={locateOnMap}
                    onLocateMany={locateManyOnMap}
                    onEvidence={setEvidence}
                  />
                )
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

          {!isTopicExploration(peripheral.graphView) &&
            (peripheral.loading ||
              peripheral.error ||
              peripheral.exhausted) && (
              <aside
                className={styles.peripheralStatus}
                aria-label="주변부 조회 상태"
              >
                <PageNotice
                  loading={peripheral.loading}
                  error={peripheral.error}
                  empty={false}
                  additional={Boolean(peripheral.graphView)}
                  retrySuccess={peripheral.retrySuccess}
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
            failedRequest={failedRequest}
            currentCenterId={currentView?.centerId ?? null}
            currentName={currentNode?.name ?? null}
            currentRange={timeRange}
            failedTargetName={failedTargetName}
            defaultCenterId={defaultCenterId}
            onRetry={retry}
            onDefault={openDefault}
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
