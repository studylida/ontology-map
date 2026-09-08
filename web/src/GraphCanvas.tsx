import ForceGraph3D, { type ForceGraph3DInstance } from "3d-force-graph";
import { useCallback, useEffect, useRef, useState } from "react";
import * as THREE from "three";
import type { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import {
  type ExplorationView,
  getFilamentOffsets,
  type KnowledgeViewNode,
  type KnowledgeViewRelation,
  type NodeTier,
} from "./data";
import styles from "./GraphCanvas.module.css";
import {
  layoutTargets,
  type Position,
  pinPosition,
  retainGraphItems,
} from "./graphLayout";
import { watchBoundaryPan } from "./peripheralPan";
import type { EvidenceSelection } from "./RelationPanel";

interface RuntimeNode extends KnowledgeViewNode {
  x?: number;
  y?: number;
  z?: number;
  vx?: number;
  vy?: number;
  vz?: number;
  fx?: number;
  fy?: number;
  fz?: number;
}

interface RuntimeLink extends Omit<KnowledgeViewRelation, "source" | "target"> {
  source: string | RuntimeNode;
  target: string | RuntimeNode;
}

interface GraphCanvasProps {
  view: ExplorationView;
  introStarted: boolean;
  onSelect: (nodeId: string) => void;
  onTransitionComplete: (nodeId: string) => void;
  onReady: () => void;
  onPanBoundary: () => void;
  onEvidence: (selection: EvidenceSelection) => void;
}

type GraphControls = OrbitControls;

interface NodeStyle {
  opacity: number;
  emission: number;
  haloOpacity: number;
  haloFactor: number;
  shellOpacity: number;
  labelOpacity: number;
  colorScale: number;
}

type NodeVisual = THREE.Group & {
  userData: {
    nodeId: string;
    surface: THREE.Mesh<THREE.SphereGeometry, THREE.MeshStandardMaterial>;
    occluder: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>;
    core: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>;
    halo: THREE.Sprite;
    shell: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>;
    label: THREE.Sprite;
    radius: number;
    style: NodeStyle;
  };
};

type LinkVisual = THREE.Group & {
  userData: {
    linkId: string;
    lines: THREE.Line[];
    opacity: number;
    endpoints?: number[];
  };
};

const colors = {
  사람: "#6ea8fe",
  회사: "#b792f4",
  기술: "#43c6d9",
  주제: "#65c98b",
  사건: "#f17c9e",
};

const nodeStyles: Record<NodeTier, NodeStyle> = {
  center: {
    opacity: 1,
    emission: 1.7,
    haloOpacity: 0.42,
    haloFactor: 6,
    shellOpacity: 0.1,
    labelOpacity: 0.98,
    colorScale: 0.9,
  },
  direct: {
    opacity: 0.9,
    emission: 1.05,
    haloOpacity: 0.19,
    haloFactor: 4.6,
    shellOpacity: 0,
    labelOpacity: 0.66,
    colorScale: 0.86,
  },
  twoHop: {
    opacity: 0.9,
    emission: 1.05,
    haloOpacity: 0.19,
    haloFactor: 4.6,
    shellOpacity: 0,
    labelOpacity: 0.66,
    colorScale: 0.86,
  },
  ambient: {
    opacity: 0.48,
    emission: 0.46,
    haloOpacity: 0.055,
    haloFactor: 3.8,
    shellOpacity: 0,
    labelOpacity: 0,
    colorScale: 0.58,
  },
};

const relationOpacity = { direct: 0.9, twoHop: 0.56, ambient: 0.3 } as const;

function radiusFor(node: RuntimeNode): number {
  const activity = node.activityEvidenceGroupCount;
  const radius = activity >= 6 ? 3.5 : activity >= 3 ? 2.35 : 1.6;
  return radius * 1.25;
}

function makeGlowTexture(): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const context = canvas.getContext("2d");
  if (context) {
    const gradient = context.createRadialGradient(64, 64, 0, 64, 64, 64);
    gradient.addColorStop(0, "rgba(255,255,255,0.95)");
    gradient.addColorStop(0.12, "rgba(255,255,255,0.55)");
    gradient.addColorStop(0.42, "rgba(255,255,255,0.14)");
    gradient.addColorStop(1, "rgba(255,255,255,0)");
    context.fillStyle = gradient;
    context.fillRect(0, 0, 128, 128);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function makeLabel(node: RuntimeNode): THREE.Sprite {
  const canvas = document.createElement("canvas");
  canvas.width = 512;
  canvas.height = 104;
  const context = canvas.getContext("2d");
  if (context) {
    context.fillStyle = "rgba(9, 13, 20, 0.82)";
    context.beginPath();
    context.roundRect(8, 8, 496, 88, 18);
    context.fill();
    context.strokeStyle = "rgba(154, 177, 208, 0.42)";
    context.lineWidth = 2;
    context.stroke();
    context.fillStyle = "#f3f6fa";
    context.font = "600 30px system-ui, sans-serif";
    context.textAlign = "center";
    context.textBaseline = "middle";
    context.fillText(node.name, 256, 52, 448);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: texture,
      transparent: true,
      opacity: 0,
      depthTest: false,
      depthWrite: false,
      toneMapped: false,
    }),
  );
  sprite.scale.set(48, 9.75, 1);
  sprite.renderOrder = 14;
  return sprite;
}

