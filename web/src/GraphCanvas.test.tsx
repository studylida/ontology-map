import { act, cleanup, render } from "@testing-library/react";
import * as THREE from "three";
import type { CSS2DRenderer } from "three/examples/jsm/renderers/CSS2DRenderer.js";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { ExplorationView, KnowledgeRelation } from "./data";
import { GraphCanvas } from "./GraphCanvas";

const harness = vi.hoisted(() => ({
  camera: null as THREE.PerspectiveCamera | null,
  target: null as THREE.Vector3 | null,
  navigationEnabled: true,
  labels: null as CSS2DRenderer | null,
  scene: null as THREE.Scene | null,
  options: new Map<string, (...args: never[]) => unknown>(),
  nodes: new Map<string, THREE.Group>(),
  links: new Map<string, THREE.Group>(),
}));

// WebGL 경계만 대체하고 실제 GraphCanvas의 effect·frame·DOM 수명주기를 실행한다.
vi.mock("3d-force-graph", () => ({
  default: function FakeGraph(
    container: HTMLElement,
    config: { extraRenderers: CSS2DRenderer[] },
  ) {
    harness.labels = config.extraRenderers[0] ?? null;
    const camera = new THREE.PerspectiveCamera();
    const scene = new THREE.Scene();
    harness.scene = scene;
    const controls = {
      object: camera,
      target: new THREE.Vector3(),
      mouseButtons: {},
      touches: {},
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      update: vi.fn(),
    };
    harness.camera = camera;
    harness.target = controls.target;
    let nodeFactory: (node: { id: string }) => THREE.Group;
    let linkFactory: (link: KnowledgeRelation) => THREE.Group;
    const dimensions = { width: 800, height: 600 };
    const graph: Record<string, unknown> = {};
    const proxy = new Proxy(graph, {
      get: (_, key: string) => {
        if (key === "controls") return () => controls;
        if (key === "camera") return () => camera;
        if (key === "scene") return () => scene;
        if (key === "cameraPosition")
          return (position: THREE.Vector3, target: THREE.Vector3) => {
            camera.position.copy(position);
            controls.target.copy(target);
            return proxy;
          };
        if (key === "enableNavigationControls")
          return (enabled: boolean) => {
            harness.navigationEnabled = enabled;
            return proxy;
          };
        if (key === "renderer") return () => ({});
        if (key === "postProcessingComposer")
          return () => ({ addPass: vi.fn() });
        if (key === "width" || key === "height")
          return (value?: number) =>
            value === undefined ? dimensions[key] : proxy;
        if (key === "nodeThreeObject")
          return (factory: typeof nodeFactory) => {
            nodeFactory = factory;
            return proxy;
          };
        if (key === "linkThreeObject")
          return (factory: typeof linkFactory) => {
            linkFactory = factory;
            harness.options.set(key, factory);
            return proxy;
          };
        if (key === "graphData")
          return (data: {
            nodes: { id: string }[];
            links: KnowledgeRelation[];
          }) => {
            // 실제 renderer처럼 data 교체 후 이전 객체가 늦게 제거되는 경우도 실행한다.
            for (const [id, visual] of harness.nodes) {
              if (!data.nodes.some((node) => node.id === id)) {
                container.append(visual.userData.label.element);
                window.setTimeout(() => {
                  scene.remove(visual);
                  harness.nodes.delete(id);
                }, 0);
              }
            }
            for (const node of data.nodes) {
              const visual = nodeFactory(node);
              if (visual.parent !== scene) scene.add(visual);
              harness.nodes.set(node.id, visual);
              container.append(visual.userData.label.element);
            }
            for (const link of data.links) {
              const visual = linkFactory(link);
              // 설치된 three-forcegraph가 custom link에 지정하는 group 순서다.
              visual.renderOrder = 10;
              harness.links.set(link.id, visual);
            }
            return proxy;
          };
        return (...args: never[]) => {
          if (typeof args[0] === "function") harness.options.set(key, args[0]);
          return proxy;
        };
      },
    });
    return proxy;
  },
}));

