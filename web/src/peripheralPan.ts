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
  const outward = (from: number, to: number, center: number, half: number) =>
    Math.abs(to - center) / half >= 0.6 && (to - center) * (to - from) > 0;
  return (
    outward(start.x, end.x, centerX, halfWidth) ||
    outward(start.y, end.y, centerY, halfHeight)
  );
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
  let lastTarget = controls.target.clone();
  let lastDistance = 0;
  let timer: number | undefined;
  const cancel = () => {
    window.clearTimeout(timer);
  };
  const schedule = () => {
    cancel();
    lastTarget = controls.target.clone();
    lastDistance = controls.object.position.distanceTo(controls.target);
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
    // damping의 미세한 잔여 이동 때문에 정지 판정을 계속 미루지 않는다.
    if (
      waiting &&
      (controls.target.distanceTo(lastTarget) > 0.5 ||
        Math.abs(
          controls.object.position.distanceTo(controls.target) - lastDistance,
        ) > 0.5)
    )
      schedule();
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
