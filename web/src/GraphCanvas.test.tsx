import { act, cleanup, render } from "@testing-library/react";
import * as THREE from "three";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { ExplorationView, KnowledgeRelation } from "./data";
import { GraphCanvas } from "./GraphCanvas";

const harness = vi.hoisted(() => ({
  options: new Map<string, (...args: never[]) => unknown>(),
  nodes: new Map<string, THREE.Group>(),
  links: new Map<string, THREE.Group>(),
}));

// WebGL 경계만 대체하고 실제 GraphCanvas의 effect·frame·DOM 수명주기를 실행한다.
vi.mock("3d-force-graph", () => ({
  default: function FakeGraph(container: HTMLElement) {
    const camera = new THREE.PerspectiveCamera();
    const scene = new THREE.Scene();
    const controls = {
      object: camera,
      target: new THREE.Vector3(),
      mouseButtons: {},
      touches: {},
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      update: vi.fn(),
    };
    let nodeFactory: (node: { id: string }) => THREE.Group;
    let linkFactory: (link: KnowledgeRelation) => THREE.Group;
    const dimensions = { width: 800, height: 600 };
    const graph: Record<string, unknown> = {};
    const proxy = new Proxy(graph, {
      get: (_, key: string) => {
        if (key === "controls") return () => controls;
        if (key === "camera") return () => camera;
        if (key === "scene") return () => scene;
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
