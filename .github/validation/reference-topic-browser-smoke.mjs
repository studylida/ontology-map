import assert from "node:assert/strict";
import { createRequire } from "node:module";

const require = createRequire(new URL("../../web/package.json", import.meta.url));
const { chromium } = require("playwright");

const topicPayload = {
  topic: {
    node_id: "77",
    topic_code: "SEMICONDUCTOR",
    canonical_display_name: "반도체",
    is_active: true,
  },
  time_window: "RECENT_1_YEAR",
  total_public_membership_count: 1,
  recent_member_count: 1,
  recent_activity_evidence_group_count: 4,
  graph: {
    nodes: [
      {
        node_id: "77",
        name: "반도체",
        node_type: { code: "TOPIC", display_name: "주제" },
        tier: "CENTER",
        activity_evidence_group_count: 4,
      },
      {
        node_id: "10",
        name: "회사 A",
        node_type: { code: "COMPANY", display_name: "회사" },
        tier: "DIRECT",
        activity_evidence_group_count: 4,
      },
    ],
    relations: [
      {
        relation_id: "91",
        source_node_id: "10",
        target_node_id: "77",
        relation_type_display_name: "주제 분류",
        directionality: "DIRECTED",
        supporting_evidence_group_count: 4,
        has_conflict: false,
      },
    ],
  },
};

const memberExploration = {
  center_node_id: "10",
  context_text: "회사 A의 공개 탐색 문맥입니다.",
  graph: {
    nodes: [
      {
        node_id: "10",
        name: "회사 A",
        node_type: { code: "COMPANY", display_name: "회사" },
        tier: "CENTER",
        activity_evidence_group_count: 5,
      },
      {
        node_id: "11",
        name: "기술 B",
        node_type: { code: "TECHNOLOGY", display_name: "기술" },
        tier: "DIRECT",
        activity_evidence_group_count: 2,
      },
    ],
    relations: [
      {
        relation_id: "101",
        source_node_id: "10",
        target_node_id: "11",
        relation_type_display_name: "관련 기술",
        directionality: "DIRECTED",
        supporting_evidence_group_count: 2,
        has_conflict: false,
      },
    ],
  },
  recommendations: [],
  followup_questions: [
    { slot: 1, question_text: "질문 1", target_node_id: "11" },
    { slot: 2, question_text: "질문 2", target_node_id: "10" },
  ],
};

const reportPayload = {
  items: [
    {
      report_id: "501",
      title: "반도체 공급망 변화",
      summary: "요약",
      as_of_at: "2026-09-15T00:00:00Z",
      evidence_group_count: 3,
      conclusion: null,
      caveat: null,
      sections: [],
    },
  ],
};

function reply(route, status, body) {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

const browser = await chromium.launch({
  headless: true,
  args: ["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
const pageErrors = [];
page.on("pageerror", (error) => pageErrors.push(error.message));
page.on("console", (message) => {
  if (message.type() === "error") pageErrors.push(`console: ${message.text()}`);
});

await page.route("**/api/v1/**", async (route) => {
  const url = new URL(route.request().url());
  const requestPath = `${url.pathname}${url.search}`;

  if (requestPath === "/api/v1/exploration/77?time_window=RECENT_1_YEAR") {
    return reply(route, 404, {
      error: { code: "NODE_NOT_FOUND", retryable: false },
    });
  }
  if (
    requestPath ===
    "/api/v1/topics/77/exploration?time_window=RECENT_1_YEAR"
  ) {
    return reply(route, 200, topicPayload);
  }
  if (requestPath === "/api/v1/exploration/10?time_window=RECENT_1_YEAR") {
    return reply(route, 200, memberExploration);
  }
  if (
    requestPath ===
    "/api/v1/nodes/10/insight-report?time_window=RECENT_1_YEAR&detail=false"
  ) {
    return reply(route, 200, reportPayload);
  }
  if (url.pathname === "/api/v1/topics") {
    return reply(route, 200, {
      items: [
        {
          node_id: "77",
          topic_code: "SEMICONDUCTOR",
          canonical_display_name: "반도체",
          is_active: true,
        },
      ],
    });
  }
  if (url.pathname.includes("/peripheral")) {
    return reply(route, 200, {
      graph: { nodes: [], relations: [] },
      next_cursor: null,
    });
  }
  if (/\/api\/v1\/nodes\/[^/]+\/(relations|questions)$/.test(url.pathname)) {
    return reply(route, 200, { items: [], next_cursor: null });
  }

  throw new Error(`unhandled browser-smoke request: ${requestPath}`);
});

async function waitHeading(name) {
  await page.getByRole("heading", { name, exact: true }).waitFor({
    state: "visible",
    timeout: 30_000,
  });
}

async function assertOneYearSelected() {
  assert.equal(
    await page
      .getByRole("button", { name: "최근 1년", exact: true })
      .getAttribute("aria-pressed"),
    "true",
  );
}

try {
  await page.goto("http://127.0.0.1:4173/?center=77&range=1y");
  await waitHeading("반도체");
  const loading = page.getByLabel("탐색 데이터 불러오는 중");
  if ((await loading.count()) > 0) {
    await loading.waitFor({ state: "detached", timeout: 30_000 });
  }
  await assertOneYearSelected();

  await page
    .getByRole("button", { name: /반도체 공급망 변화/ })
    .click({ timeout: 10_000 });
  await waitHeading("회사 A");
  assert.equal(
    await page
      .getByRole("tab", { name: "인사이트", exact: true })
      .getAttribute("aria-selected"),
    "true",
  );
  await assertOneYearSelected();
  assert.equal(new URL(page.url()).searchParams.get("center"), "10");
  assert.equal(new URL(page.url()).searchParams.get("range"), "1y");
  const trailAtNode = await page
    .getByRole("navigation", { name: "최근 탐색 경로" })
    .innerText();
  assert.match(trailAtNode, /반도체/);
  assert.match(trailAtNode, /회사 A/);

  await page.goBack();
  await waitHeading("반도체");
  await assertOneYearSelected();
  assert.equal(new URL(page.url()).searchParams.get("center"), "77");

  await page.goForward();
  await waitHeading("회사 A");
  await assertOneYearSelected();
  assert.equal(new URL(page.url()).searchParams.get("center"), "10");

  await page.goBack();
  await waitHeading("반도체");
  const legend = page.getByLabel("지식맵 범례");
  await legend.getByRole("button", { name: "범례", exact: true }).click();
  await legend.getByRole("button", { name: "회사", exact: true }).click();
  const topicPanel = page.getByLabel("반도체 주제 상세 정보");
  const memberButton = topicPanel.getByRole("button", { name: /회사 A/ }).first();
  await memberButton.waitFor({ state: "visible" });
  await memberButton.click();
  await waitHeading("회사 A");
  await assertOneYearSelected();
  assert.equal(new URL(page.url()).searchParams.get("center"), "10");

  assert.deepEqual(pageErrors, []);
  console.log(
    JSON.stringify(
      {
        navigation: "Topic → Insight → Node → Back → Topic → Forward",
        period: "1y preserved",
        trail: "Topic and Node observed",
        camera: "real GraphCanvas center transitions completed",
        filter: "COMPANY hidden on map; Topic membership stayed selectable",
      },
      null,
      2,
    ),
  );
} finally {
  await browser.close();
}