beforeEach(() => {
  harness.options.clear();
  harness.nodes.clear();
  harness.links.clear();
  vi.useFakeTimers();
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) =>
    window.setTimeout(() => callback(performance.now()), 16),
  );
  vi.stubGlobal("cancelAnimationFrame", (id: number) =>
    window.clearTimeout(id),
  );
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
  vi.stubGlobal("matchMedia", () => ({ matches: false }));
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
});
afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const node = (id: string, tier: "center" | "direct" | "ambient") => ({
  id,
  name: id,
  kind: "기술",
  kindCode: "TECHNOLOGY",
  tier,
  activityEvidenceGroupCount: 1,
});
const view: ExplorationView = {
  centerId: "1",
  context: "",
  nodes: [node("1", "center"), node("2", "direct")],
  relations: [],
  recommendations: [],
  followups: [],
};
const props = () => ({
  view,
  introStarted: false,
  pendingNodeId: null,
  panelOpen: true,
  onReady: vi.fn(),
  onIntroComplete: vi.fn(),
  onPanBoundary: vi.fn(),
  onSelect: vi.fn(),
  onEvidence: vi.fn(),
  onTransitionComplete: vi.fn(),
});

it("첫 frame 이전의 초기 page 병합에도 준비 신호를 전달하고 label을 중복하지 않는다", () => {
  const callbacks = props();
  const page = { ...view, nodes: [...view.nodes, node("3", "ambient")] };
  const { rerender, container, unmount } = render(
    <GraphCanvas {...callbacks} />,
  );
  rerender(<GraphCanvas {...callbacks} view={page} />);
  act(() => vi.advanceTimersByTime(16));
  expect(callbacks.onReady).toHaveBeenCalledTimes(1);
  expect(container.querySelectorAll("[data-node-id]")).toHaveLength(3);
  rerender(<GraphCanvas {...callbacks} view={page} introStarted />);
  act(() => vi.advanceTimersByTime(2000));
  expect(callbacks.onIntroComplete).toHaveBeenCalledTimes(1);
  const label = container.querySelector("[data-node-id='3']");
  rerender(<GraphCanvas {...callbacks} introStarted />);
  act(() => vi.advanceTimersByTime(16));
  expect(label?.isConnected).toBe(false);
  expect(container.querySelectorAll("[data-node-id]")).toHaveLength(2);
  unmount();
  expect(document.querySelectorAll("[data-node-id]")).toHaveLength(0);
});

it("진행 중 전환을 취소하고 원래 중심으로 돌아오면 busy 상태도 해제한다", () => {
  const callbacks = props();
  const { rerender, container } = render(<GraphCanvas {...callbacks} />);
  act(() => vi.advanceTimersByTime(16));
  rerender(<GraphCanvas {...callbacks} introStarted />);
  act(() => vi.advanceTimersByTime(2000));
  const next = {
    ...view,
    centerId: "2",
    nodes: [node("2", "center"), node("1", "direct")],
  };
  rerender(<GraphCanvas {...callbacks} view={next} introStarted />);
  act(() => vi.advanceTimersByTime(160));
  expect(container.querySelector("section")?.getAttribute("aria-busy")).toBe(
    "true",
  );
  rerender(<GraphCanvas {...callbacks} introStarted />);
  expect(container.querySelector("section")?.getAttribute("aria-busy")).toBe(
    "false",
  );
  expect(callbacks.onTransitionComplete).not.toHaveBeenCalled();
});