function applyNodeVisual(
  visual: NodeVisual,
  node: RuntimeNode,
  radius: number,
  style: NodeStyle,
) {
  const color = new THREE.Color(
    colors[node.kind as keyof typeof colors] ?? "#8fa1b8",
  );
  visual.userData.surface.material.color
    .copy(color)
    .multiplyScalar(style.colorScale);
  visual.userData.surface.material.emissive.copy(color);
  visual.userData.surface.material.emissiveIntensity = style.emission;
  visual.userData.surface.material.opacity = style.opacity;
  visual.userData.surface.scale.setScalar(radius);
  visual.userData.occluder.scale.setScalar(radius * 1.04);
  visual.userData.occluder.material.opacity = style.opacity;
  visual.userData.core.material.color.copy(color);
  visual.userData.core.material.opacity = style.opacity;
  visual.userData.core.scale.setScalar(radius * 0.22);
  const haloMaterial = visual.userData.halo.material as THREE.SpriteMaterial;
  haloMaterial.color.copy(color);
  haloMaterial.opacity = style.haloOpacity;
  visual.userData.halo.scale.setScalar(radius * style.haloFactor);
  visual.userData.shell.material.opacity = style.shellOpacity;
  visual.userData.shell.scale.setScalar(radius * 1.42);
  (visual.userData.label.material as THREE.SpriteMaterial).opacity =
    style.labelOpacity;
  visual.userData.label.position.y = radius + 9;
  visual.userData.radius = radius;
  visual.userData.style = { ...style };
}

