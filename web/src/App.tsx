import { useEffect, useId, useMemo, useState } from "react";
import styles from "./App.module.css";
import {
  buildKnowledgeView,
  getKnowledgeNode,
  isKnownNode,
  type KnowledgeNode,
  knowledgeRelations,
  searchKnowledgeNodes,
  type TimeRange,
} from "./data";
import { GraphCanvas } from "./GraphCanvas";

interface LocationState {
  centerId: string;
  range: TimeRange;
  query: string;
}

const maxTrailLength = 4;

function appendTrail(trail: string[], nodeId: string): string[] {
  if (trail.at(-1) === nodeId) return trail;
  return [...trail, nodeId].slice(-maxTrailLength);
}

function readLocation(): LocationState {
  const params = new URLSearchParams(window.location.search);
  const candidateCenter = params.get("center") ?? "sk";
  const candidateRange = params.get("range");
  return {
    centerId: isKnownNode(candidateCenter) ? candidateCenter : "sk",
    range: candidateRange === "1y" ? "1y" : "90d",
    query: params.get("q") ?? "",
  };
}

function writeLocation(
  state: LocationState,
  mode: "push" | "replace" = "replace",
) {
  const params = new URLSearchParams();
  params.set("center", state.centerId);
  params.set("range", state.range);
  if (state.query) params.set("q", state.query);
  window.history[`${mode}State`](
    {},
    "",
    `${window.location.pathname}?${params.toString()}`,
  );
}

function SearchCandidate({
  node,
  active,
  onSelect,
}: {
  node: KnowledgeNode;
  active: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      role="option"
      aria-selected={active}
      className={styles.searchCandidate}
      onMouseDown={(event) => event.preventDefault()}
      onClick={onSelect}
    >
      <span className={styles.candidateMain}>
        <strong>{node.name}</strong>
        <span>{node.kind}</span>
      </span>
      <span>{node.searchReason}</span>
    </button>
  );
}