it("노드 장식이 간선 선택을 가로채지 않고 이동한 선을 클릭하면 관계 정보를 전달한다", () => {
  const callbacks = props();
  const relation: KnowledgeRelation = {
    id: "edge",
    source: "1",
    target: "2",
    label: "관련 기술",
    tier: "direct",
    directionality: "DIRECTED",
    evidenceGroupCount: 3,
    conflict: false,
  };
  render(
    <GraphCanvas {...callbacks} view={{ ...view, relations: [relation] }} />,
  );
  const nodeVisual = harness.nodes.get("1");
  const linkVisual = harness.links.get("edge");
  if (!nodeVisual || !linkVisual) throw new Error("graph 객체가 없습니다.");
  expect(nodeVisual.renderOrder).toBeGreaterThan(linkVisual.renderOrder);
  nodeVisual.updateMatrixWorld(true);
  const raycaster = new THREE.Raycaster(
    new THREE.Vector3(4, 0, 100),
    new THREE.Vector3(0, 0, -1),
  );
  raycaster.camera = new THREE.PerspectiveCamera();
  expect(raycaster.intersectObject(nodeVisual, true)).toHaveLength(0);
  const update = harness.options.get("linkPositionUpdate") as unknown as (
    object: THREE.Group,
    coordinates: {
      start: { x: number; y: number; z: number };
      end: { x: number; y: number; z: number };
    },
  ) => void;
  update(linkVisual, {
    start: { x: 0, y: 0, z: 0 },
    end: { x: 40, y: 0, z: 0 },
  });
  raycaster.set(new THREE.Vector3(20, 2, 100), new THREE.Vector3(0, 0, -1));
  linkVisual.updateMatrixWorld(true);
  expect(raycaster.intersectObject(linkVisual, true).length).toBeGreaterThan(0);
  update(linkVisual, {
    start: { x: 200, y: 0, z: 0 },
    end: { x: 240, y: 0, z: 0 },
  });
  raycaster.set(new THREE.Vector3(220, 2, 100), new THREE.Vector3(0, 0, -1));
  expect(raycaster.intersectObject(linkVisual, true).length).toBeGreaterThan(0);
  const click = harness.options.get("onLinkClick") as unknown as (
    link: KnowledgeRelation,
  ) => void;
  act(() => click(relation));
  expect(callbacks.onEvidence).toHaveBeenCalledWith({
    id: "edge",
    label: expect.stringContaining("관련 기술"),
  });
  expect(callbacks.onSelect).not.toHaveBeenCalled();
});

function visual(id: string) {
  const value = harness.nodes.get(id);
  if (!value) throw new Error(`node ${id}가 없습니다.`);
  return value;
}

it("기간 변경은 위치와 camera를 유지하며 320ms 보간하고 page 도착과 재선택에도 이전 목표로 돌아가지 않는다", () => {
  const callbacks = props();
  const { rerender } = render(<GraphCanvas {...callbacks} />);
  act(() => vi.advanceTimersByTime(16));
  rerender(<GraphCanvas {...callbacks} introStarted />);
  act(() => vi.advanceTimersByTime(2000));
  const before = visual("1").userData.radius;
  const position = visual("1").position.clone();
  const camera = harness.camera?.position.clone();
  const target = harness.target?.clone();
  const larger = {
    ...view,
    nodes: view.nodes.map((n) => ({ ...n, activityEvidenceGroupCount: 6 })),
  };
  rerender(<GraphCanvas {...callbacks} introStarted view={larger} />);
  expect(visual("1").userData.radius).toBe(before);
  act(() => vi.advanceTimersByTime(160));
  const halfway = visual("1").userData.radius;
  expect(halfway).toBeGreaterThan(before);
  rerender(
    <GraphCanvas
      {...callbacks}
      introStarted
      view={{ ...larger, nodes: [...larger.nodes, node("3", "ambient")] }}
    />,
  );
  act(() => vi.advanceTimersByTime(160));
  const end = visual("1").userData.radius;
  expect(end).toBeGreaterThan(halfway);
  act(() => vi.advanceTimersByTime(400));
  expect(visual("1").userData.radius).toBe(end);
  expect(visual("1").position).toEqual(position);
  expect(harness.camera?.position).toEqual(camera);
  expect(harness.target).toEqual(target);
  rerender(<GraphCanvas {...callbacks} introStarted />);
  act(() => vi.advanceTimersByTime(160));
  const interrupted = visual("1").userData.radius;
  rerender(<GraphCanvas {...callbacks} introStarted view={larger} />);
  expect(visual("1").userData.radius).toBe(interrupted);
  act(() => vi.advanceTimersByTime(1000));
  expect(visual("1").userData.radius).toBe(end);
  expect(callbacks.onTransitionComplete).not.toHaveBeenCalled();
  vi.stubGlobal("matchMedia", () => ({ matches: true }));
  rerender(<GraphCanvas {...callbacks} introStarted />);
  expect(visual("1").userData.radius).toBe(before);
});

