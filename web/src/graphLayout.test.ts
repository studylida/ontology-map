import { expect, it } from "vitest";
import type { KnowledgeNode } from "./data";
import { layoutTargets, retainGraphItems } from "./graphLayout";

it("새 중심의 현재 위치를 유지하고 이웃을 새 중심 주위에 결정적으로 배치한다", () => {
  const nodes = ["new", "neighbor", "two-hop"].map(
    (id) => ({ id }) as KnowledgeNode,
  );
  const anchor = { x: 80, y: -50, z: 12 };
  const positions = layoutTargets(nodes, "new", anchor);
  expect(positions.get("new")).toEqual(anchor);
  expect(positions.get("neighbor")).toMatchObject({ x: 108, y: -50 });
  expect(Math.abs(positions.get("two-hop")?.z ?? 100)).toBeLessThanOrEqual(32);
  expect(layoutTargets(nodes, "new", anchor)).toEqual(positions);
  expect(anchor).toEqual({ x: 80, y: -50, z: 12 });
});

it("전환 완료 뒤 새 응답에 없는 node와 Relation이 남지 않는다", () => {
  const retained = { id: "new" };
  const nodes = new Map([
    ["old", { id: "old" }],
    ["new", retained],
  ]);
  const links = new Map([["old-link", {}]]);
  retainGraphItems(nodes, new Set(["new"]));
  retainGraphItems(links, new Set());
  expect([...nodes.values()]).toEqual([retained]);
  expect(links.size).toBe(0);
});
