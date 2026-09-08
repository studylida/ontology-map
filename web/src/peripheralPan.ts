import type { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import type { Position } from "./graphLayout";

export function approachesBoundary(
  nodes: Position[],
  start: Position,
  end: Position,
): boolean {
  if (!nodes.length) return false;
  let minX = Infinity,
    maxX = -Infinity,
    minY = Infinity,
    maxY = -Infinity;
  for (const node of nodes) {
    minX = Math.min(minX, node.x);
    maxX = Math.max(maxX, node.x);
    minY = Math.min(minY, node.y);
    maxY = Math.max(maxY, node.y);
  }
  const centerX = (minX + maxX) / 2,
    centerY = (minY + maxY) / 2;
  const halfWidth = Math.max(28, (maxX - minX) / 2);
  const halfHeight = Math.max(28, (maxY - minY) / 2);
  const distance = (point: Position) =>
    Math.max(
      Math.abs(point.x - centerX) / halfWidth,
      Math.abs(point.y - centerY) / halfHeight,
    );
  return distance(end) >= 0.6 && distance(end) > distance(start);
}

export function watchBoundaryPan(
  controls: OrbitControls,
  getNodes: () => Position[],
  canLoad: () => boolean,
  onBoundary: () => void,
): () => void {
  let start: Position | null = null;
  let waiting = false;
  let startDistance = 0;
  let timer: number | undefined;
  const cancel = () => {
    window.clearTimeout(timer);
  };
  const schedule = () => {
    cancel();
    timer = window.setTimeout(() => {
      waiting = false;
      if (
        start &&
        canLoad() &&
        (approachesBoundary(getNodes(), start, controls.target) ||
          controls.object.position.distanceTo(controls.target) >
            startDistance + 0.5)
      )
        onBoundary();
      start = null;
    }, 200);
  };
  const onStart = () => {
    cancel();
    waiting = false;
    start = controls.target.clone();
    startDistance = controls.object.position.distanceTo(controls.target);
  };
  const onEnd = () => {
    if (canLoad()) {
      waiting = true;
      schedule();
    }
  };
  const onChange = () => {
    if (waiting) schedule();
  };
  controls.addEventListener("start", onStart);
  controls.addEventListener("end", onEnd);
  controls.addEventListener("change", onChange);
  return () => {
    cancel();
    controls.removeEventListener("start", onStart);
    controls.removeEventListener("end", onEnd);
    controls.removeEventListener("change", onChange);
  };
}
