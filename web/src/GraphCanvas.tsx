import ForceGraph3D, { type ForceGraph3DInstance } from "3d-force-graph";
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { UnrealBloomPass } from "three/examples/jsm/postprocessing/UnrealBloomPass.js";
import {
  buildKnowledgeView,
  getFilamentOffsets,
  type KnowledgeViewNode,
  type KnowledgeViewRelation,
  type NodeTier,
  type TimeRange,
} from "./data";
import styles from "./GraphCanvas.module.css";

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
  centerId: string;
  timeRange: TimeRange;
  onSelect: (nodeId: string) => void;
}

interface GraphControls {
  enableRotate: boolean;
  enablePan: boolean;
  enableZoom: boolean;
  enableDamping: boolean;
  dampingFactor: number;
  minDistance: number;
  maxDistance: number;
  target: THREE.Vector3;
  update: () => void;
}

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
    opacity: 0.66,
    emission: 0.72,
    haloOpacity: 0.1,
    haloFactor: 4.2,
    shellOpacity: 0,
    labelOpacity: 0.3,
    colorScale: 0.68,
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
const depthLimit = 32;

function radiusFor(node: RuntimeNode, range: TimeRange): number {
  const activity = node.activity[range];
  if (activity >= 84) return 3.5;
  if (activity >= 56) return 2.35;
  return 1.6;
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
  sprite.scale.set(32, 6.5, 1);
  sprite.renderOrder = 14;
  return sprite;
}

function applyNodeVisual(
  visual: NodeVisual,
  node: RuntimeNode,
  radius: number,
  style: NodeStyle,
) {
  const color = new THREE.Color(colors[node.kind]);
  visual.userData.surface.material.color
    .copy(color)
    .multiplyScalar(style.colorScale);
  visual.userData.surface.material.emissive.copy(color);
  visual.userData.surface.material.emissiveIntensity = style.emission;
  visual.userData.surface.material.opacity = style.opacity;
  visual.userData.surface.scale.setScalar(radius);
  visual.userData.occluder.scale.setScalar(radius * 1.04);
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
  visual.userData.label.position.y = radius + 7;
  visual.userData.radius = radius;
  visual.userData.style = { ...style };
}