it("응답 대기 중 선택 node는 고정하고 주변만 떠 움직이다 현재 화면 위치에서 전환한다", () => {
  const callbacks = props();
  const { rerender } = render(<GraphCanvas {...callbacks} />);
  act(() => vi.advanceTimersByTime(16));
  rerender(<GraphCanvas {...callbacks} introStarted />);
  act(() => vi.advanceTimersByTime(2000));
  const selected = visual("2").position.clone();
  const neighbor = visual("1").position.clone();
  const camera = harness.camera?.position.clone();
  rerender(<GraphCanvas {...callbacks} introStarted pendingNodeId="2" />);
  act(() => vi.advanceTimersByTime(400));
  expect(visual("2").position).toEqual(selected);
  expect(visual("1").position).not.toEqual(neighbor);
  expect(harness.camera?.position).toEqual(camera);
  const floating = visual("1").position.clone();
  const next = {
    ...view,
    centerId: "2",
    nodes: [node("2", "center"), node("1", "direct")],
  };
  rerender(<GraphCanvas {...callbacks} introStarted view={next} />);
  expect(visual("1").position).toEqual(floating);
  expect(visual("2").position).toEqual(selected);
  act(() => vi.advanceTimersByTime(1300));
  const settled = visual("1").position.clone();
  act(() => vi.advanceTimersByTime(1000));
  expect(visual("1").position).toEqual(settled);
  expect(callbacks.onTransitionComplete).toHaveBeenCalledExactlyOnceWith("2");
});

it("대기 중 재선택·오류 종료는 떠 움직임을 정리하고 reduced motion에서는 움직이지 않는다", () => {
  const callbacks = props();
  const { rerender, container } = render(<GraphCanvas {...callbacks} />);
  act(() => vi.advanceTimersByTime(16));
  rerender(<GraphCanvas {...callbacks} introStarted />);
  act(() => vi.advanceTimersByTime(2000));
  rerender(<GraphCanvas {...callbacks} introStarted pendingNodeId="2" />);
  act(() => vi.advanceTimersByTime(200));
  const selected = visual("1").position.clone();
  rerender(<GraphCanvas {...callbacks} introStarted pendingNodeId="1" />);
  act(() => vi.advanceTimersByTime(200));
  expect(visual("1").position).toEqual(selected);
  rerender(<GraphCanvas {...callbacks} introStarted />);
  const stopped = visual("2").position.clone();
  act(() => vi.advanceTimersByTime(1000));
  expect(visual("2").position).toEqual(stopped);
  expect(container.querySelector("section")?.getAttribute("aria-busy")).toBe(
    "false",
  );
  vi.stubGlobal("matchMedia", () => ({ matches: true }));
  rerender(<GraphCanvas {...callbacks} introStarted pendingNodeId="1" />);
  act(() => vi.advanceTimersByTime(1000));
  expect(visual("2").position).toEqual(stopped);
  expect(callbacks.onTransitionComplete).not.toHaveBeenCalled();
});

