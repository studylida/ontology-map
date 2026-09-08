export type TimeRange = "90d" | "1y";
export type NodeTier = "center" | "direct" | "twoHop" | "threeHop" | "ambient";

export interface KnowledgeNode {
  id: string;
  name: string;
  kind: string;
  kindCode: string;
  tier: NodeTier;
  activityEvidenceGroupCount: number;
}

export interface KnowledgeRelation {
  id: string;
  source: string;
  target: string;
  label: string;
  directionality: "DIRECTED" | "SYMMETRIC";
  evidenceGroupCount: number;
  conflict?: boolean;
  tier: Exclude<NodeTier, "center">;
}

export interface ExplorationRecommendation {
  node: KnowledgeNode;
  reason: string;
  status: "confirmedRelation" | "connectedPath" | "ambient";
  evidenceGroupCount?: number;
}

export interface FollowupQuestion {
  id: string;
  text: string;
  targetNodeId: string;
}

export interface ExplorationView {
  centerId: string;
  context: string;
  nodes: KnowledgeNode[];
  relations: KnowledgeRelation[];
  recommendations: ExplorationRecommendation[];
  followups: FollowupQuestion[];
}

export type SearchMatchReason = "EXACT_ALIAS" | "FULL_TEXT";

export interface SearchCandidate {
  nodeId: string;
  name: string;
  kind: string;
  kindCode: string;
  matchReasons: SearchMatchReason[];
}

export type KnowledgeViewNode = KnowledgeNode;
export type KnowledgeViewRelation = KnowledgeRelation;

export class APIRequestError extends Error {
  constructor(
    readonly code: string,
    readonly status: number,
    readonly retryable: boolean,
  ) {
    super(code);
  }
}

type JsonObject = Record<string, unknown>;

function object(value: unknown): JsonObject {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new APIRequestError("INVALID_RESPONSE", 0, true);
  }
  return value as JsonObject;
}

function array(value: unknown): unknown[] {
  if (!Array.isArray(value)) {
    throw new APIRequestError("INVALID_RESPONSE", 0, true);
  }
  return value;
}

function string(value: unknown): string {
  if (typeof value !== "string") {
    throw new APIRequestError("INVALID_RESPONSE", 0, true);
  }
  return value;
}

function number(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new APIRequestError("INVALID_RESPONSE", 0, true);
  }
  return value;
}

function boolean(value: unknown): boolean {
  if (typeof value !== "boolean") {
    throw new APIRequestError("INVALID_RESPONSE", 0, true);
  }
  return value;
}

function nodeTier(value: unknown): Exclude<NodeTier, "ambient"> {
  if (value === "CENTER") return "center";
  if (value === "DIRECT") return "direct";
  if (value === "TWO_HOP") return "twoHop";
  if (value === "THREE_HOP") return "threeHop";
  throw new APIRequestError("INVALID_RESPONSE", 0, true);
}

function relationTier(
  source: KnowledgeNode,
  target: KnowledgeNode,
): Exclude<NodeTier, "center"> {
  if (source.tier === "center" || target.tier === "center") return "direct";
  if (source.tier === "ambient" || target.tier === "ambient") return "ambient";
  if (source.tier === "threeHop" || target.tier === "threeHop")
    return "threeHop";
  return "twoHop";
}

export function relationPathLabel(
  source: string,
  label: string,
  target: string,
  direction: KnowledgeRelation["directionality"],
): string {
  return `${source} — ${label} ${direction === "DIRECTED" ? "→" : "—"} ${target}`;
}

function recommendationReason(item: JsonObject): string {
  const code = member(item.reason_code, [
    "DIRECT",
    "TWO_HOP",
    "AMBIENT",
  ] as const);
  const path = array(item.path);
  if (path.length !== { DIRECT: 1, TWO_HOP: 2, AMBIENT: 0 }[code])
    throw new APIRequestError("INVALID_RESPONSE", 0, true);
  if (code === "AMBIENT")
    return "현재 중심과의 관계가 확인되지 않은 새 탐색 출발점입니다.";
  return path
    .map((value) => {
      const edge = object(value);
      string(edge.relation_id);
      string(edge.source_node_id);
      string(edge.target_node_id);
      return relationPathLabel(
        string(edge.source_node_name),
        string(edge.relation_type_display_name),
        string(edge.target_node_name),
        directionality(edge.directionality),
      );
    })
    .join(" · ");
}

