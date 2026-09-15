import { useEffect, useMemo, useState } from "react";
import styles from "./App.module.css";
import {
  fetchPanelReport,
  type KnowledgeNode,
  type KnowledgeRelation,
  type TimeRange,
} from "./data";
import type { EvidenceSelection } from "./RelationPanel";
import topicStyles from "./Topic.module.css";
import type { TopicExplorationView } from "./topicData";

interface TopicPanelProps {
  view: TopicExplorationView;
  timeRange: TimeRange;
  onClose: () => void;
  onSelect: (nodeId: string) => void;
  onSelectInsight: (nodeId: string) => void;
  onEvidence: (selection: EvidenceSelection) => void;
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

function MemberActions({
  node,
  relation,
  topicName,
  onSelect,
  onEvidence,
}: {
  node: KnowledgeNode;
  relation: KnowledgeRelation | undefined;
  topicName: string;
  onSelect: (nodeId: string) => void;
  onEvidence: (selection: EvidenceSelection) => void;
}) {
  return (
    <span>
      <button type="button" onClick={() => onSelect(node.id)}>
        Node 보기
      </button>
      {relation && (
        <button
          type="button"
          onClick={() =>
            onEvidence({
              id: relation.id,
              label: `${node.name} · ${relation.label} · ${topicName}`,
            })
          }
        >
          관계 근거
        </button>
      )}
    </span>
  );
}

export function TopicPanel({
  view,
  timeRange,
  onClose,
  onSelect,
  onSelectInsight,
  onEvidence,
}: TopicPanelProps) {
  const { rich, remainingRecent, older, groups, relationByMember } =
    useMemo(() => {
      const members = view.nodes.filter((node) => node.id !== view.centerId);
      const recent = members
        .filter((node) => node.activityEvidenceGroupCount > 0)
        .sort(byRecentEvidence);
      const richNodes = recent.slice(0, 3);
      const richIds = new Set(richNodes.map((node) => node.id));
      const olderNodes = members
        .filter((node) => node.activityEvidenceGroupCount === 0)
        .sort(
          (left, right) =>
            left.kind.localeCompare(right.kind, "ko") || byName(left, right),
        );
      const grouped = new Map<string, KnowledgeNode[]>();
      for (const node of olderNodes) {
        const current = grouped.get(node.kind) ?? [];
        current.push(node);
        grouped.set(node.kind, current);
      }
      const relations = new Map<string, KnowledgeRelation>();
      for (const relation of view.relations) {
        const memberId =
          relation.source === view.centerId ? relation.target : relation.source;
        relations.set(memberId, relation);
      }
      return {
        rich: richNodes,
        remainingRecent: recent.filter((node) => !richIds.has(node.id)),
        older: olderNodes,
        groups: grouped,
        relationByMember: relations,
      };
    }, [view]);
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
  }, [rich, timeRange]);

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
      <div className={topicStyles.topicPanelBody}>
        {view.totalPublicMembershipCount === 0 ? (
          <p className={styles.empty}>아직 공개된 연결 대상이 없습니다.</p>
        ) : (
          <>
            <section>
              <h2>최근 근거가 많은 연결</h2>
              {rich.length > 0 ? (
                <div className={topicStyles.topicRichCards}>
                  {rich.map((node) => {
                    const insightTitle = insightTitles.get(node.id);
                    return (
                      <article
                        key={node.id}
                        className={topicStyles.topicRichCard}
                        data-kind={node.kind}
                      >
                        <button
                          type="button"
                          className={topicStyles.topicMemberButton}
                          onClick={() => onSelect(node.id)}
                        >
                          <span>
                            <i className={styles.nodeTypeDot} />
                            <strong>{node.name}</strong>
                          </span>
                          <small>{node.kind}</small>
                        </button>
                        <MemberActions
                          node={node}
                          relation={relationByMember.get(node.id)}
                          topicName={view.topic.name}
                          onSelect={onSelect}
                          onEvidence={onEvidence}
                        />
                        {insightTitle && (
                          <button
                            type="button"
                            className={topicStyles.topicInsightLink}
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
                <div className={topicStyles.topicMemberList}>
                  {remainingRecent.map((node) => (
                    <article key={node.id}>
                      <button type="button" onClick={() => onSelect(node.id)}>
                        <span>{node.name}</span>
                        <small>{node.kind}</small>
                      </button>
                      <MemberActions
                        node={node}
                        relation={relationByMember.get(node.id)}
                        topicName={view.topic.name}
                        onSelect={onSelect}
                        onEvidence={onEvidence}
                      />
                    </article>
                  ))}
                </div>
              </section>
            )}

            {older.length > 0 && (
              <section>
                <h2>그 외 연결</h2>
                {[...groups].map(([kind, nodes]) => (
                  <div className={topicStyles.topicMemberGroup} key={kind}>
                    <h3>{kind}</h3>
                    <div className={topicStyles.topicMemberList}>
                      {nodes.map((node) => (
                        <article key={node.id}>
                          <button
                            type="button"
                            onClick={() => onSelect(node.id)}
                          >
                            <span>{node.name}</span>
                          </button>
                          <MemberActions
                            node={node}
                            relation={relationByMember.get(node.id)}
                            topicName={view.topic.name}
                            onSelect={onSelect}
                            onEvidence={onEvidence}
                          />
                        </article>
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
