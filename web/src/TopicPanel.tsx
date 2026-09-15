import { useEffect, useMemo, useState } from "react";
import styles from "./App.module.css";
import {
  fetchPanelReport,
  type KnowledgeNode,
  type TimeRange,
} from "./data";
import type { TopicExplorationView } from "./topicData";

interface TopicPanelProps {
  view: TopicExplorationView;
  timeRange: TimeRange;
  onClose: () => void;
  onSelect: (nodeId: string) => void;
  onSelectInsight: (nodeId: string) => void;
}

function byName(left: KnowledgeNode, right: KnowledgeNode) {
  return left.name.localeCompare(right.name, "ko");
}

function byRecentEvidence(left: KnowledgeNode, right: KnowledgeNode) {
  return (
    right.activityEvidenceGroupCount - left.activityEvidenceGroupCount ||
    byName(left, right)
  );
}

export function TopicPanel({
  view,
  timeRange,
  onClose,
  onSelect,
  onSelectInsight,
}: TopicPanelProps) {
  const members = useMemo(
    () => view.nodes.filter((node) => node.id !== view.centerId),
    [view],
  );
  const recent = useMemo(
    () =>
      members
        .filter((node) => node.activityEvidenceGroupCount > 0)
        .sort(byRecentEvidence),
    [members],
  );
  const rich = recent.slice(0, 3);
  const richIds = new Set(rich.map((node) => node.id));
  const remainingRecent = recent.filter((node) => !richIds.has(node.id));
  const older = members
    .filter((node) => node.activityEvidenceGroupCount === 0)
    .sort((left, right) =>
      left.kind.localeCompare(right.kind, "ko") || byName(left, right),
    );
  const groups = useMemo(() => {
    const result = new Map<string, KnowledgeNode[]>();
    for (const node of older) {
      const current = result.get(node.kind) ?? [];
      current.push(node);
      result.set(node.kind, current);
    }
    return result;
  }, [older]);
  const [insightTitles, setInsightTitles] = useState<Map<string, string>>(
    new Map(),
  );

  useEffect(() => {
    const controller = new AbortController();
    setInsightTitles(new Map());
    void Promise.all(
      rich.map(async (node) => {
        try {
          const page = await fetchPanelReport(
            node.id,
            timeRange,
            false,
            controller.signal,
          );
          return [node.id, page.items[0]?.title ?? null] as const;
        } catch (error) {
          if (controller.signal.aborted) throw error;
          return [node.id, null] as const;
        }
      }),
    )
      .then((rows) => {
        if (controller.signal.aborted) return;
        setInsightTitles(
          new Map(
            rows.flatMap(([nodeId, title]) =>
              title === null ? [] : [[nodeId, title] as const],
            ),
          ),
        );
      })
      .catch(() => undefined);
    return () => controller.abort();
  }, [rich.map((node) => node.id).join(":"), timeRange]);

  const periodLabel = timeRange === "90d" ? "최근 90일" : "최근 1년";

  return (
    <aside
      className={styles.detailPanel}
      aria-label={`${view.topic.name} 주제 상세 정보`}
    >
      <button
        type="button"
        className={styles.closeButton}
        aria-label="상세 패널 닫기"
        onClick={onClose}
      >
        ×
      </button>
      <header className={styles.panelHeader} data-kind="주제">
        <span className={styles.nodeKind}>
          <i className={styles.nodeTypeDot} />
          주제
        </span>
        <h1>{view.topic.name}</h1>
      </header>
      <div className={styles.topicPanelBody}>
        {view.totalPublicMembershipCount === 0 ? (
          <p className={styles.empty}>아직 공개된 연결 대상이 없습니다.</p>
        ) : (
          <>
            <section>
              <h2>최근 근거가 많은 연결</h2>
              {rich.length > 0 ? (
                <div className={styles.topicRichCards}>
                  {rich.map((node) => {
                    const insightTitle = insightTitles.get(node.id);
                    return (
                      <article
                        key={node.id}
                        className={styles.topicRichCard}
                        data-kind={node.kind}
                      >
                        <button
                          type="button"
                          className={styles.topicMemberButton}
                          onClick={() => onSelect(node.id)}
                        >
                          <span>
                            <i className={styles.nodeTypeDot} />
                            <strong>{node.name}</strong>
                          </span>
                          <small>{node.kind}</small>
                        </button>
                        {insightTitle && (
                          <button
                            type="button"
                            className={styles.topicInsightLink}
                            onClick={() => onSelectInsight(node.id)}
                          >
                            {insightTitle}
                            <span aria-hidden="true"> ›</span>
                          </button>
                        )}
                      </article>
                    );
                  })}
                </div>
              ) : (
                <p className={styles.empty}>
                  {periodLabel}에 새로 확인된 연결 근거가 없습니다.
                </p>
              )}
            </section>

            {remainingRecent.length > 0 && (
              <section>
                <h2>최근 근거가 있는 연결</h2>
                <div className={styles.topicMemberList}>
                  {remainingRecent.map((node) => (
                    <button
                      type="button"
                      key={node.id}
                      onClick={() => onSelect(node.id)}
                    >
                      <span>{node.name}</span>
                      <small>{node.kind}</small>
                    </button>
                  ))}
                </div>
              </section>
            )}

            {older.length > 0 && (
              <section>
                <h2>그 외 연결</h2>
                {[...groups].map(([kind, nodes]) => (
                  <div className={styles.topicMemberGroup} key={kind}>
                    <h3>{kind}</h3>
                    <div className={styles.topicMemberList}>
                      {nodes.map((node) => (
                        <button
                          type="button"
                          key={node.id}
                          onClick={() => onSelect(node.id)}
                        >
                          <span>{node.name}</span>
                        </button>
                      ))}
                    </div>
                  </div>
                ))}
              </section>
            )}
          </>
        )}
      </div>
    </aside>
  );
}
