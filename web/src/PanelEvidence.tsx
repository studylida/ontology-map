import { useCallback, useId, useRef, useState } from "react";
import styles from "./App.module.css";
import {
  type ExplorationView,
  relationPathLabel,
  type TimeRange,
} from "./data";
import {
  type EvidenceSelection,
  PageNotice,
  RelationList,
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
              ? "선택 기간의 근거"
              : trace.periodRole === "BACKGROUND"
                ? "기간 밖 배경 근거"
                : "게시 시점 미상"}
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
          출처 더 보기
        </button>
      )}
    </div>
  );
}

function roleLabel(claim: PanelClaim213): string | null {
  if (claim.role === "KEY_CLAIM") return "핵심 근거";
  if (claim.role === "SUPPORTING_CLAIM") return "보조 근거";
  if (claim.role === "CONTRASTING_CLAIM") return "비교 근거";
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
  if (claim.connections.some((c) => c.kind === "ATTRIBUTE")) return "노드 속성";
  if (claim.connections.some((c) => c.kind === "EVENT_TIME"))
    return "사건 시간";
  if (claim.connections.some((c) => c.kind === "RELATION")) return "관계 근거";
  return "연결 근거";
}

export function ClaimCard({
  nodeId,
  claim,
  range,
  expanded,
  onExpanded,
  onEvidence,
  onSelect,
}: {
  nodeId: string;
  claim: PanelClaim213;
  range: TimeRange;
  expanded?: boolean;
  onExpanded?: (open: boolean) => void;
  onEvidence: (selection: EvidenceSelection) => void;
  onSelect: (nodeId: string) => void;
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
            {claim.state === "HUMAN_VERIFIED" ? "사람 확인됨" : "근거 확인됨"}
            {modality ? ` · ${modality}` : ""}
            {conflict ? " · 충돌" : ""}
          </small>
          <span>{claim.text}</span>
          <small>기간 내 독립 근거 {claim.evidenceGroupCount}개</small>
        </span>
        <span aria-hidden="true">{open ? "−" : "+"}</span>
      </button>

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
                <small>{relation.stance === "SUPPORT" ? "지지" : "반박"}</small>
              </span>
              <span>
                <button
                  type="button"
                  onClick={() => onSelect(relation.otherNode.id)}
                >
                  {relation.otherNode.name} · Node 보기
                </button>
                <button
                  type="button"
                  onClick={() =>
                    onEvidence({
                      id: relation.id,
                      label: `${relation.sourceNode.name} · ${relation.displayName} · ${relation.targetNode.name}`,
                    })
                  }
                >
                  관계 근거
                </button>
              </span>
            </div>
          </div>
        );
      })}

      {otherConnections.map((connection) => (
        <small
          key={`${connection.kind}:${connection.id}:${connection.position}`}
        >
          {connection.label}
        </small>
      ))}

      <div id={id} hidden={!open}>
        {open && <ClaimTraces nodeId={nodeId} claim={claim} range={range} />}
      </div>
    </article>
  );
}

export function PanelEvidence({
  nodeId,
  nodeName,
  range,
  onEvidence,
  onSelect,
  loadedGraph,
  hiddenKinds,
}: {
  nodeId: string;
  nodeName: string;
  range: TimeRange;
  onEvidence: (selection: EvidenceSelection) => void;
  onSelect: (nodeId: string) => void;
  loadedGraph: ExplorationView | null;
  hiddenKinds: readonly string[];
}) {
  const fetchPage = useCallback(
    (id: string, cursor: string | null, signal: AbortSignal) =>
      fetchPanelClaims213(id, range, cursor, signal),
    [range],
  );
  const page = useCursorPage(nodeId, fetchPage);
  const [subview, setSubview] = useState<"claims" | "relations">("claims");
  const claimsSectionRef = useRef<HTMLElement>(null);
  const relationOpenerRef = useRef<HTMLButtonElement>(null);
  const savedScrollRef = useRef(0);

  const openRelations = () => {
    const panel = claimsSectionRef.current?.closest("aside");
    savedScrollRef.current = panel?.scrollTop ?? 0;
    setSubview("relations");
  };
  const closeRelations = () => {
    setSubview("claims");
    requestAnimationFrame(() => {
      const panel = claimsSectionRef.current?.closest("aside");
      if (panel) panel.scrollTop = savedScrollRef.current;
      relationOpenerRef.current?.focus();
    });
  };

  return (
    <>
      <section
        ref={claimsSectionRef}
        aria-label="노드와 관계의 근거"
        hidden={subview !== "claims"}
      >
        <h2>주장과 근거</h2>
        <PeriodNote range={range} />
        <p className={styles.panelMeta}>
          주장을 펼쳐 원문과 출처를 확인하세요.
        </p>
        <button ref={relationOpenerRef} type="button" onClick={openRelations}>
          전체 관계 보기
        </button>
        {page.items.map((claim) => (
          <ClaimCard
            key={claim.id}
            nodeId={nodeId}
            claim={claim}
            range={range}
            onEvidence={onEvidence}
            onSelect={onSelect}
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
            주장 더 보기
          </button>
        )}
      </section>
      {subview === "relations" && (
        <section aria-label="전체 관계 보기">
          <button type="button" onClick={closeRelations}>
            주장과 근거로 돌아가기
          </button>
          <RelationList
            nodeId={nodeId}
            nodeName={nodeName}
            onEvidence={onEvidence}
            onSelect={onSelect}
            loadedGraph={loadedGraph}
            hiddenKinds={hiddenKinds}
          />
        </section>
      )}
    </>
  );
}
