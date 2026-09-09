import { useCallback, useId, useState } from "react";
import styles from "./App.module.css";
import {
  fetchPanelClaims,
  fetchPanelTraces,
  type PanelClaim,
  type TimeRange,
} from "./data";
import { PageNotice, TraceContent } from "./RelationPanel";
import { useCursorPage } from "./useCursorPage";

export function PeriodNote({
  range,
  asOf,
}: {
  range: TimeRange;
  asOf?: string;
}) {
  return (
    <p className={styles.panelMeta}>
      {range === "90d" ? "최근 90일" : "최근 1년"}
      {asOf
        ? ` · ${new Date(asOf).toLocaleDateString("ko-KR")} 기준`
        : " · 출처 게시일 기준"}
    </p>
  );
}

function ClaimTraces({
  nodeId,
  claim,
  range,
}: {
  nodeId: string;
  claim: PanelClaim;
  range: TimeRange;
}) {
  const fetchPage = useCallback(
    (_id: string, cursor: string | null, signal: AbortSignal) =>
      fetchPanelTraces(nodeId, claim, range, cursor, signal),
    [nodeId, claim, range],
  );
  const page = useCursorPage(claim.id, fetchPage);
  return (
    <div className={styles.panelTraceList}>
      {page.items.map((trace) => (
        <article key={trace.key} className={styles.evidenceEntry}>
          <small>
            {trace.periodRole === "IN_WINDOW"
              ? "선택 기간의 근거"
              : trace.periodRole === "BACKGROUND"
                ? "기간 밖 배경 근거"
                : "게시 시점 미상"}
          </small>
          <TraceContent trace={trace} claimText={claim.text} />
        </article>
      ))}
      <PageNotice {...page} empty={!page.items.length} onRetry={page.retry} />
      {page.nextCursor && (
        <button
          type="button"
          onClick={page.more}
          disabled={page.loading || !!page.error}
        >
          출처 더 보기
        </button>
      )}
    </div>
  );
}

function claimLabel(claim: PanelClaim): string {
  if (
    claim.role === "CONTRASTING_CLAIM" ||
    claim.connections.some((c) => c.kind === "CONFLICT")
  )
    return "엇갈리는 주장";
  if (claim.connections.some((c) => c.kind === "ATTRIBUTE")) return "노드 속성";
  if (claim.connections.some((c) => c.kind === "EVENT_TIME"))
    return "사건 시간";
  return claim.connections.length ? "관계 근거" : "연결 근거";
}

export function ClaimCard({
  nodeId,
  claim,
  range,
  expanded,
  onExpanded,
}: {
  nodeId: string;
  claim: PanelClaim;
  range: TimeRange;
  expanded?: boolean;
  onExpanded?: (open: boolean) => void;
}) {
  const [localOpen, setOpen] = useState(false);
  const open = expanded ?? localOpen;
  const id = useId();
  return (
    <article className={styles.panelClaim}>
      <button
        type="button"
        className={styles.panelDisclosure}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => {
          setOpen(!open);
          onExpanded?.(!open);
        }}
      >
        <span>
          <small>
            {claimLabel(claim)} ·{" "}
            {claim.state === "HUMAN_VERIFIED" ? "사람 확인됨" : "근거 확인됨"}
          </small>
          <span>{claim.text}</span>
          {claim.connections.map((connection) => (
            <small
              key={`${connection.kind}:${connection.id}:${connection.position}`}
            >
              {connection.label}
              {connection.position === "DISPUTE" ? " · 반박" : ""}
            </small>
          ))}
          <small>기간 내 독립 근거 {claim.evidenceGroupCount}개</small>
        </span>
        <span aria-hidden="true">{open ? "−" : "+"}</span>
      </button>
      <div id={id} hidden={!open}>
        {open && <ClaimTraces nodeId={nodeId} claim={claim} range={range} />}
      </div>
    </article>
  );
}

export function PanelEvidence({
  nodeId,
  range,
}: {
  nodeId: string;
  range: TimeRange;
}) {
  const fetchPage = useCallback(
    (id: string, cursor: string | null, signal: AbortSignal) =>
      fetchPanelClaims(id, range, cursor, signal),
    [range],
  );
  const page = useCursorPage(nodeId, fetchPage);
  return (
    <section aria-label="노드와 관계의 근거">
      <h2>주장과 근거</h2>
      <PeriodNote range={range} />
      <p className={styles.panelMeta}>주장을 펼쳐 원문과 출처를 확인하세요.</p>
      {page.items.map((claim) => (
        <ClaimCard key={claim.id} nodeId={nodeId} claim={claim} range={range} />
      ))}
      <PageNotice {...page} empty={!page.items.length} onRetry={page.retry} />
      {page.nextCursor && (
        <button
          type="button"
          onClick={page.more}
          disabled={page.loading || !!page.error}
        >
          주장 더 보기
        </button>
      )}
    </section>
  );
}