function makeNodeVisual(node: RuntimeNode): NodeVisual {
  const group = new THREE.Group() as NodeVisual;
  const geometry = new THREE.SphereGeometry(1, 28, 18);
  const color = new THREE.Color(
    colors[node.kind as keyof typeof colors] ?? "#8fa1b8",
  );
  const occluder = new THREE.Mesh(
    geometry,
    new THREE.MeshBasicMaterial({
      color: "#070a10",
      transparent: true,
      opacity: 1,
      depthTest: false,
      depthWrite: false,
      toneMapped: false,
    }),
  );
  occluder.renderOrder = 10;
  const surface = new THREE.Mesh(
    geometry,
    new THREE.MeshStandardMaterial({
      color,
      emissive: color,
      roughness: 0.24,
      metalness: 0.04,
      transparent: true,
      depthTest: false,
      depthWrite: false,
    }),
  );
  surface.renderOrder = 11;
  const core = new THREE.Mesh(
    geometry,
    new THREE.MeshBasicMaterial({
      color,
      transparent: true,
      depthTest: false,
      depthWrite: false,
      toneMapped: false,
    }),
  );
  core.renderOrder = 12;
  const halo = new THREE.Sprite(
    new THREE.SpriteMaterial({
      map: makeGlowTexture(),
      color,
      transparent: true,
      blending: THREE.AdditiveBlending,
      depthTest: false,
      depthWrite: false,
      toneMapped: false,
    }),
  );
  halo.renderOrder = 9;
  const shell = new THREE.Mesh(
    geometry,
    new THREE.MeshBasicMaterial({
      color: "#d9e7ff",
      transparent: true,
      side: THREE.BackSide,
      blending: THREE.AdditiveBlending,
      depthTest: false,
      depthWrite: false,
      toneMapped: false,
    }),
  );
  shell.renderOrder = 13;
  const label = makeLabel(node);
  group.add(halo, occluder, surface, core, shell, label);
  group.userData = {
    nodeId: node.id,
    surface,
    occluder,
    core,
    halo,
    shell,
    label,
    radius: radiusFor(node),
    style: { ...nodeStyles[node.tier] },
  };
  applyNodeVisual(group, node, group.userData.radius, group.userData.style);
  return group;
}

function makeLinkVisual(link: RuntimeLink): LinkVisual {
  const group = new THREE.Group() as LinkVisual;
  const opacity = relationOpacity[link.tier];
  const lines = Array.from(
    { length: Math.max(1, Math.round(link.evidenceGroupCount)) },
    () => {
      const material = link.conflict
        ? new THREE.LineDashedMaterial({
            color: "#e6a23c",
            transparent: true,
            opacity,
            dashSize: 3,
            gapSize: 2,
            depthTest: true,
            depthWrite: false,
          })
        : new THREE.LineBasicMaterial({
            color: getComputedStyle(document.documentElement)
              .getPropertyValue("--relation")
              .trim(),
            transparent: true,
            opacity,
            depthTest: true,
            depthWrite: false,
          });
      const line = new THREE.Line(new THREE.BufferGeometry(), material);
      line.renderOrder = 1;
      line.frustumCulled = false;
      group.add(line);
      return line;
    },
  );
  group.userData = { linkId: link.id, lines, opacity };
  return group;
}

function updateLinkPosition(
  object: THREE.Object3D,
  start: { x: number; y: number; z: number },
  end: { x: number; y: number; z: number },
): boolean {
  const group = object as LinkVisual;
  const endpoints = [start.x, start.y, start.z, end.x, end.y, end.z];
  if (group.userData.endpoints?.every((value, i) => value === endpoints[i]))
    return true;
  group.userData.endpoints = endpoints;
  const startPoint = new THREE.Vector3(start.x, start.y, start.z);
  const endPoint = new THREE.Vector3(end.x, end.y, end.z);
  const direction = endPoint.clone().sub(startPoint);
  const perpendicular = new THREE.Vector3(-direction.y, direction.x, 0);
  if (perpendicular.lengthSq() < 0.001) perpendicular.set(1, 0, 0);
  perpendicular.normalize();
  const offsets = getFilamentOffsets(group.userData.lines.length);
  group.userData.lines.forEach((line, index) => {
    const offset = perpendicular.clone().multiplyScalar(offsets[index] ?? 0);
    const midpoint = startPoint
      .clone()
      .add(endPoint)
      .multiplyScalar(0.5)
      .add(perpendicular.clone().multiplyScalar(4))
      .add(offset);
    const curve = new THREE.QuadraticBezierCurve3(
      startPoint,
      midpoint,
      endPoint,
    );
    line.geometry.setFromPoints(curve.getPoints(14));
    if (line.material instanceof THREE.LineDashedMaterial)
      line.computeLineDistances();
  });
  return true;
}