it("미리보기는 중심·초점 연결을 파란색으로, 충돌을 우선 빨간 점선으로 표시하고 발광을 숨긴다", () => {
  const callbacks = props();
  const direct = {
    id: "direct",
    source: "1",
    target: "2",
    label: "연결",
    directionality: "DIRECTED" as const,
    evidenceGroupCount: 3,
    conflict: false,
    tier: "direct" as const,
  };
  const remote = {
    ...direct,
    id: "remote",
    source: "2",
    target: "3",
    tier: "threeHop" as const,
  };
  const conflict = { ...remote, id: "conflict", conflict: true };
  const data = {
    ...view,
    nodes: [...view.nodes, node("3", "ambient")],
    relations: [direct, remote, conflict],
  };
  const { rerender, getByRole } = render(
    <GraphCanvas {...callbacks} view={data} designPreview />,
  );
  act(() => vi.advanceTimersByTime(16));
  rerender(
    <GraphCanvas {...callbacks} view={data} designPreview introStarted />,
  );
  act(() => vi.advanceTimersByTime(2000));
  const color = (id: string) =>
    harness.links.get(id)?.userData.lines[0].material.color.getHexString();
  expect(color("direct")).toBe("72a7ff");
  expect(color("remote")).toBe("7b8797");
  expect(color("conflict")).toBe("f26d78");
  expect(harness.links.get("direct")?.userData.lines).toHaveLength(3);
  expect(
    harness.links.get("conflict")?.userData.lines[0].material,
  ).toBeInstanceOf(THREE.LineDashedMaterial);
  expect(visual("1").userData.halo.visible).toBe(false);
  expect(visual("1").userData.core.visible).toBe(false);
  expect(visual("1").userData.shell.visible).toBe(false);
  const isVisible = () => harness.options.get("linkVisibility");
  expect(isVisible()?.(remote as never)).toBe(false);
  act(() => getByRole("button", { name: "3 · 기술" }).focus());
  expect(isVisible()?.(remote as never)).toBe(true);
  expect(isVisible()?.(conflict as never)).toBe(true);
  const recreate = harness.options.get("linkThreeObject");
  if (!recreate) throw new Error("간선 생성기가 없습니다.");
  const revealed = recreate(remote as never) as THREE.Group;
  const revealedColor = () =>
    (
      (revealed.children[0] as THREE.Line).material as THREE.LineBasicMaterial
    ).color.getHexString();
  expect(revealedColor()).toBe("72a7ff");
  expect(color("remote")).toBe("72a7ff");
  expect(color("conflict")).toBe("f26d78");
  act(() => getByRole("button", { name: "3 · 기술" }).blur());
  expect(isVisible()?.(remote as never)).toBe(false);
  expect(revealedColor()).toBe("7b8797");
  expect(color("direct")).toBe("72a7ff");
});