export function App() {
  const initial = useMemo(readLocation, []);
  const [centerId, setCenterId] = useState(initial.centerId);
  const [trail, setTrail] = useState([initial.centerId]);
  const [timeRange, setTimeRange] = useState<TimeRange>(initial.range);
  const [query, setQuery] = useState(initial.query);
  const [panelOpen, setPanelOpen] = useState(true);
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const [searchFocused, setSearchFocused] = useState(false);
  const [activeCandidate, setActiveCandidate] = useState(0);
  const [announcement, setAnnouncement] = useState(
    "SK하이닉스를 중심으로 지식맵을 열었습니다.",
  );
  const searchListId = useId();
  const node = getKnowledgeNode(centerId);
  const view = useMemo(() => buildKnowledgeView(centerId), [centerId]);
  const candidates = useMemo(() => searchKnowledgeNodes(query), [query]);
  const directCount = view.nodes.filter(
    (item) => item.tier === "direct",
  ).length;
  const twoHopCount = view.nodes.filter(
    (item) => item.tier === "twoHop",
  ).length;
  const related = knowledgeRelations.filter(
    (relation) => relation.source === centerId || relation.target === centerId,
  );

  useEffect(() => {
    writeLocation(initial);
    const onPopState = () => {
      const next = readLocation();
      setCenterId(next.centerId);
      setTimeRange(next.range);
      setQuery(next.query);
      setTrail((current) => {
        const index = current.lastIndexOf(next.centerId);
        return index >= 0
          ? current.slice(0, index + 1)
          : appendTrail(current, next.centerId);
      });
    };
    window.addEventListener("popstate", onPopState);
    return () => window.removeEventListener("popstate", onPopState);
  }, [initial]);

  const selectNode = (
    nextId: string,
    nextQuery = query,
    trailIndex?: number,
  ) => {
    const target = getKnowledgeNode(nextId);
    setCenterId(target.id);
    setTrail((current) =>
      trailIndex === undefined
        ? appendTrail(current, target.id)
        : current.slice(0, trailIndex + 1),
    );
    setQuery(nextQuery);
    setPanelOpen(true);
    setEvidenceOpen(false);
    writeLocation(
      { centerId: target.id, range: timeRange, query: nextQuery },
      "push",
    );
    setAnnouncement(`${target.name} 중심으로 이동했습니다.`);
  };

  const changeRange = (range: TimeRange) => {
    setTimeRange(range);
    writeLocation({ centerId, range, query });
    setAnnouncement(
      range === "90d"
        ? "최근 90일 관측 활동량을 표시합니다."
        : "최근 1년 전체 관측 활동량을 표시합니다.",
    );
  };

  const chooseCandidate = (candidate: KnowledgeNode) => {
    selectNode(candidate.id, candidate.name);
    setSearchFocused(false);
  };

  const handleFollowup = (targetNodeId: string) => {
    if (targetNodeId === centerId) {
      setAnnouncement(
        "현재 중심과 상세 패널을 유지합니다. 추가 모델 호출은 실행하지 않았습니다.",
      );
      return;
    }
    selectNode(targetNodeId);
  };

  return (
    <main className={styles.app}>
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
              const trailNode = getKnowledgeNode(trailId);
              const current = index === trail.length - 1;
              return (
                // biome-ignore lint/suspicious/noArrayIndexKey: 같은 node가 경로에 반복될 수 있고 항목 내부 상태가 없습니다.
                <li className={styles.trailItem} key={`${trailId}-${index}`}>
                  {index > 0 && (
                    <span className={styles.trailSeparator} aria-hidden="true">
                      /
                    </span>
                  )}
                  {current ? (
                    <span aria-current="page" title={trailNode.name}>
                      {trailNode.name}
                    </span>
                  ) : (
                    <button
                      type="button"
                      title={trailNode.name}
                      aria-label={`탐색 경로에서 ${trailNode.name} 선택`}
                      onClick={() => selectNode(trailId, query, index)}
                    >
                      {trailNode.name}
                    </button>
                  )}
                </li>
              );
            })}
          </ol>
        </nav>
      </header>

      <section className={styles.workspace}>
        <GraphCanvas
          centerId={centerId}
          timeRange={timeRange}
          onSelect={selectNode}
        />

        <div className={styles.controls}>
          <label htmlFor="node-search">중심 NODE 검색</label>
          <div className={styles.searchBox}>
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="10.5" cy="10.5" r="6.5" />
              <path d="m15.5 15.5 5 5" />
            </svg>
            <input
              id="node-search"
              type="search"
              role="combobox"
              aria-expanded={searchFocused && candidates.length > 0}
              aria-controls={searchListId}
              aria-autocomplete="list"
              aria-activedescendant={
                searchFocused && candidates[activeCandidate]
                  ? `${searchListId}-${candidates[activeCandidate].id}`
                  : undefined
              }
              value={query}
              placeholder="회사, 사람, 기술 또는 주제 검색"
              onFocus={() => setSearchFocused(true)}
              onBlur={() => setSearchFocused(false)}
              onChange={(event) => {
                setQuery(event.target.value);
                setActiveCandidate(0);
                writeLocation({
                  centerId,
                  range: timeRange,
                  query: event.target.value,
                });
              }}
              onKeyDown={(event) => {
                if (!candidates.length) return;
                if (event.key === "ArrowDown") {
                  event.preventDefault();
                  setActiveCandidate(
                    (current) => (current + 1) % candidates.length,
                  );
                } else if (event.key === "ArrowUp") {
                  event.preventDefault();
                  setActiveCandidate(
                    (current) =>
                      (current - 1 + candidates.length) % candidates.length,
                  );
                } else if (event.key === "Enter") {
                  event.preventDefault();
                  const candidate = candidates[activeCandidate];
                  if (candidate) chooseCandidate(candidate);
                } else if (event.key === "Escape") {
                  setSearchFocused(false);
                }
              }}
            />
          </div>
          {searchFocused && candidates.length > 0 && (
            <div
              id={searchListId}
              role="listbox"
              className={styles.searchResults}
            >
              {candidates.map((candidate, index) => (
                <div id={`${searchListId}-${candidate.id}`} key={candidate.id}>
                  <SearchCandidate
                    node={candidate}
                    active={index === activeCandidate}
                    onSelect={() => chooseCandidate(candidate)}
                  />
                </div>
              ))}
            </div>
          )}
          <p>
            직접 이웃 {directCount}개 · 중요한 2단계 이웃 {twoHopCount}개
          </p>

          <fieldset className={styles.rangeControl}>
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
              전체 1년
            </button>
          </fieldset>
        </div>

        <aside className={styles.legend} aria-label="지식맵 범례">
          <h2>NODE 유형</h2>
          <div className={styles.nodeTypes}>
            {(["사람", "회사", "기술", "주제", "사건"] as const).map((kind) => (
              <span key={kind} data-kind={kind}>
                <i />
                {kind}
              </span>
            ))}
          </div>
          <div className={styles.legendLine}>
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
        </aside>

        {panelOpen ? (
          <aside
            className={styles.detailPanel}
            aria-label={`${node.name} 상세 정보`}
          >
            <button
              type="button"
              className={styles.closeButton}
              aria-label="상세 패널 닫기"
              onClick={() => setPanelOpen(false)}
            >
              ×
            </button>
            <span className={styles.eyebrow}>현재 중심 · {node.kind}</span>
            <h1>{node.name}</h1>
            <p className={styles.context}>{node.context}</p>

            <section>
              <h2>근거 확인된 관계</h2>
              {related.length ? (
                <ul className={styles.relationList}>
                  {related.map((relation) => {
                    const otherId =
                      relation.source === centerId
                        ? relation.target
                        : relation.source;
                    return (
                      <li key={relation.id}>
                        <button
                          type="button"
                          onClick={() => selectNode(otherId)}
                        >
                          {getKnowledgeNode(otherId).name}
                        </button>
                        <span>
                          {relation.label} · 독립 근거{" "}
                          {relation.evidenceGroupCount}개
                          {relation.conflict ? " · 충돌" : ""}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className={styles.empty}>현재 공개된 Relation이 없습니다.</p>
              )}
            </section>

            <section>
              <h2>원자적 Claim</h2>
              <p>{node.claim}</p>
            </section>

            <section>
              <h2>출처</h2>
              <button
                type="button"
                className={styles.evidenceButton}
                aria-expanded={evidenceOpen}
                onClick={() => setEvidenceOpen((open) => !open)}
              >
                <span>
                  <strong>{node.evidence.sourceTitle}</strong>
                  <small>
                    {node.evidence.publisher} · {node.evidence.publishedAt}
                  </small>
                </span>
                <span>{evidenceOpen ? "접기" : "Evidence Trace"}</span>
              </button>
              {evidenceOpen && (
                <div className={styles.evidenceTrace}>
                  <span>원문 인용</span>
                  <blockquote>{node.evidence.quote}</blockquote>
                  <dl>
                    <dt>원문 위치</dt>
                    <dd>{node.evidence.locator}</dd>
                    <dt>게시 시점</dt>
                    <dd>{node.evidence.publishedAt}</dd>
                  </dl>
                </div>
              )}
            </section>

            <section>
              <h2>후속 질문</h2>
              <div className={styles.followups}>
                {node.followups.map((followup) => (
                  <button
                    type="button"
                    key={followup.id}
                    onClick={() => handleFollowup(followup.targetNodeId)}
                  >
                    <span>{followup.text}</span>
                    <small>
                      대상 · {getKnowledgeNode(followup.targetNodeId).name}
                    </small>
                  </button>
                ))}
              </div>
            </section>
          </aside>
        ) : (
          <button
            type="button"
            className={styles.openPanel}
            onClick={() => setPanelOpen(true)}
          >
            상세 패널 열기
          </button>
        )}
      </section>
      <div className={styles.liveRegion} aria-live="polite">
        {announcement}
      </div>
    </main>
  );
}
