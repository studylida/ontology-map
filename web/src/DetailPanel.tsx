import {
  type RefObject,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
} from "react";
import styles from "./App.module.css";
import {
  getExplorationRecommendations,
  getKnowledgeNode,
  getRelationEvidence,
  type InsightReport,
  type KnowledgeNode,
  type KnowledgeRelation,
  knowledgeRelations,
  type RelationEvidence,
  type TimeRange,
} from "./data";

type PanelTab = "explore" | "evidence" | "insights";

interface TraceState {
  relationId: string;
  evidenceIndex: number;
}

interface DetailPanelProps {
  centerId: string;
  timeRange: TimeRange;
  onClose: () => void;
  onFollowup: (targetNodeId: string) => void;
  onSelect: (nodeId: string) => void;
}

const panelTabs: readonly { id: PanelTab; label: string }[] = [
  { id: "explore", label: "탐색" },
  { id: "evidence", label: "근거" },
  { id: "insights", label: "인사이트" },
];

const recommendationStatusLabel = {
  confirmedRelation: "확인된 관계",
  connectedPath: "연결 경로 있음",
  unconfirmed: "관계 미확인",
} as const;

function otherNodeId(relation: KnowledgeRelation, centerId: string): string {
  return relation.source === centerId ? relation.target : relation.source;
}

function resolvedInsightEvidence(insight: InsightReport): RelationEvidence[] {
  return insight.evidenceIds
    .map(getRelationEvidence)
    .filter((evidence): evidence is RelationEvidence => Boolean(evidence));
}

function EvidenceTraceView({
  panelRef,
  node,
  target,
  relation,
  evidenceIndex,
  onBack,
  onPrevious,
  onNext,
}: {
  panelRef: RefObject<HTMLElement | null>;
  node: KnowledgeNode;
  target: KnowledgeNode;
  relation: KnowledgeRelation;
  evidenceIndex: number;
  onBack: () => void;
  onPrevious: () => void;
  onNext: () => void;
}) {
  const evidence = relation.evidence[evidenceIndex];
  if (!evidence) return null;
  return (
    <aside
      ref={panelRef}
      className={styles.detailPanel}
      aria-label={`${node.name} 근거 추적`}
    >
      <div className={styles.traceHeader}>
        <button type="button" onClick={onBack}>
          ← 근거로 돌아가기
        </button>
        <span>
          근거 {evidenceIndex + 1} / {relation.evidence.length}
        </span>
      </div>
      <article className={styles.traceView}>
        <span className={styles.traceRelation}>
          {node.name} — {target.name}
        </span>
        <h1>근거 추적</h1>
        <section>
          <h2>이 근거가 뒷받침하는 사실</h2>
          <p>{evidence.claim}</p>
        </section>
        <section>
          <h2>원문 인용</h2>
          <blockquote>{evidence.quote}</blockquote>
        </section>
        <section>
          <h2>출처</h2>
          <dl>
            <dt>문서</dt>
            <dd>{evidence.sourceTitle}</dd>
            <dt>게시자</dt>
            <dd>{evidence.publisher}</dd>
            <dt>게시 시점</dt>
            <dd>{evidence.publishedAt}</dd>
            <dt>원문 위치</dt>
            <dd>{evidence.locator}</dd>
          </dl>
          {evidence.sourceUrl && (
            <a href={evidence.sourceUrl} target="_blank" rel="noreferrer">
              원문 열기 ↗
            </a>
          )}
        </section>
      </article>
      <div className={styles.traceNavigation}>
        <button
          type="button"
          disabled={evidenceIndex === 0}
          onClick={onPrevious}
        >
          ‹ 이전 근거
        </button>
        <button
          type="button"
          disabled={evidenceIndex === relation.evidence.length - 1}
          onClick={onNext}
        >
          다음 근거 ›
        </button>
      </div>
    </aside>
  );
}

