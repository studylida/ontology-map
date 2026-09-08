import { PerspectiveCamera } from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { expect, it, vi } from "vitest";
import { approachesBoundary, watchBoundaryPan } from "./peripheralPan";

it("바깥 20%를 향한 이동만 감지하고 이동 종료 후 200ms 동안 기다린다", () => {
  vi.useFakeTimers();
  const nodes = [
    { x: -100, y: -100, z: 0 },
    { x: 100, y: 100, z: 0 },
  ];
  const origin = { x: 0, y: 0, z: 0 };
  expect(approachesBoundary(nodes, origin, { ...origin, x: 59 })).toBe(false);
  expect(
    approachesBoundary(nodes, { ...origin, x: 90 }, { ...origin, x: 70 }),
  ).toBe(false);
  const controls = new OrbitControls(
    new PerspectiveCamera(),
    document.createElement("div"),
  );
  const load = vi.fn();
  const stop = watchBoundaryPan(
    controls,
    () => nodes,
    () => true,
    load,
  );
  controls.target.x = 70;
  controls.dispatchEvent({ type: "change" });
  vi.advanceTimersByTime(300);
  expect(load).not.toHaveBeenCalled();
  controls.dispatchEvent({ type: "start" });
  controls.dispatchEvent({ type: "end" });
  vi.advanceTimersByTime(300);
  expect(load).not.toHaveBeenCalled();
  controls.dispatchEvent({ type: "start" });
  controls.target.x = 90;
  controls.dispatchEvent({ type: "end" });
  vi.advanceTimersByTime(150);
  controls.target.x += 1;
  controls.dispatchEvent({ type: "change" });
  vi.advanceTimersByTime(199);
  expect(load).not.toHaveBeenCalled();
  vi.advanceTimersByTime(1);
  expect(load).toHaveBeenCalledTimes(1);
  vi.advanceTimersByTime(1000);
  expect(load).toHaveBeenCalledTimes(1);
  stop();
  controls.dispose();
  vi.useRealTimers();
});

it("사용자 축소만 다음 페이지를 요청하고 확대와 프로그램 이동은 무시한다", () => {
  vi.useFakeTimers();
  const camera = new PerspectiveCamera();
  camera.position.z = 100;
  const controls = new OrbitControls(camera, document.createElement("div"));
  const load = vi.fn();
  const stop = watchBoundaryPan(
    controls,
    () => [],
    () => true,
    load,
  );
  controls.dispatchEvent({ type: "start" });
  camera.position.z = 80;
  controls.dispatchEvent({ type: "end" });
  vi.advanceTimersByTime(201);
  camera.position.z = 120;
  controls.dispatchEvent({ type: "change" });
  vi.advanceTimersByTime(201);
  expect(load).not.toHaveBeenCalled();
  controls.dispatchEvent({ type: "start" });
  camera.position.z = 150;
  controls.dispatchEvent({ type: "end" });
  vi.advanceTimersByTime(201);
  expect(load).toHaveBeenCalledTimes(1);
  stop();
  controls.dispose();
  vi.useRealTimers();
});

it("한쪽 가장자리에 있어도 다른 축의 경계 진입을 놓치지 않고 미세한 damping은 기다리지 않는다", () => {
  const nodes = [
    { x: -100, y: -100, z: 0 },
    { x: 100, y: 100, z: 0 },
  ];
  expect(
    approachesBoundary(nodes, { x: 90, y: 0, z: 0 }, { x: 90, y: 80, z: 0 }),
  ).toBe(true);
  expect(
    approachesBoundary(nodes, { x: 90, y: 80, z: 0 }, { x: 80, y: 70, z: 0 }),
  ).toBe(false);
  expect(
    approachesBoundary(nodes, { x: 90, y: 0, z: 0 }, { x: -80, y: 0, z: 0 }),
  ).toBe(true);
  vi.useFakeTimers();
  const camera = new PerspectiveCamera();
  camera.position.set(90, 0, 100);
  const controls = new OrbitControls(camera, document.createElement("div"));
  controls.target.set(90, 0, 0);
  const load = vi.fn();
  const stop = watchBoundaryPan(
    controls,
    () => nodes,
    () => true,
    load,
  );
  controls.dispatchEvent({ type: "start" });
  controls.target.y = camera.position.y = 80;
  controls.dispatchEvent({ type: "end" });
  for (let i = 0; i < 40; i++) {
    controls.target.y += 0.01;
    camera.position.y += 0.01;
    controls.dispatchEvent({ type: "change" });
    vi.advanceTimersByTime(16);
  }
  expect(load).toHaveBeenCalledTimes(1);
  stop();
  controls.dispose();
  vi.useRealTimers();
});
