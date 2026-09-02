import { describe, expect, it } from "vitest";
import {
  buildKnowledgeView,
  getExplorationRecommendations,
  getFilamentOffsets,
  getKnowledgeNode,
  getRelationEvidence,
  isKnownNode,
  knowledgeNodes,
  knowledgeRelations,
  searchKnowledgeNodes,
} from "./data";

describe("knowledge view", () => {
  it("중심, 직접 이웃, 2단계 이웃과 주변 node를 구분한다", () => {
    const view = buildKnowledgeView("sk");
    expect(view.nodes.find((node) => node.id === "sk")?.tier).toBe("center");
    expect(view.nodes.find((node) => node.id === "sandisk")?.tier).toBe(
      "direct",
    );
    expect(view.nodes.find((node) => node.id === "hbf")?.tier).toBe("twoHop");
    expect(view.nodes.find((node) => node.id === "isolated")?.tier).toBe(
      "ambient",
    );
  });

  it("관계가 없는 공개 node에 가짜 Relation을 만들지 않는다", () => {
    const isolated = buildKnowledgeView("isolated");
    expect(
      isolated.relations.some(
        (relation) =>
          relation.source === "isolated" || relation.target === "isolated",
      ),
    ).toBe(false);
    expect(getKnowledgeNode("missing").id).toBe("sk");
  });

  it("후속 질문은 항상 두 개이며 공개 target을 가진다", () => {
    for (const node of knowledgeNodes) {
      expect(node.followups).toHaveLength(2);
      expect(
        node.followups.every((followup) => isKnownNode(followup.targetNodeId)),
      ).toBe(true);
    }
  });

  it("주요 3개 node에 인사이트를 세 개씩 제공한다", () => {
    for (const nodeId of ["sk", "sandisk", "hbf"]) {
      expect(getKnowledgeNode(nodeId).insights).toHaveLength(3);
      for (const insight of getKnowledgeNode(nodeId).insights) {
        expect(insight.evidenceIds.length).toBeGreaterThan(0);
        expect(insight.evidenceIds.every(getRelationEvidence)).toBe(true);
      }
    }
    expect(getKnowledgeNode("isolated").insights).toHaveLength(0);
  });

  it("탐색 추천은 직접 관계 두 개와 경로 및 주변부 후보를 하나씩 제공한다", () => {
    const recommendations = getExplorationRecommendations("sk", "90d");
    expect(recommendations).toHaveLength(4);
    expect(new Set(recommendations.map(({ node }) => node.id)).size).toBe(4);
    expect(
      recommendations.filter(({ status }) => status === "confirmedRelation"),
    ).toHaveLength(2);
    expect(
      recommendations.filter(({ status }) => status === "connectedPath"),
    ).toHaveLength(1);
    expect(
      recommendations.filter(({ status }) => status === "unconfirmed"),
    ).toHaveLength(1);
  });

  it("관계의 독립 근거 수와 근거 레코드 수가 일치한다", () => {
    for (const relation of knowledgeRelations) {
      expect(relation.evidence).toHaveLength(relation.evidenceGroupCount);
      expect(
        relation.evidence.every(
          (evidence) => getRelationEvidence(evidence.id) === evidence,
        ),
      ).toBe(true);
    }
  });

  it("검색 후보를 최대 다섯 개로 제한한다", () => {
    expect(searchKnowledgeNodes("기술").length).toBeLessThanOrEqual(5);
    expect(searchKnowledgeNodes("미연결")[0]?.id).toBe("isolated");
  });

  it("근거 묶음마다 필라멘트 하나를 만들고 5개 이후에는 간격을 좁힌다", () => {
    for (const count of [1, 3, 5, 6, 12]) {
      const offsets = getFilamentOffsets(count);
      expect(offsets).toHaveLength(count);
      expect(Math.max(...offsets) - Math.min(...offsets)).toBeLessThanOrEqual(
        4.8,
      );
    }
    const five = getFilamentOffsets(5);
    const six = getFilamentOffsets(6);
    const [fiveFirst = 0, fiveSecond = 0] = five;
    const [sixFirst = 0, sixSecond = 0] = six;
    expect(fiveSecond - fiveFirst).toBeCloseTo(1.2);
    expect(sixSecond - sixFirst).toBeLessThan(fiveSecond - fiveFirst);
    expect(knowledgeRelations.some((relation) => relation.conflict)).toBe(true);
  });
});
