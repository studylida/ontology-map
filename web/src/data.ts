export type TimeRange = "90d" | "1y";
export type NodeKind = "사람" | "회사" | "기술" | "주제" | "사건";
export type NodeTier = "center" | "direct" | "twoHop" | "ambient";

export interface EvidenceTrace {
  sourceTitle: string;
  publisher: string;
  publishedAt: string;
  quote: string;
  locator: string;
}

export interface FollowupQuestion {
  id: string;
  text: string;
  targetNodeId: string;
}

export interface KnowledgeNode {
  id: string;
  name: string;
  kind: NodeKind;
  searchReason: string;
  context: string;
  claim: string;
  activity: Record<TimeRange, number>;
  evidence: EvidenceTrace;
  followups: readonly [FollowupQuestion, FollowupQuestion];
}

export interface KnowledgeRelation {
  id: string;
  source: string;
  target: string;
  label: string;
  evidenceGroupCount: number;
  conflict?: boolean;
}

export interface KnowledgeViewNode extends KnowledgeNode {
  tier: NodeTier;
}

export interface KnowledgeViewRelation extends KnowledgeRelation {
  tier: Exclude<NodeTier, "center">;
}

type ActivityLevel = "low" | "medium" | "high";

const nodeCatalog: readonly {
  id: string;
  name: string;
  kind: NodeKind;
  activity: ActivityLevel;
}[] = [
  { id: "sk", name: "SK하이닉스", kind: "회사", activity: "high" },
  { id: "sandisk", name: "SanDisk", kind: "회사", activity: "medium" },
  { id: "fms", name: "FMS 2026 HBF 발표", kind: "사건", activity: "medium" },
  { id: "standard", name: "HBF 표준화 착수", kind: "사건", activity: "medium" },
  { id: "kim", name: "김천성", kind: "사람", activity: "medium" },
  { id: "kang", name: "강욱성", kind: "사람", activity: "medium" },
  {
    id: "nand-event",
    name: "375단 4D NAND 공개",
    kind: "사건",
    activity: "medium",
  },
  { id: "ai-memory", name: "AI 메모리", kind: "주제", activity: "medium" },
  {
    id: "tiered-memory",
    name: "계층형 메모리",
    kind: "기술",
    activity: "medium",
  },
  { id: "hbf", name: "HBF", kind: "기술", activity: "medium" },
  { id: "ucie", name: "UCIe", kind: "기술", activity: "medium" },
  { id: "google", name: "Google", kind: "회사", activity: "low" },
  { id: "tenstorrent", name: "Tenstorrent", kind: "회사", activity: "low" },
  { id: "nand", name: "375단 4D NAND", kind: "기술", activity: "low" },
  { id: "ocp", name: "OCP 공개 표준", kind: "주제", activity: "low" },
  { id: "hbm", name: "HBM", kind: "기술", activity: "medium" },
  { id: "ssd", name: "SSD", kind: "기술", activity: "medium" },
  { id: "cpu", name: "CPU", kind: "기술", activity: "low" },
  { id: "gpu", name: "GPU", kind: "기술", activity: "low" },
  {
    id: "isolated",
    name: "미연결 공개 기술",
    kind: "기술",
    activity: "medium",
  },
];

export const knowledgeRelations: readonly KnowledgeRelation[] = [
  ["sk", "sandisk", 3],
  ["sk", "fms", 3],
  ["sk", "standard", 3],
  ["sk", "kim", 1],
  ["sk", "kang", 1],
  ["sk", "nand-event", 3],
  ["sk", "ai-memory", 6],
  ["sk", "tiered-memory", 3],
  ["fms", "hbf", 1],
  ["hbf", "ucie", 1],
  ["sandisk", "google", 1],
  ["sandisk", "tenstorrent", 1],
  ["nand-event", "nand", 1],
  ["standard", "ocp", 1],
  ["hbf", "sandisk", 3],
  ["hbf", "hbm", 6],
  ["hbf", "ssd", 3],
  ["hbf", "standard", 1],
  ["hbf", "ocp", 1],
  ["hbf", "ai-memory", 3],
  ["ucie", "cpu", 1],
  ["ucie", "gpu", 1],
  ["ai-memory", "tiered-memory", 3],
  ["tiered-memory", "hbm", 1],
].map(([source, target, evidenceGroupCount], index) => ({
  id: `link-${index}`,
  source: String(source),
  target: String(target),
  label: "공개 관계",
  evidenceGroupCount: Number(evidenceGroupCount),
  conflict: index === 13,
}));

const activityByLevel: Record<ActivityLevel, Record<TimeRange, number>> = {
  low: { "90d": 32, "1y": 52 },
  medium: { "90d": 64, "1y": 82 },
  high: { "90d": 92, "1y": 100 },
};