function easeInOutCubic(value: number): number {
  return value < 0.5
    ? 4 * value * value * value
    : 1 - (-2 * value + 2) ** 3 / 2;
}

function endpointId(endpoint: string | RuntimeNode): string {
  return typeof endpoint === "string" ? endpoint : endpoint.id;
}

export function GraphCanvas({
  view,
  introStarted,
  onSelect,
  onTransitionComplete,
  onReady,
  onEvidence,
  onPanBoundary,
}: GraphCanvasProps) {
  const centerId = view.centerId;
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<ForceGraph3DInstance<
    RuntimeNode,
    RuntimeLink
  > | null>(null);
  const nodesRef = useRef(new Map<string, RuntimeNode>());
  const linksRef = useRef(new Map<string, RuntimeLink>());
  const nodeVisualsRef = useRef(new Map<string, NodeVisual>());
  const linkVisualsRef = useRef(new Map<string, LinkVisual>());
  const previousCenterRef = useRef(centerId);
  const viewNodesRef = useRef(new Set(view.nodes.map((node) => node.id)));
  useEffect(() => {
    viewNodesRef.current = new Set(view.nodes.map((node) => node.id));
  }, [view]);
  const onSelectRef = useRef(onSelect);
  const onTransitionCompleteRef = useRef(onTransitionComplete);
  const onReadyRef = useRef(onReady);
  const focusPathRef = useRef<(nodeId: string | null) => void>(() => {});
  const dataInitializedRef = useRef(false);
  const readyRef = useRef(false);
  const introCompletedRef = useRef(false);
  const animationRef = useRef<number | null>(null);
  const hoverAnimationRef = useRef<number | null>(null);
  const introTimeoutRef = useRef<number | null>(null);
  const [busy, setBusy] = useState(true);
  const [hoveredRelation, setHoveredRelation] = useState<string | null>(null);
  const focusRelationRef = useRef<(id: string | null) => void>(() => {});
  const onEvidenceRef = useRef(onEvidence);
  const onPanRef = useRef(onPanBoundary);
  useEffect(() => {
    onPanRef.current = onPanBoundary;
  }, [onPanBoundary]);
  const relationButtonsRef = useRef(new Map<string, HTMLButtonElement>());
  useEffect(() => {
    onEvidenceRef.current = onEvidence;
  }, [onEvidence]);
  const relationName = useCallback(
    (relation: KnowledgeViewRelation) => {
      const source =
        view.nodes.find((node) => node.id === relation.source)?.name ?? "노드";
      const target =
        view.nodes.find((node) => node.id === relation.target)?.name ?? "노드";
      const direction = relation.directionality === "DIRECTED" ? "→" : "↔";
      return `${source} ${direction} ${target} · ${relation.label} · 독립 근거 ${relation.evidenceGroupCount}개`;
    },
    [view.nodes],
  );
  const relationActionsRef = useRef(new Map<string, EvidenceSelection>());
  useEffect(() => {
    relationActionsRef.current = new Map(
      view.relations.map((relation) => [
        relation.id,
        { id: relation.id, label: relationName(relation) },
      ]),
    );
    setHoveredRelation(null);
  }, [view, relationName]);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    onTransitionCompleteRef.current = onTransitionComplete;
  }, [onTransitionComplete]);

  useEffect(() => {
    onReadyRef.current = onReady;
  }, [onReady]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const graph = new ForceGraph3D(container, {
      controlType: "orbit",
      rendererConfig: {
        antialias: true,
        alpha: false,
        preserveDrawingBuffer: true,
        powerPreference: "high-performance",
      },
    }) as unknown as ForceGraph3DInstance<RuntimeNode, RuntimeLink>;
    graphRef.current = graph;
    graph
      .backgroundColor("#070a10")
      .showNavInfo(false)
      .enableNodeDrag(false)
      .enableNavigationControls(true)
      .nodeId("id")
      .nodeLabel((node) => `${node.name} · ${node.kind}`)
      .nodeThreeObject((node) => {
        const visual = makeNodeVisual(node);
        nodeVisualsRef.current.set(node.id, visual);
        return visual;
      })
      .linkThreeObject((link) => {
        const visual = makeLinkVisual(link);
        linkVisualsRef.current.set(link.id, visual);
        return visual;
      })
      .linkDirectionalArrowLength((link) =>
        link.directionality === "DIRECTED" ? 4 : 0,
      )
      .linkDirectionalArrowRelPos(0.85)
      .linkHoverPrecision(6)
      .onLinkHover((link) => focusRelationRef.current(link?.id ?? null))
      .onLinkClick((link) => {
        const selection = relationActionsRef.current.get(link.id);
        if (selection) {
          relationButtonsRef.current.get(link.id)?.focus();
          onEvidenceRef.current(selection);
        }
      })
      .linkPositionUpdate((object, coordinates) =>
        updateLinkPosition(object, coordinates.start, coordinates.end),
      )
      .onNodeClick((node) => {
        if (viewNodesRef.current.has(node.id)) onSelectRef.current(node.id);
      })
      .onNodeHover((node) => {
        focusPathRef.current(node?.id ?? null);
        container.style.cursor = node ? "pointer" : "grab";
      })
      .warmupTicks(0)
      .cooldownTicks(0);

    const highlight = (nodeIds: Set<string>, relationId: string | null) => {
      if (hoverAnimationRef.current !== null)
        cancelAnimationFrame(hoverAnimationRef.current);
      const nodeTargets = [...nodesRef.current.values()].map((item) => {
        const visual = nodeVisualsRef.current.get(item.id);
        return {
          item,
          visual,
          from: visual
            ? (visual.userData.halo.material as THREE.SpriteMaterial).opacity
            : 0,
          to:
            nodeIds.has(item.id) && item.tier !== "center"
              ? Math.min(
                  nodeStyles.center.haloOpacity - 0.01,
                  nodeStyles[item.tier].haloOpacity + 0.14,
                )
              : nodeStyles[item.tier].haloOpacity,
        };
      });
      const linkTargets = [...linksRef.current.values()].map((link) => {
        const visual = linkVisualsRef.current.get(link.id);
        const focused =
          relationId !== null
            ? link.id === relationId
            : nodeIds.has(endpointId(link.source)) ||
              nodeIds.has(endpointId(link.target));
        return {
          visual,
          from: visual?.userData.opacity ?? 0,
          to: focused
            ? link.tier === "ambient"
              ? 0.66
              : 0.9
            : relationOpacity[link.tier],
        };
      });
      const startedAt = performance.now();
      const animate = (now: number) => {
        const progress = Math.min(1, (now - startedAt) / 160);
        const eased = 1 - (1 - progress) ** 3;
        for (const target of nodeTargets) {
          if (!target.visual) continue;
          (
            target.visual.userData.halo.material as THREE.SpriteMaterial
          ).opacity = target.from + (target.to - target.from) * eased;
        }
        for (const target of linkTargets) {
          if (!target.visual) continue;
          const opacity = target.from + (target.to - target.from) * eased;
          for (const line of target.visual.userData.lines)
            (line.material as THREE.Material).opacity = opacity;
          target.visual.userData.opacity = opacity;
        }
        if (progress < 1)
          hoverAnimationRef.current = requestAnimationFrame(animate);
        else hoverAnimationRef.current = null;
      };
      hoverAnimationRef.current = requestAnimationFrame(animate);
    };

    focusPathRef.current = (id) => highlight(new Set(id ? [id] : []), null);
    focusRelationRef.current = (id) => {
      const relation = id ? linksRef.current.get(id) : undefined;
      setHoveredRelation(id);
      const nodeIds = relation
        ? [endpointId(relation.source), endpointId(relation.target)]
        : [];
      highlight(new Set(nodeIds), id);
    };

    graph.d3Force("charge", null);
    graph.d3Force("link", null);
    graph.d3Force("center", null);

    const controls = graph.controls() as GraphControls;
    controls.enableRotate = false;
    controls.enablePan = true;
    controls.mouseButtons.LEFT = THREE.MOUSE.PAN;
    controls.enableZoom = true;
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 95;
    controls.maxDistance = 2400;
    const stopWatchingPan = watchBoundaryPan(
      controls,
      () =>
        [...nodesRef.current.values()].map((node) => ({
          x: node.x ?? 0,
          y: node.y ?? 0,
          z: node.z ?? 0,
        })),
      () =>
        readyRef.current &&
        introTimeoutRef.current === null &&
        animationRef.current === null,
      () => onPanRef.current(),
    );

    const renderer = graph.renderer();
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    graph.scene().fog = new THREE.FogExp2(0x070a10, 0.0017);
    const hemisphere = new THREE.HemisphereLight("#b9d3ff", "#070a10", 0.72);
    const key = new THREE.DirectionalLight("#e8f1ff", 1.4);
    key.position.set(90, 120, 170);
    const rim = new THREE.DirectionalLight("#5a7bff", 0.8);
    rim.position.set(-120, 10, -90);
    graph.lights([hemisphere, key, rim]);
    const bloom = new UnrealBloomPass(
      new THREE.Vector2(container.clientWidth, container.clientHeight),
      0.44,
      0.2,
      0.7,
    );
    graph.postProcessingComposer().addPass(bloom);

    const dustPositions: number[] = [];
    for (let index = 0; index < 260; index += 1) {
      const angle = index * 2.399963229728653;
      const radius = 250 + (index % 43) * 6.5;
      const height = ((index * 37) % 180) - 90;
      dustPositions.push(
        Math.cos(angle) * radius,
        height,
        Math.sin(angle) * radius - 120,
      );
    }
    const dustGeometry = new THREE.BufferGeometry();
    dustGeometry.setAttribute(
      "position",
      new THREE.Float32BufferAttribute(dustPositions, 3),
    );
    graph.scene().add(
      new THREE.Points(
        dustGeometry,
        new THREE.PointsMaterial({
          color: "#7892b7",
          size: 0.62,
          transparent: true,
          opacity: 0.18,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
          toneMapped: false,
        }),
      ),
    );

    const resize = () => {
      graph.width(container.clientWidth).height(container.clientHeight);
      bloom.resolution.set(container.clientWidth, container.clientHeight);
    };
    resize();
    const observer = new ResizeObserver(resize);
    observer.observe(container);
    graph.cameraPosition({ x: 0, y: 0, z: 360 }, { x: 0, y: 0, z: 0 }, 0);

    return () => {
      stopWatchingPan();
      observer.disconnect();
      if (animationRef.current !== null)
        cancelAnimationFrame(animationRef.current);
      if (hoverAnimationRef.current !== null)
        cancelAnimationFrame(hoverAnimationRef.current);
      if (introTimeoutRef.current !== null)
        window.clearTimeout(introTimeoutRef.current);
      graph._destructor();
      graphRef.current = null;
      dataInitializedRef.current = false;
      readyRef.current = false;
      introCompletedRef.current = false;
      nodesRef.current.clear();
      linksRef.current.clear();
      nodeVisualsRef.current.clear();
      linkVisualsRef.current.clear();
      focusPathRef.current = () => {};
      focusRelationRef.current = () => {};
    };
  }, []);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const controls = graph.controls() as GraphControls;
    const initial = !dataInitializedRef.current;
    const changed = previousCenterRef.current !== centerId;
    const center = nodesRef.current.get(centerId);
    const anchor = { x: center?.x ?? 0, y: center?.y ?? 0, z: center?.z ?? 0 };
    const currentPositions = new Map(
      [...nodesRef.current].map(([id, n]) => [
        id,
        { x: n.x ?? 0, y: n.y ?? 0, z: n.z ?? 0 },
      ]),
    );
    const targets = layoutTargets(
      view.nodes,
      centerId,
      anchor,
      view.relations,
      changed || initial ? new Map() : currentPositions,
    );
    const starts = new Map(currentPositions);
    for (const target of view.nodes) {
      const position = targets.get(target.id);
      if (!position) continue;
      const existing = nodesRef.current.get(target.id);
      const node = existing ?? { ...target, ...position };
      Object.assign(node, target);
      pinPosition(
        node as RuntimeNode & Position,
        starts.get(target.id) ?? position,
      );
      nodesRef.current.set(target.id, node);
      starts.set(target.id, { x: node.x ?? 0, y: node.y ?? 0, z: node.z ?? 0 });
    }
    for (const target of view.relations) {
      const existing = linksRef.current.get(target.id);
      if (existing) Object.assign(existing, target);
      else linksRef.current.set(target.id, { ...target });
    }
    const publishData = () =>
      graph.graphData({
        nodes: [...nodesRef.current.values()],
        links: [...linksRef.current.values()],
      });
    publishData();
    const fitDistance = (wide: boolean) => {
      const camera = graph.camera() as THREE.PerspectiveCamera;
      const visible = view.nodes.filter((n) => n.tier !== "ambient");
      let x = 40,
        y = 40;
      for (const node of visible) {
        const position = targets.get(node.id);
        if (!position) continue;
        x = Math.max(x, Math.abs(position.x - anchor.x) + 24);
        y = Math.max(y, Math.abs(position.y - anchor.y) + 24);
      }
      const tangent = Math.tan((camera.fov * Math.PI) / 360);
      return (
        Math.max(
          150,
          x / ((tangent * graph.width()) / graph.height()),
          y / tangent,
        ) * (wide ? 1.55 : 1)
      );
    };
    const removeOutgoing = () => {
      const nodeIds = new Set(view.nodes.map((n) => n.id));
      const linkIds = new Set(view.relations.map((r) => r.id));
      retainGraphItems(nodesRef.current, nodeIds);
      retainGraphItems(linksRef.current, linkIds);
      retainGraphItems(nodeVisualsRef.current, nodeIds);
      retainGraphItems(linkVisualsRef.current, linkIds);
      publishData();
    };
    const paint = (progress: number, move: boolean) => {
      for (const [id, node] of nodesRef.current) {
        const target = targets.get(id);
        const start = starts.get(id);
        if (target && start && move)
          pinPosition(node as RuntimeNode & Position, {
            x: start.x + (target.x - start.x) * progress,
            y: start.y + (target.y - start.y) * progress,
            z: start.z + (target.z - start.z) * progress,
          });
        const visual = nodeVisualsRef.current.get(id);
        if (!visual) continue;
        const style = { ...nodeStyles[node.tier] };
        if (!viewNodesRef.current.has(id)) {
          style.opacity *= 1 - progress;
          style.haloOpacity *= 1 - progress;
          style.labelOpacity *= 1 - progress;
          style.shellOpacity *= 1 - progress;
        }
        visual.position.set(node.x ?? 0, node.y ?? 0, node.z ?? 0);
        applyNodeVisual(visual, node, radiusFor(node), style);
      }
      const ids = new Set(view.relations.map((r) => r.id));
      for (const [id, link] of linksRef.current) {
        const visual = linkVisualsRef.current.get(id);
        if (!visual) continue;
        const source = nodesRef.current.get(endpointId(link.source));
        const target = nodesRef.current.get(endpointId(link.target));
        if (source && target)
          updateLinkPosition(
            visual,
            { x: source.x ?? 0, y: source.y ?? 0, z: source.z ?? 0 },
            { x: target.x ?? 0, y: target.y ?? 0, z: target.z ?? 0 },
          );
        const opacity =
          relationOpacity[link.tier] * (ids.has(id) ? 1 : 1 - progress);
        for (const line of visual.userData.lines)
          (line.material as THREE.Material).opacity = opacity;
        visual.userData.opacity = opacity;
      }
    };
    const animate = (intro: boolean) => {
      const startCamera = graph.camera().position.clone();
      const startTarget = controls.target.clone();
      const endTarget = new THREE.Vector3(anchor.x, anchor.y, anchor.z);
      const endCamera = endTarget
        .clone()
        .add(new THREE.Vector3(0, 0, fitDistance(false)));
      const duration = reducedMotion ? 0 : 1200;
      const begun = performance.now();
      setBusy(true);
      const frame = (now: number) => {
        const progress = duration ? Math.min(1, (now - begun) / duration) : 1;
        const eased = easeInOutCubic(progress);
        paint(eased, !intro);
        graph.camera().position.lerpVectors(startCamera, endCamera, eased);
        controls.target.lerpVectors(startTarget, endTarget, eased);
        controls.update();
        if (progress < 1) {
          animationRef.current = requestAnimationFrame(frame);
          return;
        }
        animationRef.current = null;
        previousCenterRef.current = centerId;
        introCompletedRef.current = true;
        if (!intro) {
          removeOutgoing();
          onTransitionCompleteRef.current(centerId);
        }
        graph.enableNavigationControls(true).enablePointerInteraction(true);
        setBusy(false);
      };
      animationRef.current = requestAnimationFrame(frame);
    };
    if (initial) {
      dataInitializedRef.current = true;
      paint(1, false);
      graph.cameraPosition(
        { x: anchor.x, y: anchor.y, z: anchor.z + fitDistance(true) },
        anchor,
        0,
      );
      graph.enableNavigationControls(false).enablePointerInteraction(false);
      animationRef.current = requestAnimationFrame(() => {
        animationRef.current = null;
        readyRef.current = true;
        onReadyRef.current();
      });
    } else if (introStarted && !introCompletedRef.current) {
      introTimeoutRef.current = window.setTimeout(
        () => {
          introTimeoutRef.current = null;
          animate(true);
        },
        reducedMotion ? 0 : 720,
      );
    } else if (introStarted && changed) {
      animate(false);
    } else {
      paint(1, false);
      removeOutgoing();
    }
    return () => {
      if (animationRef.current !== null)
        cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
      if (introTimeoutRef.current !== null)
        window.clearTimeout(introTimeoutRef.current);
      introTimeoutRef.current = null;
    };
  }, [centerId, introStarted, view]);

  return (
    <section className={styles.map} aria-label="동적 지식맵" aria-busy={busy}>
      <div ref={containerRef} className={styles.canvas} />
      {hoveredRelation && (
        <div className={styles.relationHint} role="status">
          {relationActionsRef.current.get(hoveredRelation)?.label}
        </div>
      )}
      <nav className={styles.accessibleNodes} aria-label="지도 관계 목록">
        {view.relations.map((relation) => (
          <button
            key={relation.id}
            ref={(element) => {
              if (element) relationButtonsRef.current.set(relation.id, element);
              else relationButtonsRef.current.delete(relation.id);
            }}
            type="button"
            onFocus={() => focusRelationRef.current(relation.id)}
            onBlur={() => focusRelationRef.current(null)}
            onClick={() =>
              onEvidence({ id: relation.id, label: relationName(relation) })
            }
          >
            {relationName(relation)}
          </button>
        ))}
      </nav>
      <div className={styles.depthNote}>얕은 2.5D · z ±32 · 회전 없음</div>
      <nav
        className={styles.accessibleNodes}
        aria-label="탐색 가능한 node 목록"
      >
        {view.nodes.map((node) => (
          <button
            key={node.id}
            type="button"
            onClick={() => onSelect(node.id)}
            onFocus={() => focusPathRef.current(node.id)}
            onBlur={() => focusPathRef.current(null)}
          >
            {node.name} · {node.kind}
          </button>
        ))}
      </nav>
    </section>
  );
}