export function toExplorationView(payload: unknown): ExplorationView {
  const root = object(payload);
  const graph = object(root.graph);
  const nodes = array(graph.nodes).map((value) => {
    const item = object(value);
    const type = object(item.node_type);
    return {
      id: string(item.node_id),
      name: string(item.name),
      kind: string(type.display_name),
      kindCode: string(type.code),
      tier: nodeTier(item.tier),
      activityEvidenceGroupCount: number(item.activity_evidence_group_count),
    } satisfies KnowledgeNode;
  });
  const nodesById = new Map(nodes.map((node) => [node.id, node]));
  const relations = array(graph.relations).map((value) => {
    const item = object(value);
    const source = nodesById.get(string(item.source_node_id));
    const target = nodesById.get(string(item.target_node_id));
    if (!source || !target) {
      throw new APIRequestError("INVALID_RESPONSE", 0, true);
    }
    return {
      id: string(item.relation_id),
      source: source.id,
      target: target.id,
      label: string(item.relation_type_display_name),
      directionality: directionality(item.directionality),
      evidenceGroupCount: number(item.supporting_evidence_group_count),
      conflict: boolean(item.has_conflict),
      tier: relationTier(source, target),
    } satisfies KnowledgeRelation;
  });
  const recommendations = array(root.recommendations).map((value) => {
    const item = object(value);
    const target = object(item.target_node);
    const targetType = object(target.node_type);
    const id = string(target.node_id);
    const reasonCode = string(item.reason_code);
    const graphNode = nodesById.get(id);
    const recommendationNode: KnowledgeNode = graphNode ?? {
      id,
      name: string(target.name),
      kind: string(targetType.display_name),
      kindCode: string(targetType.code),
      tier: "ambient",
      activityEvidenceGroupCount: 0,
    };
    const evidenceCount =
      item.supporting_evidence_group_count === null
        ? undefined
        : number(item.supporting_evidence_group_count);
    return {
      node: recommendationNode,
      reason: recommendationReason(item),
      status:
        reasonCode === "DIRECT"
          ? "confirmedRelation"
          : reasonCode === "TWO_HOP"
            ? "connectedPath"
            : "ambient",
      ...(evidenceCount === undefined
        ? {}
        : { evidenceGroupCount: evidenceCount }),
    } satisfies ExplorationRecommendation;
  });
  const followups = array(root.followup_questions).map((value) => {
    const item = object(value);
    const slot = number(item.slot);
    return {
      id: `followup-${slot}`,
      text: string(item.question_text),
      targetNodeId: string(item.target_node_id),
    } satisfies FollowupQuestion;
  });

  return {
    centerId: string(root.center_node_id),
    context: string(root.context_text),
    nodes,
    relations,
    recommendations,
    followups,
  };
}

function matchReason(value: unknown): SearchMatchReason {
  if (value === "EXACT_ALIAS" || value === "FULL_TEXT") return value;
  throw new APIRequestError("INVALID_RESPONSE", 0, true);
}

export function toSearchCandidates(payload: unknown): SearchCandidate[] {
  return array(object(payload).items).map((value) => {
    const item = object(value);
    const type = object(item.node_type);
    return {
      nodeId: string(item.node_id),
      name: string(item.name),
      kind: string(type.display_name),
      kindCode: string(type.code),
      matchReasons: array(item.match_reasons).map(matchReason),
    };
  });
}

async function fetchAPI(path: string, signal?: AbortSignal): Promise<unknown> {
  let response: Response;
  try {
    response = await fetch(path, signal ? { signal } : undefined);
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError")
      throw error;
    throw new APIRequestError("NETWORK_ERROR", 0, true);
  }

  const payload: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const errorBody =
      payload && typeof payload === "object"
        ? (payload as JsonObject).error
        : null;
    const detail =
      errorBody && typeof errorBody === "object"
        ? (errorBody as JsonObject)
        : {};
    throw new APIRequestError(
      typeof detail.code === "string" ? detail.code : "REQUEST_FAILED",
      response.status,
      typeof detail.retryable === "boolean"
        ? detail.retryable
        : response.status >= 500,
    );
  }
  return payload;
}

export async function fetchExploration(
  centerId: string,
  timeRange: TimeRange,
  signal?: AbortSignal,
): Promise<ExplorationView> {
  const path = `/api/v1/exploration/${encodeURIComponent(
    centerId,
  )}?time_window=${timeRange === "90d" ? "RECENT_90_DAYS" : "RECENT_1_YEAR"}`;
  return toExplorationView(await fetchAPI(path, signal));
}

