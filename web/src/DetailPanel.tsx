import styles from "./App.module.css";
import type { ExplorationView } from "./data";

interface DetailPanelProps {
  view: ExplorationView;
  onClose: () => void;
  onFollowup: (targetNodeId: string) => void;
  onSelect: (nodeId: string) => void;
}

const recommendationStatusLabel = {
  confirmedRelation: "확인된 관계",
  connectedPath: "연결 경로 있음",
  ambient: "새 탐색 출발점",
} as const;

export function DetailPanel({
  view,
  onClose,
  onFollowup,
  onSelect,
}: DetailPanelProps) {
  const center = view.nodes.find((node) => node.id === view.centerId);
  if (!center) return null;

  const nodesById = new Map(view.nodes.map((node) => [node.id, node]));
  const related = view.relations.filter(
    (relation) =>
      relation.source === view.centerId || relation.target === view.centerId,
  );

  return (
    <aside
      className={styles.detailPanel}
      aria-label={`${center.name} 상세 정보`}
    >
      <button
        type="button"
        className={styles.closeButton}
        aria-label="상세 패널 닫기"
        onClick={onClose}
      >
        ×
      </button>
      <header className={styles.panelHeader} data-kind={center.kind}>
        <span className={styles.nodeKind}>
          <i className={styles.nodeTypeDot} />
          {center.kind}
        </span>
        <h1>{center.name}</h1>
        <p>{view.context}</p>
      </header>

      <div className={styles.tabPanel}>
        <div className={styles.sectionHeading}>
          <h2>이어서 탐색</h2>
          <span>{view.recommendations.length}</span>
        </div>
        {view.recommendations.length ? (
          <div className={styles.recommendations}>
            {view.recommendations.map((recommendation) => (
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
        ) : (
          <p className={styles.empty}>추천할 탐색 대상이 없습니다.</p>
        )}

        <section className={styles.followupSection}>
          <h2>후속 질문</h2>
          {view.followups.length ? (
            <div className={styles.followups}>
              {view.followups.map((followup) => (
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
          ) : (
            <p className={styles.empty}>표시할 후속 질문이 없습니다.</p>
          )}
        </section>

        <section className={styles.followupSection}>
          <div className={styles.sectionHeading}>
            <h2>확인된 관계</h2>
            <span>{related.length}</span>
          </div>
          {related.length ? (
            <div className={styles.relationAccordion}>
              {related.map((relation) => {
                const targetId =
                  relation.source === view.centerId
                    ? relation.target
                    : relation.source;
                const target = nodesById.get(targetId);
                return (
                  <article
                    key={relation.id}
                    className={styles.relationCard}
                    data-conflict={relation.conflict || undefined}
                  >
                    <div className={styles.relationToggle}>
                      <span>
                        <strong>{target?.name ?? targetId}</strong>
                        <small>
                          {relation.label} · 독립 근거{" "}
                          {relation.evidenceGroupCount}개
                          {relation.conflict ? " · 충돌 있음" : ""}
                        </small>
                      </span>
                    </div>
                  </article>
                );
              })}
            </div>
          ) : (
            <p className={styles.empty}>현재 공개된 관계가 없습니다.</p>
          )}
        </section>
      </div>
    </aside>
  );
}