function InsightDialog({
  dialogRef,
  nodeName,
  insight,
  evidence,
  expandedEvidence,
  onClose,
  onClosed,
  onToggleEvidence,
  onCollapseAll,
}: {
  dialogRef: RefObject<HTMLDialogElement | null>;
  nodeName: string;
  insight: InsightReport | null;
  evidence: RelationEvidence[];
  expandedEvidence: Set<string>;
  onClose: () => void;
  onClosed: () => void;
  onToggleEvidence: (evidenceId: string) => void;
  onCollapseAll: () => void;
}) {
  return (
    <dialog
      ref={dialogRef}
      className={styles.insightDialog}
      aria-labelledby={insight ? "insight-dialog-title" : undefined}
      onClose={onClosed}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
    >
      {insight && (
        <article>
          <button
            type="button"
            className={styles.dialogClose}
            aria-label="분석 닫기"
            onClick={onClose}
          >
            ×
          </button>
          <span className={styles.dialogEyebrow}>인사이트 · {nodeName}</span>
          <h2 id="insight-dialog-title">{insight.title}</h2>
          <span className={styles.insightEvidenceCount}>
            근거 {evidence.length}개
          </span>
          <p className={styles.dialogSummary}>{insight.summary}</p>
          <section>
            <h3>확인된 사실</h3>
            <p>{insight.verifiedFact}</p>
          </section>
          <section>
            <h3>종합 해석</h3>
            <p>{insight.synthesis}</p>
          </section>
          <section>
            <div className={styles.dialogSectionHeading}>
              <h3>연결 근거</h3>
              {expandedEvidence.size >= 2 && (
                <button type="button" onClick={onCollapseAll}>
                  모두 접기
                </button>
              )}
            </div>
            <div className={styles.dialogEvidenceList}>
              {evidence.map((item) => {
                const expanded = expandedEvidence.has(item.id);
                return (
                  <article key={item.id}>
                    <button
                      type="button"
                      aria-expanded={expanded}
                      onClick={() => onToggleEvidence(item.id)}
                    >
                      <span>
                        <strong>{item.sourceTitle}</strong>
                        <small>
                          {item.publisher} · {item.publishedAt}
                        </small>
                      </span>
                      <span aria-hidden="true">{expanded ? "⌃" : "⌄"}</span>
                    </button>
                    {expanded && (
                      <div className={styles.dialogEvidenceTrace}>
                        <blockquote>{item.quote}</blockquote>
                        <span>{item.locator}</span>
                        {item.sourceUrl && (
                          <a
                            href={item.sourceUrl}
                            target="_blank"
                            rel="noreferrer"
                          >
                            원문 열기 ↗
                          </a>
                        )}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          </section>
          <section className={styles.caveat}>
            <h3>해석 시 유의점</h3>
            <p>{insight.caveat}</p>
          </section>
        </article>
      )}
    </dialog>
  );
}

export function DetailPanel({
  centerId,
  timeRange,
  onClose,
  onFollowup,
  onSelect,
}: DetailPanelProps) {
  const [panelTab, setPanelTab] = useState<PanelTab>("explore");
  const [expandedRelationId, setExpandedRelationId] = useState<string | null>(
    null,
  );
  const [traceState, setTraceState] = useState<TraceState | null>(null);
  const [selectedInsight, setSelectedInsight] = useState<InsightReport | null>(
    null,
  );
  const [expandedInsightEvidence, setExpandedInsightEvidence] = useState(
    () => new Set<string>(),
  );
  const panelRef = useRef<HTMLElement>(null);
  const savedScrollTopRef = useRef(0);
  const dialogRef = useRef<HTMLDialogElement>(null);
  const insightTriggerRef = useRef<HTMLButtonElement>(null);
  const panelTabsId = useId();
  const node = getKnowledgeNode(centerId);
  const recommendations = useMemo(
    () => getExplorationRecommendations(centerId, timeRange),
    [centerId, timeRange],
  );
  const related = useMemo(
    () =>
      knowledgeRelations.filter(
        (relation) =>
          relation.source === centerId || relation.target === centerId,
      ),
    [centerId],
  );

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (selectedInsight && !dialog.open) dialog.showModal();
    if (!selectedInsight && dialog.open) dialog.close();
  }, [selectedInsight]);

  const closeInsight = () => {
    if (dialogRef.current?.open) dialogRef.current.close();
    else setSelectedInsight(null);
  };

  const openTrace = (relationId: string, evidenceIndex: number) => {
    savedScrollTopRef.current = panelRef.current?.scrollTop ?? 0;
    setTraceState({ relationId, evidenceIndex });
    if (panelRef.current) panelRef.current.scrollTop = 0;
  };

  const closeTrace = () => {
    setTraceState(null);
    window.requestAnimationFrame(() => {
      if (panelRef.current)
        panelRef.current.scrollTop = savedScrollTopRef.current;
    });
  };

  const toggleInsightEvidence = (evidenceId: string) => {
    setExpandedInsightEvidence((current) => {
      const next = new Set(current);
      if (next.has(evidenceId)) next.delete(evidenceId);
      else next.add(evidenceId);
      return next;
    });
  };

  const handleTabKeyDown = (
    event: React.KeyboardEvent<HTMLButtonElement>,
    currentTab: PanelTab,
  ) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const currentIndex = panelTabs.findIndex((tab) => tab.id === currentTab);
    const direction = event.key === "ArrowRight" ? 1 : -1;
    const nextIndex =
      (currentIndex + direction + panelTabs.length) % panelTabs.length;
    const nextTab = panelTabs[nextIndex];
    if (!nextTab) return;
    setPanelTab(nextTab.id);
    document.getElementById(`${panelTabsId}-${nextTab.id}-tab`)?.focus();
  };

  const traceRelation = traceState
    ? related.find((item) => item.id === traceState.relationId)
    : undefined;
  if (traceState && traceRelation) {
    return (
      <EvidenceTraceView
        panelRef={panelRef}
        node={node}
        target={getKnowledgeNode(otherNodeId(traceRelation, centerId))}
        relation={traceRelation}
        evidenceIndex={traceState.evidenceIndex}
        onBack={closeTrace}
        onPrevious={() =>
          setTraceState({
            ...traceState,
            evidenceIndex: traceState.evidenceIndex - 1,
          })
        }
        onNext={() =>
          setTraceState({
            ...traceState,
            evidenceIndex: traceState.evidenceIndex + 1,
          })
        }
      />
    );
  }

  const selectedInsightEvidence = selectedInsight
    ? resolvedInsightEvidence(selectedInsight)
    : [];

  return (
    <>
      <aside
        ref={panelRef}
        className={styles.detailPanel}
        aria-label={`${node.name} 상세 정보`}
      >
        <button
          type="button"
          className={styles.closeButton}
          aria-label="상세 패널 닫기"
          onClick={onClose}
        >
          ×
        </button>
        <header className={styles.panelHeader} data-kind={node.kind}>
          <span className={styles.nodeKind}>
            <i className={styles.nodeTypeDot} />
            {node.kind}
          </span>
          <h1>{node.name}</h1>
          <p>{node.context}</p>
        </header>

        <div
          className={styles.panelTabs}
          role="tablist"
          aria-label="상세 정보 보기"
        >
          {panelTabs.map((tab) => (
            <button
              type="button"
              id={`${panelTabsId}-${tab.id}-tab`}
              key={tab.id}
              role="tab"
              tabIndex={panelTab === tab.id ? 0 : -1}
              aria-selected={panelTab === tab.id}
              aria-controls={`${panelTabsId}-${tab.id}-panel`}
              onClick={() => setPanelTab(tab.id)}
              onKeyDown={(event) => handleTabKeyDown(event, tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {panelTab === "explore" && (
          <div
            id={`${panelTabsId}-explore-panel`}
            role="tabpanel"
            aria-labelledby={`${panelTabsId}-explore-tab`}
            className={styles.tabPanel}
          >
            <div className={styles.sectionHeading}>
              <h2>이어서 탐색</h2>
              <span>{recommendations.length}</span>
            </div>
            <div className={styles.recommendations}>
              {recommendations.map((recommendation) => (
                <button
                  type="button"
                  key={recommendation.node.id}
                  className={styles.recommendationCard}
                  data-kind={recommendation.node.kind}
                  onClick={() => onSelect(recommendation.node.id)}
                >
                  <span className={styles.cardTitle}>
                    <span>
                      <i className={styles.nodeTypeDot} />
                      {recommendation.node.name}
                    </span>
                    <small>{recommendation.node.kind}</small>
                  </span>
                  <span className={styles.cardReason}>
                    {recommendation.reason}
                  </span>
                  <span className={styles.cardMeta}>
                    {recommendationStatusLabel[recommendation.status]}
                    {recommendation.evidenceGroupCount
                      ? ` · 독립 근거 ${recommendation.evidenceGroupCount}개`
                      : ""}
                  </span>
                  <span className={styles.cardArrow} aria-hidden="true">
                    ›
                  </span>
                </button>
              ))}
            </div>

            <section className={styles.followupSection}>
              <h2>후속 질문</h2>
              <div className={styles.followups}>
                {node.followups.map((followup) => (
                  <button
                    type="button"
                    key={followup.id}
                    onClick={() => onFollowup(followup.targetNodeId)}
                  >
                    <span>{followup.text}</span>
                    <span aria-hidden="true">›</span>
                  </button>
                ))}
              </div>
            </section>
          </div>
        )}

        {panelTab === "evidence" && (
          <div
            id={`${panelTabsId}-evidence-panel`}
            role="tabpanel"
            aria-labelledby={`${panelTabsId}-evidence-tab`}
            className={styles.tabPanel}
          >
            <div className={styles.sectionHeading}>
              <h2>확인된 관계</h2>
              <span>{related.length}</span>
            </div>
            {related.length ? (
              <div className={styles.relationAccordion}>
                {related.map((relation) => {
                  const target = getKnowledgeNode(
                    otherNodeId(relation, centerId),
                  );
                  const expanded = expandedRelationId === relation.id;
                  return (
                    <article
                      key={relation.id}
                      className={styles.relationCard}
                      data-conflict={relation.conflict || undefined}
                    >
                      <button
                        type="button"
                        className={styles.relationToggle}
                        aria-expanded={expanded}
                        onClick={() =>
                          setExpandedRelationId(expanded ? null : relation.id)
                        }
                      >
                        <span>
                          <strong>{target.name}</strong>
                          <small>
                            {relation.label} · 독립 근거{" "}
                            {relation.evidenceGroupCount}개
                            {relation.conflict ? " · 충돌 있음" : ""}
                          </small>
                        </span>
                        <span aria-hidden="true">{expanded ? "⌃" : "⌄"}</span>
                      </button>
                      {expanded && (
                        <div className={styles.relationEvidence}>
                          {relation.evidence.map((evidence, index) => (
                            <article
                              key={evidence.id}
                              className={styles.evidencePreview}
                            >
                              <span className={styles.evidenceStance}>
                                {evidence.stance === "conflict"
                                  ? "충돌"
                                  : "지지"}
                              </span>
                              <p>{evidence.claim}</p>
                              <small>
                                {evidence.sourceTitle} · {evidence.publishedAt}
                              </small>
                              <blockquote>{evidence.quote}</blockquote>
                              <button
                                type="button"
                                onClick={() => openTrace(relation.id, index)}
                              >
                                근거 추적 보기
                              </button>
                            </article>
                          ))}
                        </div>
                      )}
                    </article>
                  );
                })}
              </div>
            ) : (
              <p className={styles.empty}>현재 공개된 관계가 없습니다.</p>
            )}

            <section className={styles.nodeFacts}>
              <h2>확인된 사실</h2>
              <p>{node.claim}</p>
            </section>
          </div>
        )}

        {panelTab === "insights" && (
          <div
            id={`${panelTabsId}-insights-panel`}
            role="tabpanel"
            aria-labelledby={`${panelTabsId}-insights-tab`}
            className={styles.tabPanel}
          >
            <div className={styles.sectionHeading}>
              <h2>종합 인사이트</h2>
              <span>{node.insights.length}</span>
            </div>
            {node.insights.length ? (
              <ul className={styles.insightList}>
                {node.insights.map((insight) => (
                  <li key={insight.id}>
                    <button
                      type="button"
                      onClick={(event) => {
                        insightTriggerRef.current = event.currentTarget;
                        setExpandedInsightEvidence(new Set());
                        setSelectedInsight(insight);
                      }}
                    >
                      <span>
                        <strong>{insight.title}</strong>
                        <small>근거 {insight.evidenceIds.length}개</small>
                      </span>
                      <span aria-hidden="true">›</span>
                    </button>
                  </li>
                ))}
              </ul>
            ) : (
              <p className={styles.insightEmpty}>
                이 노드의 종합 분석 데모는 아직 준비되지 않았습니다.
              </p>
            )}
          </div>
        )}
      </aside>

      <InsightDialog
        dialogRef={dialogRef}
        nodeName={node.name}
        insight={selectedInsight}
        evidence={selectedInsightEvidence}
        expandedEvidence={expandedInsightEvidence}
        onClose={closeInsight}
        onClosed={() => {
          setSelectedInsight(null);
          setExpandedInsightEvidence(new Set());
          insightTriggerRef.current?.focus();
        }}
        onToggleEvidence={toggleInsightEvidence}
        onCollapseAll={() => setExpandedInsightEvidence(new Set())}
      />
    </>
  );
}
