export type TimeRange = "90d" | "1y";
export type NodeTier = "center" | "direct" | "twoHop" | "ambient";

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
  throw new APIRequestError("INVALID_RESPONSE", 0, true);
}

function relationTier(
  source: KnowledgeNode,
  target: KnowledgeNode,
): Exclude<NodeTier, "center"> {
  if (
    source.tier === "center" ||
    target.tier === "center" ||
    source.tier === "direct" ||
    target.tier === "direct"
  ) {
    return "direct";
  }
  return "twoHop";
}

function recommendationReason(
  code: string,
  targetName: string,
  viaNodeName?: string,
): string {
  if (code === "DIRECT") {
    return `${targetName}와 직접 연결된 공개 관계를 살펴봅니다.`;
  }
  if (code === "TWO_HOP") {
    return `${viaNodeName ?? "연결 node"}에서 이어지는 공개 경로를 살펴봅니다.`;
  }
  if (code === "AMBIENT") {
    return "현재 지도 밖의 공개 node를 새 탐색 출발점으로 살펴봅니다.";
  }
  throw new APIRequestError("INVALID_RESPONSE", 0, true);
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
    const viaId =
      item.via_node_id === null ? undefined : string(item.via_node_id);
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
      reason: recommendationReason(
        reasonCode,
        recommendationNode.name,
        viaId ? nodesById.get(viaId)?.name : undefined,
      ),
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