export async function fetchNodeSearch(
  query: string,
  signal?: AbortSignal,
): Promise<SearchCandidate[]> {
  const params = new URLSearchParams({ q: query, limit: "5" });
  return toSearchCandidates(
    await fetchAPI(`/api/v1/nodes/search?${params.toString()}`, signal),
  );
}

export function getFilamentOffsets(evidenceGroupCount: number): number[] {
  const count = Math.max(1, Math.round(evidenceGroupCount));
  if (count === 1) return [0];
  const spacing = count <= 5 ? 1.2 : 4.8 / (count - 1);
  return Array.from(
    { length: count },
    (_, index) => (index - (count - 1) / 2) * spacing,
  );
}

function member<T extends string>(value: unknown, choices: readonly T[]): T {
  const matched = choices.find((choice) => choice === value);
  if (matched === undefined)
    throw new APIRequestError("INVALID_RESPONSE", 0, true);
  return matched;
}

function directionality(value: unknown): KnowledgeRelation["directionality"] {
  return member(value, ["DIRECTED", "SYMMETRIC"] as const);
}

export interface CursorPage<T> {
  items: T[];
  nextCursor: string | null;
}
export interface NodeRelation {
  sourceId: string;
  targetId: string;
  directionality: KnowledgeRelation["directionality"];
  id: string;
  label: string;
  otherName: string;
  otherKind: string;
  evidenceGroupCount: number;
  conflict: boolean;
}
export interface EvidenceTrace extends SourceTrace {
  claimText: string;
  stance: "SUPPORT" | "DISPUTE";
}
export interface SourceTrace {
  key: string;
  title: string;
  publisher: string;
  publishedAt: string | null;
  precision: "INSTANT" | "DAY" | "MONTH" | "YEAR" | "UNKNOWN";
  url: string;
  quote: string;
  paragraph: number | null;
  start: number;
  end: number;
}

function nullableString(value: unknown): string | null {
  return value === null ? null : string(value);
}

function pagePath(path: string, cursor: string | null): string {
  const params = new URLSearchParams({ limit: "20" });
  if (cursor !== null) params.set("cursor", cursor);
  return `${path}?${params}`;
}

export async function fetchNodeRelations(
  id: string,
  cursor: string | null,
  signal: AbortSignal,
): Promise<CursorPage<NodeRelation>> {
  const payload = object(
    await fetchAPI(
      pagePath(`/api/v1/nodes/${encodeURIComponent(id)}/relations`, cursor),
      signal,
    ),
  );
  return {
    items: array(payload.items).map((value) => {
      const item = object(value);
      const other = object(item.other_node);
      return {
        id: string(item.relation_id),
        sourceId: string(item.source_node_id),
        targetId: string(item.target_node_id),
        directionality: directionality(item.directionality),
        label: string(item.relation_type_display_name),
        otherName: string(other.name),
        otherKind: string(object(other.node_type).display_name),
        evidenceGroupCount: number(item.supporting_evidence_group_count),
        conflict: boolean(item.has_conflict),
      };
    }),
    nextCursor: nullableString(payload.next_cursor),
  };
}

