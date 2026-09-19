import { useCallback, useId, useState } from "react";
import styles from "./App.module.css";
import { relationPathLabel, type TimeRange, timeRangeLabel } from "./data";
import {
  type EvidenceSelection,
  PageNotice,
  TraceContent,
} from "./RelationPanel";
import {
  fetchPanelClaims213,
  fetchPanelTraces213,
  type PanelClaim213,
} from "./read213";
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
      {timeRangeLabel(range)}
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
  claim: PanelClaim213;
  range: TimeRange;
}) {
  const fetchPage = useCallback(
    (_id: string, cursor: string | null, signal: AbortSignal) =>
      fetchPanelTraces213(nodeId, claim, range, cursor, signal),
    [nodeId, claim, range],
  );
  const page = useCursorPage(claim.id, fetchPage);
  return (
    <div className={styles.panelTraceList}>
      {page.items.map((trace) => (
        <article key={trace.key} className={styles.evidenceEntry}>
          <small>
            {trace.periodRole === "IN_WINDOW"
              ? range === "all"
                ? "등록된 원문"
                : "이 기간에 게시된 원문"
              : trace.periodRole === "BACKGROUND"
                ? "이 기간 이전의 배경 원문"
                : "게시 시점이 확인되지 않은 원문"}
          </small>
          <TraceContent trace={trace} claimText={claim.text} />
        </article>
      ))}
      <PageNotice
        {...page}
        empty={!page.items.length}
        additional={page.items.length > 0}
        onRetry={page.retry}
      />
      {page.nextCursor && (
        <button
          type="button"
          onClick={page.more}
          disabled={page.loading || !!page.error}
        >
          원문 더 보기
        </button>
      )}
    </div>
  );
}

function roleLabel(claim: PanelClaim213): string | null {
  if (claim.role === "KEY_CLAIM") return "핵심 내용";
  if (claim.role === "SUPPORTING_CLAIM") return "보충 내용";
  if (claim.role === "CONTRASTING_CLAIM") return "비교 내용";
  return null;
}

function modalityLabel(claim: PanelClaim213): string | null {
  if (claim.modality === "PLAN_OR_TARGET") return "계획·목표";
  if (claim.modality === "PREDICTION_OR_ESTIMATE") return "예측·추정";
  if (claim.modality === "OPINION_OR_EVALUATION") return "의견·평가";
  return null;
}

function claimKindLabel(claim: PanelClaim213): string {
  const role = roleLabel(claim);
  if (role) return role;
  const attribute = claim.connections.find((c) => c.kind === "ATTRIBUTE");
  if (attribute) return attribute.label;
  if (claim.connections.some((c) => c.kind === "EVENT_TIME"))
    return "사건 시점";
  if (claim.connections.some((c) => c.kind === "RELATION")) return "연결";
  return "확인된 내용";
}

export function ClaimCard({
  nodeId,
  claim,
  range,
  expanded,
  onExpanded,
  onEvidence,
  onLocate,
}: {
  nodeId: string;
  claim: PanelClaim213;
  range: TimeRange;
  expanded?: boolean;
  onExpanded?: (open: boolean) => void;
  onEvidence: (selection: EvidenceSelection) => void;
  onLocate: (nodeId: string, relationId?: string) => void;
}) {
  const [localOpen, setOpen] = useState(false);
  const open = expanded ?? localOpen;
  const id = useId();
  const modality = modalityLabel(claim);
  const conflict = claim.connections.some(
    (connection) => connection.kind === "CONFLICT",
  );
  const relationConnections = claim.connections.filter(
    (connection) => connection.kind === "RELATION" && connection.relation,
  );
  const otherConnections = claim.connections.filter(
    (connection) =>
      connection.kind !== "RELATION" && connection.kind !== "CONFLICT",
  );
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
            {claimKindLabel(claim)} ·{" "}
            {claim.state === "HUMAN_VERIFIED" ? "검토 완료" : "원문 연결됨"}
            {modality ? ` · ${modality}` : ""}
            {conflict ? " · 충돌" : ""}
          </small>
          <span>{claim.text}</span>
          <small>서로 다른 근거 {claim.evidenceGroupCount}개</small>
        </span>
        <span>{open ? "접기" : "원문과 연결 보기"}</span>
      </button>

      <div id={id} hidden={!open}>
        {open && (
          <>
            <ClaimTraces nodeId={nodeId} claim={claim} range={range} />
            {otherConnections.length > 0 && (
              <div className={styles.connectionTags}>
                {otherConnections.map((connection) => (
                  <small
                    key={`${connection.kind}:${connection.id}:${connection.position}`}
                  >
                    {connection.label}
                  </small>
                ))}
              </div>
            )}
            {relationConnections.map((connection) => {
              const relation = connection.relation;
              if (!relation) return null;
              return (
                <div
                  key={`${connection.kind}:${relation.id}:${relation.stance}`}
                  className={styles.relationCard}
                >
                  <div className={styles.relationToggle}>
                    <span>
                      <small>
                        {relationPathLabel(
                          relation.sourceNode.name,
                          relation.displayName,
                          relation.targetNode.name,
                          relation.directionality,
                        )}
                      </small>
                      <small>
                        {relation.stance === "SUPPORT"
                          ? "연결을 뒷받침"
                          : "연결과 상충"}
                      </small>
                    </span>
                    <span className={styles.relationActions}>
                      <button
                        type="button"
                        onClick={() =>
                          onLocate(relation.otherNode.id, relation.id)
                        }
                      >
                        지도에서 강조
                      </button>
                      <button
                        type="button"
                        aria-label={`${relation.otherNode.name} ${relation.displayName} 연결 원문 보기`}
                        onClick={() =>
                          onEvidence({
                            id: relation.id,
                            label: relationPathLabel(
                              relation.sourceNode.name,
                              relation.displayName,
                              relation.targetNode.name,
                              relation.directionality,
                            ),
                          })
                        }
                      >
                        연결 원문
                      </button>
                    </span>
                  </div>
                </div>
              );
            })}
          </>
        )}
      </div>
    </article>
  );
}

export function PanelEvidence({
  nodeId,
  range,
  onEvidence,
  onLocate,
}: {
  nodeId: string;
  range: TimeRange;
  onEvidence: (selection: EvidenceSelection) => void;
  onLocate: (nodeId: string, relationId?: string) => void;
}) {
  const fetchPage = useCallback(
    (id: string, cursor: string | null, signal: AbortSignal) =>
      fetchPanelClaims213(id, range, cursor, signal),
    [range],
  );
  const page = useCursorPage(nodeId, fetchPage);
  return (
    <section aria-label="자료에서 확인한 내용">
      <h2>자료에서 확인한 내용</h2>
      <PeriodNote range={range} />
      <p className={styles.panelMeta}>
        항목을 열어 실제 기사 문장과 출처를 확인할 수 있습니다.
      </p>
      {page.items.map((claim) => (
        <ClaimCard
          key={claim.id}
          nodeId={nodeId}
          claim={claim}
          range={range}
          onEvidence={onEvidence}
          onLocate={onLocate}
        />
      ))}
      <PageNotice
        {...page}
        empty={!page.items.length}
        additional={page.items.length > 0}
        onRetry={page.retry}
      />
      {page.nextCursor && (
        <button
          type="button"
          onClick={page.more}
          disabled={page.loading || !!page.error}
        >
          확인된 내용 더 보기
        </button>
      )}
    </section>
  );
}
