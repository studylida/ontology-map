import { useCallback, useId, useState } from "react";
import styles from "./App.module.css";
import {
  fetchInsight,
  fetchNodeInsights,
  type InsightItem,
  type TimeRange,
} from "./data";
import { PageNotice, TraceContent, useModalDialog } from "./RelationPanel";
import { useCursorPage } from "./useCursorPage";

const roles = {
  KEY_CLAIM: "확인된 사실",
  SUPPORTING_CLAIM: "보조 근거",
  CONTRASTING_CLAIM: "엇갈리는 근거",
};

function InsightDialog({
  selected,
  onClose,
}: {
  selected: InsightItem;
  onClose: () => void;
}) {
  const dialogRef = useModalDialog(onClose);
  const titleId = useId();
  const page = useCursorPage(selected.id, fetchInsight);
  const insight = page.items[0];
  const [expanded, setExpanded] = useState(new Set<string>());
  return (
    <dialog
      ref={dialogRef}
      className={styles.insightDialog}
      aria-labelledby={titleId}
      onCancel={onClose}
    >
      <article>
        <button
          type="button"
          className={styles.dialogClose}
          aria-label="분석 닫기"
          onClick={onClose}
        >
          ×
        </button>
        <span className={styles.dialogEyebrow}>인사이트</span>
        <h2 id={titleId}>{selected.title}</h2>
        <PageNotice {...page} empty={!insight} onRetry={page.retry} />
        {insight && (
          <>
            <span className={styles.insightEvidenceCount}>
              독립 근거 {insight.evidenceGroupCount}개
            </span>
            <p className={styles.dialogSummary}>{insight.summary}</p>
            <section>
              <h3>확인된 사실</h3>
              {insight.claims
                .filter((c) => c.role === "KEY_CLAIM")
                .map((c) => (
                  <p key={c.id}>{c.text}</p>
                ))}
            </section>
            <section>
              <h3>종합 해석</h3>
              <p>{insight.synthesis}</p>
            </section>
            <section>
              <div className={styles.dialogSectionHeading}>
                <h3>연결 근거</h3>
                {expanded.size >= 2 && (
                  <button type="button" onClick={() => setExpanded(new Set())}>
                    모두 접기
                  </button>
                )}
              </div>
              <div className={styles.dialogEvidenceList}>
                {insight.claims.map((claim) => (
                  <article key={claim.id}>
                    <button
                      type="button"
                      aria-expanded={expanded.has(claim.id)}
                      aria-controls={`${titleId}-${claim.id}`}
                      onClick={() =>
                        setExpanded((current) => {
                          const next = new Set(current);
                          if (next.has(claim.id)) next.delete(claim.id);
                          else next.add(claim.id);
                          return next;
                        })
                      }
                    >
                      <span>
                        <small>{roles[claim.role]}</small>
                        {claim.text}
                      </span>
                      <span>{expanded.has(claim.id) ? "접기" : "펼치기"}</span>
                    </button>
                    <div
                      id={`${titleId}-${claim.id}`}
                      hidden={!expanded.has(claim.id)}
                      className={styles.dialogEvidenceTrace}
                    >
                      {claim.traces.map((trace) => (
                        <div key={trace.key}>
                          <TraceContent trace={trace} />
                        </div>
                      ))}
                    </div>
                  </article>
                ))}
              </div>
            </section>
            <section>
              <h3>해석 시 유의점</h3>
              <p>{insight.caveat}</p>
            </section>
          </>
        )}
      </article>
    </dialog>
  );
}

export function InsightPanel({
  nodeId,
  timeRange,
}: {
  nodeId: string;
  timeRange: TimeRange;
}) {
  const fetchPage = useCallback(
    (id: string, _cursor: string | null, signal: AbortSignal) =>
      fetchNodeInsights(id, timeRange, signal),
    [timeRange],
  );
  const page = useCursorPage(nodeId, fetchPage);
  const [selected, setSelected] = useState<InsightItem | null>(null);
  return (
    <>
      <div className={styles.sectionHeading}>
        <h2>인사이트</h2>
        <span>{page.items.length}</span>
      </div>
      <PageNotice {...page} empty={!page.items.length} onRetry={page.retry} />
      <div className={styles.insightList}>
        {page.items.map((item) => (
          <button type="button" key={item.id} onClick={() => setSelected(item)}>
            <span>
              {item.title}
              <small>독립 근거 {item.evidenceGroupCount}개</small>
            </span>
            <span aria-hidden="true">›</span>
          </button>
        ))}
      </div>
      {selected && (
        <InsightDialog
          key={selected.id}
          selected={selected}
          onClose={() => setSelected(null)}
        />
      )}
    </>
  );
}