it("미리보기 준비 이동은 2단위 이내에서 멈추고 응답 순간 위치·속도를 이어받으며 오류 때 복귀한다", () => {
  const callbacks = props();
  const { rerender } = render(<GraphCanvas {...callbacks} designPreview />);
  act(() => vi.advanceTimersByTime(16));
  rerender(<GraphCanvas {...callbacks} designPreview introStarted />);
  act(() => vi.advanceTimersByTime(4000));
  const selected = visual("2").position.clone();
  const origin = visual("1").position.clone();
  const camera = harness.camera?.position.clone();
  rerender(
    <GraphCanvas {...callbacks} designPreview introStarted pendingNodeId="2" />,
  );
  act(() => vi.advanceTimersByTime(80));
  const position = visual("1").position.clone();
  const velocity = visual("1").userData.velocity.clone();
  expect(position.distanceTo(origin)).toBeGreaterThan(0);
  expect(position.distanceTo(origin)).toBeLessThanOrEqual(2);
  const next = {
    ...view,
    centerId: "2",
    nodes: [node("2", "center"), node("1", "direct")],
  };
  rerender(
    <GraphCanvas {...callbacks} designPreview introStarted view={next} />,
  );
  expect(visual("1").position).toEqual(position);
  expect(visual("1").userData.velocity).toEqual(velocity);
  expect(visual("2").position).toEqual(selected);
  expect(harness.camera?.position).toEqual(camera);
  act(() => vi.advanceTimersByTime(1300));
  const settled = visual("2").position.clone();
  rerender(
    <GraphCanvas
      {...callbacks}
      designPreview
      introStarted
      view={next}
      pendingNodeId="1"
    />,
  );
  act(() => vi.advanceTimersByTime(400));
  const waiting = visual("2").position.clone();
  expect(waiting.distanceTo(settled)).toBeCloseTo(2);
  act(() => vi.advanceTimersByTime(3000));
  expect(visual("2").position).toEqual(waiting);
  expect(visual("2").userData.velocity.length()).toBe(0);
  rerender(
    <GraphCanvas {...callbacks} designPreview introStarted view={next} />,
  );
  expect(visual("2").position).toEqual(waiting);
  act(() => vi.advanceTimersByTime(400));
  expect(visual("2").position).toEqual(settled);
  expect(callbacks.onTransitionComplete).toHaveBeenCalledTimes(1);
  vi.stubGlobal("matchMedia", () => ({ matches: true }));
  rerender(
    <GraphCanvas
      {...callbacks}
      designPreview
      introStarted
      view={next}
      pendingNodeId="1"
    />,
  );
  act(() => vi.advanceTimersByTime(1000));
  expect(visual("2").position).toEqual(settled);
  rerender(
    <GraphCanvas {...callbacks} designPreview introStarted view={next} />,
  );
  expect(visual("2").position).toEqual(settled);
});

it("로딩이 이미 끝난 상태에서 지도가 다시 생성되어도 초기 연출과 조작 복구를 완료한다", () => {
  const callbacks = props();
  const { container } = render(
    <GraphCanvas {...callbacks} designPreview introStarted />,
  );
  const { camera, target } = harness;
  if (!camera || !target) throw new Error("camera가 없습니다.");
  const initialDistance = camera.position.distanceTo(target);
  expect(harness.navigationEnabled).toBe(false);
  act(() => vi.advanceTimersByTime(1500));
  const overviewDistance = camera.position.distanceTo(target);
  expect(overviewDistance).toBeLessThan(initialDistance / 50);
  act(() => vi.advanceTimersByTime(160));
  expect(camera.position.distanceTo(target)).toBe(overviewDistance);
  expect(callbacks.onIntroComplete).not.toHaveBeenCalled();
  act(() => vi.advanceTimersByTime(600));
  expect(camera.position.distanceTo(target)).toBeLessThan(overviewDistance);
  act(() => vi.advanceTimersByTime(1740));
  expect(callbacks.onReady).toHaveBeenCalledTimes(1);
  expect(callbacks.onIntroComplete).toHaveBeenCalledTimes(1);
  expect(harness.navigationEnabled).toBe(true);
  expect(container.querySelector("section")?.getAttribute("aria-busy")).toBe(
    "false",
  );
  expect(initialDistance).toBeGreaterThan(
    90 * camera.position.distanceTo(target),
  );
});

it("초기 연출을 이미 마친 지도는 재생성 시 확대를 반복하지 않고 조작을 복구한다", () => {
  const callbacks = props();
  render(
    <GraphCanvas {...callbacks} designPreview introStarted introCompleted />,
  );
  const camera = harness.camera;
  if (!camera) throw new Error("camera가 없습니다.");
  const initialPosition = camera.position.clone();
  act(() => vi.advanceTimersByTime(16));
  expect(harness.navigationEnabled).toBe(true);
  expect(camera.position.distanceTo(initialPosition)).toBeLessThan(0.001);
  expect(callbacks.onReady).toHaveBeenCalledTimes(1);
  expect(callbacks.onIntroComplete).not.toHaveBeenCalled();
});

