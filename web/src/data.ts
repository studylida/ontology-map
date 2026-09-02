export type TimeRange = "90d" | "1y";
export type NodeKind = "사람" | "회사" | "기술" | "주제" | "사건";
export type NodeTier = "center" | "direct" | "twoHop" | "ambient";

export interface EvidenceTrace {
  sourceTitle: string;
  publisher: string;
  publishedAt: string;
  quote: string;
  locator: string;
  sourceUrl?: string;
}

export interface RelationEvidence extends EvidenceTrace {
  id: string;
  claim: string;
  stance: "support" | "conflict";
}

export interface FollowupQuestion {
  id: string;
  text: string;
  targetNodeId: string;
}

export interface InsightReport {
  id: string;
  title: string;
  summary: string;
  verifiedFact: string;
  synthesis: string;
  evidenceIds: readonly string[];
  caveat: string;
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
  insights: readonly InsightReport[];
  followups: readonly [FollowupQuestion, FollowupQuestion];
}

export interface KnowledgeRelation {
  id: string;
  source: string;
  target: string;
  label: string;
  evidenceGroupCount: number;
  evidence: readonly RelationEvidence[];
  conflict?: boolean;
}

export type RecommendationStatus =
  | "confirmedRelation"
  | "connectedPath"
  | "unconfirmed";

