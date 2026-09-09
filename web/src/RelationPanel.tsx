import { useEffect, useEffectEvent, useId, useRef } from "react";
import styles from "./App.module.css";
import {
  type APIRequestError,
  fetchNodeRelations,
  fetchRelationEvidence,
  relationPathLabel,
  type SourceTrace,
} from "./data";
import { useCursorPage } from "./useCursorPage";

export interface EvidenceSelection {
  id: string;
  label: string;
}

export function PageNotice({
  loading,
  error,
  empty,
  onRetry,
}: {
  loading: boolean;
  error: APIRequestError | null;
  empty: boolean;
  onRetry: () => void;
}) {
  if (loading) return <p role="status">불러오는 중입니다.</p>;
  if (error) {
    const message =
      error.status === 404
        ? "공개된 자료를 찾을 수 없습니다."
        : error.status === 422
          ? "조회 요청을 확인할 수 없습니다. 다시 선택해 주세요."
          : error.status === 503
            ? error.code === "PANEL_NOT_READY"
              ? "이 기간에 공개할 수 있는 자료가 아직 준비되지 않았습니다."
              : "공개 자료를 준비하고 있습니다."
            : "자료를 불러오지 못했습니다.";
    return (
      <div role="alert">
        <p>{message}</p>
        {error.retryable && (
          <button type="button" onClick={onRetry}>
            다시 시도
          </button>
        )}
      </div>
    );
  }
  return empty ? (
    <p className={styles.empty} role="status">
      현재 공개된 자료가 없습니다.
    </p>
  ) : null;
}

export function RelationList({
  nodeId,
  nodeName,
  onEvidence,
}: {
  nodeId: string;
  nodeName: string;
  onEvidence: (selection: EvidenceSelection) => void;
}) {
  const page = useCursorPage(nodeId, fetchNodeRelations);
  return (
    <section className={styles.followupSection} aria-label="Node의 공개 관계">
      <h2>확인된 관계</h2>
      <div className={styles.relationAccordion}>
        {page.items.map((relation) => (
          <article
            key={relation.id}
            className={styles.relationCard}
            data-conflict={relation.conflict || undefined}
          >
            <button
              type="button"
              className={styles.relationToggle}
              onClick={() =>
                onEvidence({
                  id: relation.id,
                  label: `${nodeName} · ${relation.label} · ${relation.otherName}`,
                })
              }
            >
              <span>
                <strong>
                  {relation.otherName} · {relation.otherKind}
                </strong>
                <small>
                  {relationPathLabel(
                    relation.sourceId === nodeId
                      ? nodeName
                      : relation.otherName,
                    relation.label,
                    relation.targetId === nodeId
                      ? nodeName
                      : relation.otherName,
                    relation.directionality,
                  )}
                </small>
                <small>
                  독립 근거 {relation.evidenceGroupCount}개
                  {relation.conflict ? " · 충돌 있음" : ""}
                </small>
              </span>
              <span>근거 보기</span>
            </button>
          </article>
        ))}
      </div>
      <PageNotice {...page} empty={!page.items.length} onRetry={page.retry} />
      {page.nextCursor && (
        <button
          type="button"
          disabled={page.loading || Boolean(page.error)}
          onClick={page.more}
        >
          관계 더 보기
        </button>
      )}
    </section>
  );
}

export function publicationLabel(trace: SourceTrace): string {
  if (trace.publishedAt === null || trace.precision === "UNKNOWN")
    return "발행 시점 미상";
  if (trace.precision === "INSTANT")
    return new Date(trace.publishedAt).toLocaleString("ko-KR");
  const length = { DAY: 10, MONTH: 7, YEAR: 4 }[trace.precision];
  return trace.publishedAt.slice(0, length);
}

export function EvidenceDialog({
  selection,
  onClose,
}: {
  selection: EvidenceSelection;
  onClose: () => void;
}) {
  const dialogRef = useModalDialog(onClose);
  const titleId = useId();
  const page = useCursorPage(selection.id, fetchRelationEvidence);
  return (
    <dialog
      ref={dialogRef}
      className={styles.evidenceDialog}
      aria-labelledby={titleId}
      onCancel={onClose}
    >
      <header>
        <h2 id={titleId}>{selection.label} · Evidence Trace</h2>
        <button type="button" onClick={onClose} aria-label="근거 창 닫기">
          ×
        </button>
      </header>
      {page.items.map((trace) => (
        <article key={trace.key} className={styles.evidenceEntry}>
          <span>{trace.stance === "SUPPORT" ? "지지 근거" : "반박 근거"}</span>
          <h3>{trace.claimText}</h3>
          <TraceContent trace={trace} claimText={trace.claimText} />
        </article>
      ))}
      <PageNotice {...page} empty={!page.items.length} onRetry={page.retry} />
      {page.nextCursor && (
        <button
          type="button"
          disabled={page.loading || Boolean(page.error)}
          onClick={page.more}
        >
          근거 더 보기
        </button>
      )}
    </dialog>
  );
}

export function useModalDialog(onClose: () => void) {
  const close = useEffectEvent(onClose);
  const dialogRef = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = dialogRef.current;
    const opener = document.activeElement;
    dialog?.showModal();
    const onClick = (event: MouseEvent) => {
      if (!dialog || event.target !== dialog) return;
      const rect = dialog.getBoundingClientRect();
      if (
        event.clientX < rect.left ||
        event.clientX > rect.right ||
        event.clientY < rect.top ||
        event.clientY > rect.bottom
      )
        close();
    };
    dialog?.addEventListener("click", onClick);
    return () => {
      dialog?.removeEventListener("click", onClick);
      dialog?.close();
      if (opener instanceof HTMLElement && opener.isConnected) opener.focus();
    };
  }, []);
  return dialogRef;
}

function normalizedText(value: string): string {
  return value.replace(/\s+/g, " ").trim();
}

export function TraceContent({
  trace,
  claimText,
}: {
  trace: SourceTrace;
  claimText?: string;
}) {
  const repeatsClaim =
    claimText !== undefined &&
    normalizedText(trace.quote) === normalizedText(claimText);
  return (
    <>
      {!repeatsClaim && <blockquote>{trace.quote}</blockquote>}
      <p>
        {trace.publisher} · {publicationLabel(trace)}
      </p>
      <p>
        {trace.paragraph === null
          ? "문단 번호 미상"
          : `${trace.paragraph}번 문단`}{" "}
        · 문자 범위 {trace.start}–{trace.end} (끝 제외)
      </p>
      <a href={trace.url} target="_blank" rel="noopener noreferrer">
        {trace.title} 원문 열기
      </a>
    </>
  );
}