it("중심 재배치는 사용자의 배율과 전환 도중 바꾼 배율을 유지한다", () => {
  const callbacks = props();
  const { rerender } = render(
    <GraphCanvas {...callbacks} designPreview introStarted introCompleted />,
  );
  act(() => vi.advanceTimersByTime(16));
  const { camera, target } = harness;
  if (!camera || !target) throw new Error("camera가 없습니다.");
  camera.position.copy(target).add(new THREE.Vector3(0, 0, 450));
  const next = {
    ...view,
    centerId: "2",
    nodes: [node("2", "center"), node("1", "direct")],
  };
  rerender(
    <GraphCanvas
      {...callbacks}
      view={next}
      designPreview
      introStarted
      introCompleted
    />,
  );
  act(() => vi.advanceTimersByTime(400));
  expect(camera.position.distanceTo(target)).toBeCloseTo(450);
  camera.position.copy(target).add(new THREE.Vector3(0, 0, 290));
  act(() => vi.advanceTimersByTime(1400));
  expect(camera.position.distanceTo(target)).toBeCloseTo(290);
  expect(callbacks.onTransitionComplete).toHaveBeenCalledWith("2");
  expect(harness.navigationEnabled).toBe(true);
});

it("근접 조망에서 숨긴 2단계는 축소하면 같은 좌표로 나타나고 숨은 node는 클릭을 가로채지 않는다", () => {
  const callbacks = props();
  const page = {
    ...view,
    nodes: [
      ...view.nodes,
      { ...node("3", "ambient"), tier: "twoHop" as const },
    ],
  };
  render(
    <GraphCanvas
      {...callbacks}
      view={page}
      designPreview
      introStarted
      introCompleted
    />,
  );
  act(() => vi.advanceTimersByTime(16));
  const { camera, target, labels, scene } = harness;
  if (!camera || !target || !labels || !scene)
    throw new Error("graph가 없습니다.");
  const second = harness.nodes.get("3");
  if (!second) throw new Error("2단계가 없습니다.");
  const position = second.position.clone();
  labels.render(scene, camera);
  expect(second.visible).toBe(false);
  expect(
    new THREE.Raycaster(
      new THREE.Vector3(position.x, position.y, 1000),
      new THREE.Vector3(0, 0, -1),
    ).intersectObject(second, true),
  ).toHaveLength(0);
  const distance = camera.position.distanceTo(target);
  target.x += distance * 0.1;
  camera.position.x += distance * 0.1;
  labels.render(scene, camera);
  expect(second.visible).toBe(true);
  const partial = second.userData.surface.material.opacity;
  expect(partial).toBeGreaterThan(0);
  expect(partial).toBeLessThan(second.userData.style.opacity);
  expect(second.userData.occluder.material.opacity).toBeLessThan(1);
  target.x -= distance * 0.1;
  camera.position.x -= distance * 0.1;
  labels.render(scene, camera);
  expect(second.visible).toBe(false);
  camera.position.sub(target).multiplyScalar(2).add(target);
  labels.render(scene, camera);
  expect(second.visible).toBe(true);
  expect(second.userData.surface.material.opacity).toBe(
    second.userData.style.opacity,
  );
  expect(second.position).toEqual(position);
});