export interface ExplorationRecommendation {
  node: KnowledgeNode;
  reason: string;
  status: RecommendationStatus;
  evidenceGroupCount?: number;
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

const relationCatalog: readonly [string, string, number, boolean?][] = [
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
  ["standard", "ocp", 1, true],
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
];

const nodeNameById = new Map(nodeCatalog.map((node) => [node.id, node.name]));

function buildRelationEvidence(
  relationId: string,
  source: string,
  target: string,
  count: number,
  conflict: boolean,
): RelationEvidence[] {
  const sourceName = nodeNameById.get(source) ?? source;
  const targetName = nodeNameById.get(target) ?? target;
  return Array.from({ length: count }, (_, index) => ({
    id: `${relationId}-evidence-${index + 1}`,
    claim: `${sourceName}–${targetName} 사이의 공개 관계가 관측되었습니다.`,
    stance: conflict && index === count - 1 ? "conflict" : "support",
    sourceTitle: `${sourceName}–${targetName} 공개 근거 ${index + 1}`,
    publisher: "ontology-map 공개 관측",
    publishedAt: `2026-08-${String(12 + index).padStart(2, "0")}`,
    quote: `${sourceName}와 ${targetName}의 관계를 확인할 수 있는 공개 원문 인용입니다.`,
    locator: `관계 근거 ${index + 1} · 공개 자료 위치`,
  }));
}

export const knowledgeRelations: readonly KnowledgeRelation[] =
  relationCatalog.map(([source, target, count, conflict = false], index) => {
    const id = `link-${index}`;
    const evidence = buildRelationEvidence(id, source, target, count, conflict);
    return {
      id,
      source,
      target,
      label: "공개 관계",
      evidenceGroupCount: evidence.length,
      evidence,
      conflict,
    };
  });

function evidenceIdsFor(
  relationIndex: number,
  limit: number,
): readonly string[] {
  return (
    knowledgeRelations[relationIndex]?.evidence
      .slice(0, limit)
      .map((evidence) => evidence.id) ?? []
  );
}

function combinedEvidenceIds(
  selections: readonly [number, number][],
): readonly string[] {
  return selections.flatMap(([relationIndex, limit]) =>
    evidenceIdsFor(relationIndex, limit),
  );
}

const activityByLevel: Record<ActivityLevel, Record<TimeRange, number>> = {
  low: { "90d": 32, "1y": 52 },
  medium: { "90d": 64, "1y": 82 },
  high: { "90d": 92, "1y": 100 },
};

const insightsByNodeId: Partial<Record<string, readonly InsightReport[]>> = {
  sk: [
    {
      id: "sk-hbf-position",
      title: "HBF 표준화 참여가 AI 메모리 협상력을 넓힐 수 있다",
      summary:
        "SK하이닉스는 제품 공개와 표준화 활동을 함께 이어가며 AI 메모리 생태계에서 영향력을 넓힐 여지가 있습니다.",
      verifiedFact:
        "현재 fixture에는 SK하이닉스와 FMS 2026 HBF 발표, HBF 표준화 착수 사이의 공개 관계가 연결되어 있습니다.",
      synthesis:
        "제품 성능만 강조하기보다 표준 논의와 생태계 협력에 함께 참여하는 전략이 향후 파트너 협상에서 유리하게 작용할 수 있습니다.",
      evidenceIds: combinedEvidenceIds([
        [1, 3],
        [2, 2],
      ]),
      caveat:
        "표준화 참여가 실제 계약이나 매출로 이어졌다는 근거는 이 데모에 포함되어 있지 않습니다.",
    },
    {
      id: "sk-sandisk-context",
      title: "SanDisk와의 연결은 협력과 경쟁을 함께 살펴봐야 한다",
      summary:
        "두 회사의 관계는 단일한 협력 구도보다 기술 생태계와 공급망 맥락을 함께 볼 때 더 잘 이해할 수 있습니다.",
      verifiedFact:
        "SK하이닉스와 SanDisk는 직접 연결되어 있고, SanDisk는 HBF와도 별도의 공개 관계를 가집니다.",
      synthesis:
        "공통 기술 생태계에서의 접점은 협력 기회를 만들지만 같은 시장을 두고 경쟁하는 상황도 함께 만들 수 있습니다.",
      evidenceIds: combinedEvidenceIds([
        [0, 3],
        [14, 1],
      ]),
      caveat:
        "현재 관계 정보만으로 두 회사의 계약 조건이나 경쟁 우위를 판단할 수는 없습니다.",
    },
    {
      id: "sk-nand-execution",
      title: "375단 NAND 공개 이후에는 실행 속도가 중요한 관찰 지점이다",
      summary:
        "기술 공개 자체보다 제품 전환과 생태계 확산이 얼마나 빠르게 이어지는지가 다음 관찰 지점입니다.",
      verifiedFact:
        "SK하이닉스는 375단 4D NAND 공개 사건과 연결되어 있고, 해당 사건은 375단 4D NAND 기술 node로 이어집니다.",
      synthesis:
        "발표 이후의 제조 전환과 적용 사례가 확인되면 기술 공개의 사업적 의미를 더 구체적으로 평가할 수 있습니다.",
      evidenceIds: evidenceIdsFor(5, 3),
      caveat:
        "양산 일정, 수율과 고객 적용 정보는 현재 fixture에 포함되어 있지 않습니다.",
    },
  ],
  sandisk: [
    {
      id: "sandisk-hbf-boundary",
      title: "HBF 협력은 SK하이닉스와의 경쟁 경계를 흐릴 수 있다",
      summary:
        "공통 기술 생태계에 참여하면 경쟁사 사이에서도 표준과 시장 확대를 위한 협력이 생길 수 있습니다.",
      verifiedFact:
        "SanDisk는 SK하이닉스와 직접 연결되어 있고 HBF와도 별도의 공개 관계를 가집니다.",
      synthesis:
        "HBF 생태계의 확대가 양사 모두에게 이익이 된다면 제품 경쟁과 기술 협력이 동시에 나타날 수 있습니다.",
      evidenceIds: combinedEvidenceIds([
        [0, 3],
        [14, 1],
      ]),
      caveat:
        "이 연결은 공동 개발이나 공식 제휴를 뜻하지 않으며 공개 관계의 맥락을 추가로 확인해야 합니다.",
    },
    {
      id: "sandisk-ai-demand",
      title: "Google과 Tenstorrent 연결은 AI 인프라 수요 관찰 범위를 넓힌다",
      summary:
        "SanDisk 주변의 AI 기업 연결은 저장장치 수요를 최종 제품이 아니라 인프라 구조 관점에서 살펴보게 합니다.",
      verifiedFact:
        "현재 fixture에서 SanDisk는 Google과 Tenstorrent에 각각 직접 연결되어 있습니다.",
      synthesis:
        "서로 다른 AI 인프라 참여자의 요구를 함께 보면 고성능 저장장치가 필요한 사용 맥락을 더 넓게 추정할 수 있습니다.",
      evidenceIds: combinedEvidenceIds([
        [10, 1],
        [11, 1],
      ]),
      caveat:
        "현재 데이터에는 구매 계약, 채택 규모와 구체적인 제품 정보가 없습니다.",
    },
    {
      id: "sandisk-evidence-balance",
      title: "관계 수보다 근거의 성격을 먼저 비교해야 한다",
      summary:
        "여러 회사와 기술에 연결되어 있다는 사실만으로 전략적 중요도를 단정하기는 어렵습니다.",
      verifiedFact:
        "SanDisk의 관계마다 독립 근거 묶음 수가 다르며 SK하이닉스와 HBF 관계가 주변 회사 관계보다 많습니다.",
      synthesis:
        "근거 수가 많은 관계부터 원문 맥락을 확인하면 연결의 의미와 지속성을 더 효율적으로 검토할 수 있습니다.",
      evidenceIds: evidenceIdsFor(0, 3),
      caveat:
        "근거 묶음 수는 관계의 확신 점수나 사업적 중요도를 직접 나타내지 않습니다.",
    },
  ],
  hbf: [
    {
      id: "hbf-ecosystem",
      title: "HBF는 제품보다 생태계 조정 능력이 중요한 기술이다",
      summary:
        "HBF 주변에는 회사, 표준과 AI 메모리 주제가 함께 연결되어 있어 단일 제품보다 생태계 관점이 필요합니다.",
      verifiedFact:
        "HBF는 SK하이닉스 관련 발표, SanDisk, HBF 표준화 착수와 AI 메모리 node에 연결되어 있습니다.",
      synthesis:
        "다양한 참여자가 같은 방향으로 움직일 수 있도록 인터페이스와 적용 맥락을 조정하는 능력이 확산 속도에 영향을 줄 수 있습니다.",
      evidenceIds: combinedEvidenceIds([
        [8, 1],
        [14, 3],
        [19, 1],
      ]),
      caveat:
        "현재 fixture만으로 각 참여자의 역할과 표준화 주도권을 판단할 수는 없습니다.",
    },
    {
      id: "hbf-interface",
      title: "UCIe 연결이 계층형 메모리 확장성의 관찰 지점이다",
      summary:
        "HBF와 UCIe의 연결은 메모리 기술을 개별 부품이 아니라 시스템 인터페이스 관점에서 보게 합니다.",
      verifiedFact:
        "HBF는 UCIe에 연결되어 있고 UCIe는 CPU와 GPU node로 이어집니다.",
      synthesis:
        "서로 다른 연산 장치와 메모리 계층을 연결하는 방식이 구체화될수록 HBF의 적용 범위를 더 명확히 평가할 수 있습니다.",
      evidenceIds: combinedEvidenceIds([
        [9, 1],
        [20, 1],
        [21, 1],
      ]),
      caveat:
        "현재 데이터에는 인터페이스 사양, 성능 결과와 호환성 검증이 포함되어 있지 않습니다.",
    },
    {
      id: "hbf-standard-gap",
      title: "표준화 속도와 상용화 근거 사이의 간극을 확인해야 한다",
      summary:
        "표준 관련 연결이 많아도 상용화 준비 수준은 별도의 근거로 확인해야 합니다.",
      verifiedFact:
        "HBF는 표준화 착수와 OCP 공개 표준에 연결되어 있으며 표준화 착수와 OCP 사이에는 충돌 관계가 표시됩니다.",
      synthesis:
        "충돌 근거를 숨기지 않고 비교하면 표준 논의가 합의 단계인지 경쟁 단계인지 더 신중하게 판단할 수 있습니다.",
      evidenceIds: combinedEvidenceIds([
        [17, 1],
        [18, 1],
        [13, 1],
      ]),
      caveat:
        "충돌 표시는 어느 한쪽이 틀렸다는 뜻이 아니라 공개 근거 사이의 불일치를 뜻합니다.",
    },
  ],
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
    insights: insightsByNodeId[node.id] ?? [],
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

function relationBetween(
  sourceId: string,
  targetId: string,
): KnowledgeRelation | undefined {
  return knowledgeRelations.find(
    (relation) =>
      (relation.source === sourceId && relation.target === targetId) ||
      (relation.source === targetId && relation.target === sourceId),
  );
}

function compareRecommendationCandidates(
  centerId: string,
  timeRange: TimeRange,
): (left: KnowledgeViewNode, right: KnowledgeViewNode) => number {
  return (left, right) => {
    const evidenceDifference =
      (relationBetween(centerId, right.id)?.evidenceGroupCount ?? 0) -
      (relationBetween(centerId, left.id)?.evidenceGroupCount ?? 0);
    return (
      evidenceDifference ||
      right.activity[timeRange] - left.activity[timeRange] ||
      left.name.localeCompare(right.name, "ko-KR")
    );
  };
}

function recommendationFor(
  centerId: string,
  candidate: KnowledgeViewNode,
): ExplorationRecommendation {
  const relation = relationBetween(centerId, candidate.id);
  if (relation) {
    return {
      node: candidate,
      reason: `${candidate.name} 관련 공개 관계를 근거와 함께 살펴봅니다.`,
      status: "confirmedRelation",
      evidenceGroupCount: relation.evidenceGroupCount,
    };
  }

  if (candidate.tier === "twoHop") {
    const viaId = neighborIds(centerId).find((neighborId) =>
      neighborIds(neighborId).includes(candidate.id),
    );
    return {
      node: candidate,
      reason: `${getKnowledgeNode(viaId ?? centerId).name}에서 이어지는 공개 경로를 살펴봅니다.`,
      status: "connectedPath",
    };
  }

  return {
    node: candidate,
    reason: "현재 지도 주변의 공개 노드를 새 탐색 출발점으로 살펴봅니다.",
    status: "unconfirmed",
  };
}

export function getExplorationRecommendations(
  centerId: string,
  timeRange: TimeRange,
): ExplorationRecommendation[] {
  const view = buildKnowledgeView(centerId);
  const compare = compareRecommendationCandidates(centerId, timeRange);
  const candidatesByTier = (tier: NodeTier) =>
    view.nodes.filter((node) => node.tier === tier).sort(compare);
  const preferred = [
    ...candidatesByTier("direct").slice(0, 2),
    ...candidatesByTier("twoHop").slice(0, 1),
    ...candidatesByTier("ambient").slice(0, 1),
  ];
  const preferredIds = new Set(preferred.map((node) => node.id));
  const fallback = view.nodes
    .filter((node) => node.id !== centerId && !preferredIds.has(node.id))
    .sort(compare);
  return [...preferred, ...fallback]
    .slice(0, 4)
    .map((candidate) => recommendationFor(centerId, candidate));
}

export function getRelationEvidence(
  evidenceId: string,
): RelationEvidence | undefined {
  for (const relation of knowledgeRelations) {
    const evidence = relation.evidence.find((item) => item.id === evidenceId);
    if (evidence) return evidence;
  }
  return undefined;
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
  const spacing = count <= 5 ? 1.2 : 4.8 / (count - 1);
  return Array.from(
    { length: count },
    (_, index) => (index - (count - 1) / 2) * spacing,
  );
}
