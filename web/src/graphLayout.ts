import type { KnowledgeNode } from "./data";

export interface Position {
  x: number;
  y: number;
  z: number;
}
export const depthLimit = 32;

export function depthTargetForNode(node: { id: string }): number {
  let hash = 0;
  for (const character of node.id)
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  return ((hash % 2001) / 1000 - 1) * depthLimit;
}

export function layoutTargets(
  nodes: KnowledgeNode[],
  centerId: string,
  anchor: Position,
): Map<string, Position> {
  let index = 0;
  return new Map(
    nodes.map((node) => {
      if (node.id === centerId) return [node.id, { ...anchor }];
      const angle = index * 2.399963229728653;
      const distance = 28 * Math.sqrt(++index);
      return [
        node.id,
        {
          x: anchor.x + Math.cos(angle) * distance,
          y: anchor.y + Math.sin(angle) * distance,
          z: depthTargetForNode(node),
        },
      ];
    }),
  );
}

export function retainGraphItems<T>(items: Map<string, T>, ids: Set<string>) {
  for (const id of items.keys()) if (!ids.has(id)) items.delete(id);
}