it("근접 조망은 1단계 간선만, 축소 뒤에는 2단계 간선까지만 표시한다", () => {
  const callbacks = props();
  const relations = (["direct", "twoHop", "threeHop", "ambient"] as const).map(
    (tier) => ({
      id: tier,
      source: "1",
      target: "2",
      label: tier,
      tier,
      directionality: "DIRECTED" as const,
      evidenceGroupCount: 1,
      conflict: false,
    }),
  );
  render(
    <GraphCanvas
      {...callbacks}
      view={{ ...view, relations }}
      designPreview
      introStarted
      introCompleted
    />,
  );
  act(() => vi.advanceTimersByTime(16));
  const { camera, target, labels, scene } = harness;
  if (!camera || !target || !labels || !scene)
    throw new Error("graph가 없습니다.");
  labels.render(scene, camera);
  const nearVisibility = harness.options.get("linkVisibility");
  if (!nearVisibility) throw new Error("간선 표시 규칙이 없습니다.");
  expect(relations.map((link) => nearVisibility(link as never))).toEqual([
    true,
    false,
    false,
    false,
  ]);
  camera.position.sub(target).multiplyScalar(2).add(target);
  labels.render(scene, camera);
  const farVisibility = harness.options.get("linkVisibility");
  if (!farVisibility) throw new Error("간선 표시 규칙이 없습니다.");
  expect(relations.map((link) => farVisibility(link as never))).toEqual([
    true,
    true,
    false,
    false,
  ]);
});

it("hover 대상은 맥동하고 테마 변경은 graph와 배율을 보존한다", () => {
  const callbacks = props();
  const { rerender } = render(
    <GraphCanvas {...callbacks} designPreview introStarted introCompleted />,
  );
  act(() => vi.advanceTimersByTime(16));
  const visual = harness.nodes.get("2");
  const camera = harness.camera;
  if (!visual || !camera) throw new Error("graph가 없습니다.");
  act(() => harness.options.get("onNodeHover")?.({ id: "2" } as never));
  act(() => vi.advanceTimersByTime(16));
  const opacity = visual.userData.shell.material.opacity;
  expect(opacity).toBeGreaterThan(0);
  expect(opacity).toBeLessThan(0.5);
  expect(visual.userData.shell.visible).toBe(true);
  act(() => vi.advanceTimersByTime(300));
  expect(visual.userData.shell.material.opacity).not.toBe(opacity);
  const position = camera.position.clone();
  rerender(
    <GraphCanvas
      {...callbacks}
      designPreview
      introStarted
      introCompleted
      theme="light"
    />,
  );
  expect(harness.camera).toBe(camera);
  expect(camera.position).toEqual(position);
  expect(visual.userData.occluder.material.color.getHexString()).toBe("f5f7fa");
  act(() => harness.options.get("onNodeHover")?.(null as never));
  act(() => vi.advanceTimersByTime(200));
  expect(visual.userData.shell.visible).toBe(false);
});

it("배치 완료 뒤 다시 생성된 간선도 첫 hover 전에 좌표를 갖는다", () => {
  const relation: KnowledgeRelation = {
    id: "late-link",
    source: "1",
    target: "2",
    label: "관계",
    tier: "direct",
    directionality: "DIRECTED",
    evidenceGroupCount: 1,
    conflict: false,
  };
  render(
    <GraphCanvas
      {...props()}
      view={{ ...view, relations: [relation] }}
      designPreview
      introStarted
      introCompleted
    />,
  );
  act(() => vi.advanceTimersByTime(16));
  const recreate = harness.options.get("linkThreeObject");
  if (!recreate) throw new Error("간선 생성기가 없습니다.");
  const group = recreate(relation as never) as THREE.Group;
  const line = group.children[0] as THREE.Line;
  const raycaster = new THREE.Raycaster(
    new THREE.Vector3(0, 0, 100),
    new THREE.Vector3(0, 0, -1),
  );
  expect(() => raycaster.intersectObject(group, true)).not.toThrow();
  const position = line.geometry.getAttribute("position");
  const source = harness.nodes.get("1")?.position;
  const target = harness.nodes.get("2")?.position;
  if (!source || !target) throw new Error("간선의 양 끝이 없습니다.");
  expect(position.count).toBeGreaterThan(1);
  expect(position.getX(0)).toBeCloseTo(source.x);
  expect(position.getY(position.count - 1)).toBeCloseTo(target.y);
});