const catalogById = new Map(nodeCatalog.map((node) => [node.id, node]));
const neighborIds = (nodeId: string): string[] => {
  const result: string[] = [];
  for (const relation of knowledgeRelations) {
    if (relation.source === nodeId) result.push(relation.target);
    if (relation.target === nodeId) result.push(relation.source);
  }
  return [...new Set(result)];
};

const followupsFor = (
  nodeId: string,
): readonly [FollowupQuestion, FollowupQuestion] => {
  const neighbors = neighborIds(nodeId);
  const firstNeighbor = neighbors[0];
  const targets: [string, string] = firstNeighbor
    ? [firstNeighbor, neighbors[1] ?? nodeId]
    : [nodeId, "sk"];
  return targets.map((targetNodeId, index) => {
    const target = catalogById.get(targetNodeId);
    const selfTarget = targetNodeId === nodeId;
    return {
      id: `${nodeId}-followup-${index + 1}`,
      text: selfTarget
        ? "현재 근거를 더 확인하기"
        : `${target?.name ?? "관련 node"}로 이동하기`,
      targetNodeId,
    };
  }) as [FollowupQuestion, FollowupQuestion];
};

export const knowledgeNodes: readonly KnowledgeNode[] = nodeCatalog.map(
  (node) => ({
    id: node.id,
    name: node.name,
    kind: node.kind,
    searchReason: `${node.name}의 공개 node와 이름이 일치합니다.`,
    context:
      node.id === "isolated"
        ? "공개된 node지만 현재 확인된 Relation이 없는 독립 기술입니다."
        : `${node.name} 중심의 공개 관측과 확인된 관계를 탐색합니다.`,
    claim:
      node.id === "isolated"
        ? "이 node에는 현재 공개 가능한 관계 근거가 없습니다."
        : `${node.name} 관련 공개 근거 묶음을 확인할 수 있습니다.`,
    activity: activityByLevel[node.activity],
    evidence: {
      sourceTitle:
        node.id === "isolated" ? "공개 상태 기록" : `${node.name} 공개 관측`,
      publisher: "ontology-map",
      publishedAt: "2026-08-31",
      quote:
        node.id === "isolated"
          ? "node 공개 상태만 확인됐으며 Relation은 공개되지 않았습니다."
          : "화면 검증을 위한 공개 관측 fixture입니다.",
      locator: "데스크톱 핵심 탐색 fixture",
    },
    followups: followupsFor(node.id),
  }),
);

const nodeById = new Map(knowledgeNodes.map((node) => [node.id, node]));
function requireDefaultNode(): KnowledgeNode {
  const node = knowledgeNodes[0];
  if (!node) throw new Error("기본 knowledge node가 필요합니다.");
  return node;
}
const defaultNode = requireDefaultNode();

export function getKnowledgeNode(id: string): KnowledgeNode {
  return nodeById.get(id) ?? defaultNode;
}

export function isKnownNode(id: string): boolean {
  return nodeById.has(id);
}

export function buildKnowledgeView(centerId: string): {
  nodes: KnowledgeViewNode[];
  relations: KnowledgeViewRelation[];
} {
  const center = isKnownNode(centerId) ? centerId : defaultNode.id;
  const direct = new Set(neighborIds(center));
  const twoHop = new Set<string>();
  for (const directId of direct) {
    for (const candidate of neighborIds(directId)) {
      if (candidate !== center && !direct.has(candidate)) twoHop.add(candidate);
    }
  }

  const tierFor = (id: string): NodeTier => {
    if (id === center) return "center";
    if (direct.has(id)) return "direct";
    if (twoHop.has(id)) return "twoHop";
    return "ambient";
  };

  return {
    nodes: knowledgeNodes.map((node) => ({ ...node, tier: tierFor(node.id) })),
    relations: knowledgeRelations.map((relation) => {
      const sourceTier = tierFor(relation.source);
      const targetTier = tierFor(relation.target);
      const tier =
        sourceTier === "center" ||
        targetTier === "center" ||
        sourceTier === "direct" ||
        targetTier === "direct"
          ? "direct"
          : sourceTier === "twoHop" || targetTier === "twoHop"
            ? "twoHop"
            : "ambient";
      return { ...relation, tier };
    }),
  };
}

export function searchKnowledgeNodes(query: string): KnowledgeNode[] {
  const normalized = query.trim().toLocaleLowerCase("ko-KR");
  if (!normalized) return [];
  return knowledgeNodes
    .filter((node) =>
      `${node.name} ${node.kind} ${node.searchReason}`
        .toLocaleLowerCase("ko-KR")
        .includes(normalized),
    )
    .slice(0, 5);
}

export function getFilamentOffsets(evidenceGroupCount: number): number[] {
  const count = Math.max(1, Math.round(evidenceGroupCount));
  if (count === 1) return [0];
  const spacing = Math.min(1.2, 6 / (count - 1));
  return Array.from(
    { length: count },
    (_, index) => (index - (count - 1) / 2) * spacing,
  );
}