function toSourceTrace(value: unknown): SourceTrace {
  const item = object(value);
  const source = object(item.source);
  const locator = object(item.locator);
  const precision = member(source.published_precision, [
    "INSTANT",
    "DAY",
    "MONTH",
    "YEAR",
    "UNKNOWN",
  ] as const);
  const url = string(source.canonical_url);
  if (!/^https?:\/\//i.test(url))
    throw new APIRequestError("INVALID_RESPONSE", 0, true);
  const trace: Omit<SourceTrace, "key"> = {
    title: string(source.title),
    publisher: string(source.publisher_name),
    publishedAt: nullableString(source.published_at),
    precision,
    url,
    quote: string(item.quote_text),
    paragraph:
      locator.paragraph_number === null
        ? null
        : number(locator.paragraph_number),
    start: number(locator.start_char),
    end: number(locator.end_char),
  };
  return { ...trace, key: JSON.stringify(trace) };
}

function toEvidenceTrace(value: unknown): EvidenceTrace {
  const item = object(value);
  return {
    ...toSourceTrace(item),
    claimText: string(item.claim_text),
    stance: member(item.stance, ["SUPPORT", "DISPUTE"] as const),
  };
}

export async function fetchRelationEvidence(
  id: string,
  cursor: string | null,
  signal: AbortSignal,
): Promise<CursorPage<EvidenceTrace>> {
  const payload = object(
    await fetchAPI(
      pagePath(`/api/v1/relations/${encodeURIComponent(id)}/evidence`, cursor),
      signal,
    ),
  );
  return {
    items: array(payload.items).map(toEvidenceTrace),
    nextCursor: nullableString(payload.next_cursor),
  };
}

export interface PeripheralPage {
  nodes: KnowledgeNode[];
  relations: KnowledgeRelation[];
  nextCursor: string | null;
}

export function mergeById<T extends { id: string }>(
  current: T[],
  additions: T[],
): T[] {
  return [
    ...new Map(
      [...current, ...additions].map((item) => [item.id, item]),
    ).values(),
  ];
}

export async function fetchPeripheral(
  view: ExplorationView,
  range: TimeRange,
  cursor: string | null,
  signal: AbortSignal,
): Promise<PeripheralPage> {
  const params = new URLSearchParams({
    time_window: range === "90d" ? "RECENT_90_DAYS" : "RECENT_1_YEAR",
    limit: "20",
  });
  if (cursor !== null) params.set("cursor", cursor);
  const payload = object(
    await fetchAPI(
      `/api/v1/exploration/${encodeURIComponent(view.centerId)}/peripheral?${params}`,
      signal,
    ),
  );
  const graph = object(payload.graph);
  const nodes = array(graph.nodes).map((value) => {
    const item = object(value);
    const type = object(item.node_type);
    member(item.tier, ["AMBIENT"] as const);
    return {
      id: string(item.node_id),
      name: string(item.name),
      kind: string(type.display_name),
      kindCode: string(type.code),
      tier: "ambient" as const,
      activityEvidenceGroupCount: number(item.activity_evidence_group_count),
    };
  });
  const known = new Set([...view.nodes, ...nodes].map((node) => node.id));
  const relations = array(graph.relations).map((value) => {
    const item = object(value);
    const source = string(item.source_node_id);
    const target = string(item.target_node_id);
    if (!known.has(source) || !known.has(target))
      throw new APIRequestError("INVALID_RESPONSE", 0, true);
    return {
      id: string(item.relation_id),
      source,
      target,
      label: string(item.relation_type_display_name),
      directionality: directionality(item.directionality),
      evidenceGroupCount: number(item.supporting_evidence_group_count),
      conflict: boolean(item.has_conflict),
      tier:
        source === view.centerId || target === view.centerId
          ? ("direct" as const)
          : ("ambient" as const),
    };
  });
  return { nodes, relations, nextCursor: nullableString(payload.next_cursor) };
}

export interface InsightItem {
  id: string;
  title: string;
  evidenceGroupCount: number;
}
export interface InsightReport extends InsightItem {
  summary: string;
  synthesis: string;
  caveat: string;
  claims: {
    id: string;
    text: string;
    role: "KEY_CLAIM" | "SUPPORTING_CLAIM" | "CONTRASTING_CLAIM";
    traces: SourceTrace[];
  }[];
}
function toInsightItem(value: unknown): InsightItem {
  const item = object(value);
  return {
    id: string(item.insight_id),
    title: string(item.title),
    evidenceGroupCount: number(item.evidence_group_count),
  };
}
export async function fetchNodeInsights(
  nodeId: string,
  range: TimeRange,
  signal: AbortSignal,
): Promise<CursorPage<InsightItem>> {
  const params = new URLSearchParams({
    time_window: range === "90d" ? "RECENT_90_DAYS" : "RECENT_1_YEAR",
  });
  const payload = object(
    await fetchAPI(
      `/api/v1/nodes/${encodeURIComponent(nodeId)}/insights?${params}`,
      signal,
    ),
  );
  return { items: array(payload.items).map(toInsightItem), nextCursor: null };
}
export async function fetchInsight(
  id: string,
  _cursor: string | null,
  signal: AbortSignal,
): Promise<CursorPage<InsightReport>> {
  const item = object(
    await fetchAPI(`/api/v1/insights/${encodeURIComponent(id)}`, signal),
  );
  return {
    items: [
      {
        ...toInsightItem(item),
        summary: string(item.summary),
        synthesis: string(item.synthesis),
        caveat: string(item.caveat),
        claims: array(item.claims).map((value) => {
          const claim = object(value);
          return {
            id: string(claim.claim_id),
            text: string(claim.claim_text),
            role: member(claim.role, [
              "KEY_CLAIM",
              "SUPPORTING_CLAIM",
              "CONTRASTING_CLAIM",
            ] as const),
            traces: array(claim.traces).map(toSourceTrace),
          };
        }),
      },
    ],
    nextCursor: null,
  };
}