function makeNodeVisual(node: RuntimeNode, range: TimeRange): NodeVisual {
  const group = new THREE.Group() as NodeVisual;
  const geometry = new THREE.SphereGeometry(1, 28, 18);
  const color = new THREE.Color(colors[node.kind]);
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
    radius: radiusFor(node, range),
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
            color: "#8fa1b8",
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

function depthTargetForNode(node: RuntimeNode): number {
  let hash = 0;
  for (const character of node.id)
    hash = (hash * 31 + character.charCodeAt(0)) >>> 0;
  return ((hash % 2001) / 1000 - 1) * depthLimit;
}

export function GraphCanvas({
  centerId,
  timeRange,
  onSelect,
}: GraphCanvasProps) {
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
  const timeRangeRef = useRef(timeRange);
  const onSelectRef = useRef(onSelect);
  const dataInitializedRef = useRef(false);
  const animationRef = useRef<number | null>(null);
  const hoverAnimationRef = useRef<number | null>(null);
  const introTimeoutRef = useRef<number | null>(null);
  const [busy, setBusy] = useState(true);
  const view = useMemo(() => buildKnowledgeView(centerId), [centerId]);

  useEffect(() => {
    onSelectRef.current = onSelect;
  }, [onSelect]);

  useEffect(() => {
    timeRangeRef.current = timeRange;
  }, [timeRange]);

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
        const visual = makeNodeVisual(node, timeRangeRef.current);
        nodeVisualsRef.current.set(node.id, visual);
        return visual;
      })
      .linkThreeObject((link) => {
        const visual = makeLinkVisual(link);
        linkVisualsRef.current.set(link.id, visual);
        return visual;
      })
      .linkPositionUpdate((object, coordinates) =>
        updateLinkPosition(object, coordinates.start, coordinates.end),
      )
      .onNodeClick((node) => onSelectRef.current(node.id))
      .onNodeHover((node, previous) => {
        if (hoverAnimationRef.current !== null)
          cancelAnimationFrame(hoverAnimationRef.current);
        const targets = [previous, node].filter((item): item is RuntimeNode =>
          Boolean(item),
        );
        const starts = targets.map((item) => {
          const visual = nodeVisualsRef.current.get(item.id);
          return {
            item,
            visual,
            from: visual
              ? (visual.userData.halo.material as THREE.SpriteMaterial).opacity
              : 0,
            to:
              node?.id === item.id
                ? Math.min(0.52, nodeStyles[item.tier].haloOpacity + 0.14)
                : nodeStyles[item.tier].haloOpacity,
          };
        });
        const startedAt = performance.now();
        const animate = (now: number) => {
          const progress = Math.min(1, (now - startedAt) / 160);
          const eased = 1 - (1 - progress) ** 3;
          for (const target of starts) {
            if (!target.visual) continue;
            (
              target.visual.userData.halo.material as THREE.SpriteMaterial
            ).opacity = target.from + (target.to - target.from) * eased;
          }
          if (progress < 1)
            hoverAnimationRef.current = requestAnimationFrame(animate);
          else hoverAnimationRef.current = null;
        };
        hoverAnimationRef.current = requestAnimationFrame(animate);
        container.style.cursor = node ? "pointer" : "grab";
      })
      .d3AlphaDecay(0.035)
      .d3VelocityDecay(0.4)
      .cooldownTicks(180);

    graph
      .d3Force("charge")
      ?.strength((node: unknown) =>
        (node as RuntimeNode).tier === "ambient" ? -4 : -64,
      );
    graph
      .d3Force("link")
      ?.distance((link: unknown) =>
        (link as RuntimeLink).tier === "twoHop" ? 46 : 56,
      )
      .strength((link: unknown) =>
        (link as RuntimeLink).tier === "ambient" ? 0.06 : 0.4,
      );

    let forceNodes: RuntimeNode[] = [];
    const shallowDepth = (alpha: number) => {
      for (const node of forceNodes) {
        if (node.fz !== undefined) continue;
        const z = Number.isFinite(node.z) ? Number(node.z) : 0;
        node.vz = (node.vz ?? 0) + (depthTargetForNode(node) - z) * 0.1 * alpha;
        node.z = Math.max(-depthLimit, Math.min(depthLimit, z));
        node.vz *= 0.72;
      }
    };
    shallowDepth.initialize = (nodes: RuntimeNode[]) => {
      forceNodes = nodes;
    };
    graph.d3Force("shallow-depth", shallowDepth);

    const controls = graph.controls() as GraphControls;
    controls.enableRotate = false;
    controls.enablePan = true;
    controls.enableZoom = true;
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.minDistance = 95;
    controls.maxDistance = 620;

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
      nodesRef.current.clear();
      linksRef.current.clear();
      nodeVisualsRef.current.clear();
      linkVisualsRef.current.clear();
    };
  }, []);

  useEffect(() => {
    const graph = graphRef.current;
    if (!graph) return;
    const reducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;

    const animateToView = (intro = false) => {
      if (animationRef.current !== null)
        cancelAnimationFrame(animationRef.current);
      if (hoverAnimationRef.current !== null)
        cancelAnimationFrame(hoverAnimationRef.current);
      const targetNodes = new Map(view.nodes.map((node) => [node.id, node]));
      const targetLinks = new Map(
        view.relations.map((relation) => [relation.id, relation]),
      );
      const nodeStarts = new Map(
        [...nodesRef.current].map(([id, node]) => {
          const visual = nodeVisualsRef.current.get(id);
          const target = targetNodes.get(id);
          if (target) Object.assign(node, target);
          return [
            id,
            {
              radius: visual?.userData.radius ?? radiusFor(node, timeRange),
              style: visual?.userData.style ?? nodeStyles[node.tier],
            },
          ];
        }),
      );
      const linkStarts = new Map(
        [...linksRef.current].map(([id, link]) => {
          const target = targetLinks.get(id);
          if (target) {
            link.tier = target.tier;
            link.label = target.label;
            link.evidenceGroupCount = target.evidenceGroupCount;
            if (target.conflict === undefined) delete link.conflict;
            else link.conflict = target.conflict;
          }
          return [id, linkVisualsRef.current.get(id)?.userData.opacity ?? 0];
        }),
      );

      const oldCenter = nodesRef.current.get(previousCenterRef.current);
      if (oldCenter && oldCenter.id !== centerId) {
        delete oldCenter.fx;
        delete oldCenter.fy;
        delete oldCenter.fz;
      }
      const center = nodesRef.current.get(centerId);
      if (!center) return;
      center.fx = center.x ?? 0;
      center.fy = center.y ?? 0;
      center.fz = Math.max(-depthLimit, Math.min(depthLimit, center.z ?? 0));
      graph.d3ReheatSimulation();

      const centerChanged = intro || previousCenterRef.current !== centerId;
      const duration = reducedMotion ? 0 : centerChanged ? 1200 : 320;
      const startCameraPosition = graph.camera().position.clone();
      const controls = graph.controls() as GraphControls;
      const startCameraTarget = controls.target.clone();
      const endCameraTarget = new THREE.Vector3(
        center.x ?? 0,
        center.y ?? 0,
        center.z ?? 0,
      );
      const offset = startCameraPosition.clone().sub(startCameraTarget);
      if (offset.lengthSq() < 1) offset.set(0, 0, 260);
      offset.setLength(
        intro
          ? Math.max(150, offset.length() * 0.52)
          : Math.max(150, Math.min(360, offset.length())),
      );
      const endCameraPosition = endCameraTarget.clone().add(offset);
      const startedAt = performance.now();
      setBusy(true);

      const animate = (now: number) => {
        const progress =
          duration === 0 ? 1 : Math.min(1, (now - startedAt) / duration);
        const eased = easeInOutCubic(progress);
        for (const [id, node] of nodesRef.current) {
          const visual = nodeVisualsRef.current.get(id);
          const start = nodeStarts.get(id);
          if (!visual || !start) continue;
          const targetRadius = radiusFor(node, timeRange);
          const targetStyle = nodeStyles[node.tier];
          const style = Object.fromEntries(
            Object.keys(targetStyle).map((key) => {
              const name = key as keyof NodeStyle;
              return [
                name,
                start.style[name] +
                  (targetStyle[name] - start.style[name]) * eased,
              ];
            }),
          ) as unknown as NodeStyle;
          applyNodeVisual(
            visual,
            node,
            start.radius + (targetRadius - start.radius) * eased,
            style,
          );
        }
        for (const [id, link] of linksRef.current) {
          const visual = linkVisualsRef.current.get(id);
          if (!visual) continue;
          const start = linkStarts.get(id) ?? 0;
          const target = relationOpacity[link.tier];
          const opacity = start + (target - start) * eased;
          for (const line of visual.userData.lines)
            (line.material as THREE.LineBasicMaterial).opacity = opacity;
          visual.userData.opacity = opacity;
        }
        if (centerChanged) {
          graph
            .camera()
            .position.lerpVectors(
              startCameraPosition,
              endCameraPosition,
              eased,
            );
          controls.target.lerpVectors(
            startCameraTarget,
            endCameraTarget,
            eased,
          );
          controls.update();
        }
        if (progress < 1) animationRef.current = requestAnimationFrame(animate);
        else {
          animationRef.current = null;
          setBusy(false);
        }
      };
      animationRef.current = requestAnimationFrame(animate);
      previousCenterRef.current = centerId;
    };

    if (!dataInitializedRef.current) {
      dataInitializedRef.current = true;
      const runtimeNodes = view.nodes.map((node, index) => {
        const angle = index * 2.399963229728653;
        const distance = 28 * Math.sqrt(index + 1);
        const runtimeNode: RuntimeNode = {
          ...node,
          tier: "twoHop",
          x: Math.cos(angle) * distance,
          y: Math.sin(angle) * distance,
          z: depthTargetForNode(node),
        };
        nodesRef.current.set(node.id, runtimeNode);
        return runtimeNode;
      });
      const runtimeLinks = view.relations.map((relation) => {
        const runtimeLink: RuntimeLink = {
          ...relation,
          tier: "ambient",
          source: relation.source,
          target: relation.target,
        };
        linksRef.current.set(relation.id, runtimeLink);
        return runtimeLink;
      });
      graph.graphData({ nodes: runtimeNodes, links: runtimeLinks });
      graph.zoomToFit(reducedMotion ? 0 : 500, 72);
      introTimeoutRef.current = window.setTimeout(
        () => {
          introTimeoutRef.current = null;
          animateToView(true);
        },
        reducedMotion ? 0 : 720,
      );
      return;
    }

    if (introTimeoutRef.current !== null) {
      window.clearTimeout(introTimeoutRef.current);
      introTimeoutRef.current = null;
    }
    animateToView();
  }, [centerId, timeRange, view]);

  return (
    <section className={styles.map} aria-label="동적 지식맵" aria-busy={busy}>
      <div ref={containerRef} className={styles.canvas} />
      <div className={styles.depthNote}>얕은 2.5D · z ±32 · 회전 없음</div>
      <nav
        className={styles.accessibleNodes}
        aria-label="탐색 가능한 node 목록"
      >
        {view.nodes.map((node) => (
          <button key={node.id} type="button" onClick={() => onSelect(node.id)}>
            {node.name} · {node.kind}
          </button>
        ))}
      </nav>
    </section>
  );
}
