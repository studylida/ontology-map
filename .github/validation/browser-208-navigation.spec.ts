import { expect, test, type Page, type Route } from "@playwright/test";

test.use({ baseURL: "http://127.0.0.1:4173" });

const A = "9223372036854775807";
const B = "9223372036854775806";
const names: Record<string, string> = { [A]: "SK하이닉스", [B]: "HBF" };

function exploration(centerId: string) {
  const neighborId = centerId === A ? B : A;
  return {
    center_node_id: centerId,
    context_text: `${names[centerId]} 중심의 공개 관계입니다.`,
    graph: {
      nodes: [
        {
          node_id: centerId,
          name: names[centerId],
          node_type: { code: "TECHNOLOGY", display_name: "기술" },
          tier: "CENTER",
          activity_evidence_group_count: 6,
        },
        {
          node_id: neighborId,
          name: names[neighborId],
          node_type: { code: "TECHNOLOGY", display_name: "기술" },
          tier: "DIRECT",
          activity_evidence_group_count: 3,
        },
      ],
      relations: [
        {
          relation_id: `relation-${centerId}`,
          source_node_id: centerId,
          target_node_id: neighborId,
          relation_type_display_name: "관련 기술",
          directionality: "SYMMETRIC",
          supporting_evidence_group_count: 3,
          has_conflict: false,
        },
      ],
    },
    recommendations: [
      {
        target_node: {
          node_id: neighborId,
          name: names[neighborId],
          node_type: { code: "TECHNOLOGY", display_name: "기술" },
        },
        path: [
          {
            relation_id: `relation-${centerId}`,
            source_node_id: centerId,
            target_node_id: neighborId,
            source_node_name: names[centerId],
            target_node_name: names[neighborId],
            relation_type_display_name: "관련 기술",
            directionality: "SYMMETRIC",
          },
        ],
        reason_code: "DIRECT",
        via_node_id: null,
        supporting_evidence_group_count: 3,
      },
    ],
    followup_questions: [],
  };
}

const unavailable = {
  error: { code: "PUBLICATION_NOT_READY", retryable: true },
};

async function json(route: Route, body: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

type ExplorationHandler = (
  route: Route,
  centerId: string,
  range: "90d" | "1y",
) => Promise<void>;

async function installRoutes(
  page: Page,
  explorationHandler: ExplorationHandler,
  options: { relationEvidenceFails?: boolean } = {},
) {
  await page.route("**/api/v1/**", async (route) => {
    const url = new URL(route.request().url());
    const path = url.pathname;

    if (path === "/api/v1/nodes/search") {
      await json(route, {
        items: [
          {
            node_id: B,
            name: "HBF",
            node_type: { code: "TECHNOLOGY", display_name: "기술" },
          },
        ],
      });
      return;
    }

    const explorationMatch = path.match(/^\/api\/v1\/exploration\/([^/]+)$/);
    if (explorationMatch) {
      const range =
        url.searchParams.get("time_window") === "RECENT_1_YEAR" ? "1y" : "90d";
      await explorationHandler(route, explorationMatch[1], range);
      return;
    }

    if (/^\/api\/v1\/exploration\/[^/]+\/peripheral$/.test(path)) {
      await json(route, {
        graph: { nodes: [], relations: [] },
        next_cursor: null,
      });
      return;
    }

    if (path === `/api/v1/nodes/${A}/relations`) {
      await json(route, {
        items: [
          {
            relation_id: "rel-a-b",
            source_node_id: A,
            target_node_id: B,
            directionality: "SYMMETRIC",
            relation_type_display_name: "관련 기술",
            other_node: {
              node_id: B,
              name: "HBF",
              node_type: { code: "TECHNOLOGY", display_name: "기술" },
            },
            supporting_evidence_group_count: 3,
            has_conflict: false,
          },
        ],
        next_cursor: null,
      });
      return;
    }

    if (/^\/api\/v1\/nodes\/[^/]+\/(relations|questions)$/.test(path)) {
      await json(route, { items: [], next_cursor: null });
      return;
    }

    if (/^\/api\/v1\/relations\/[^/]+\/evidence$/.test(path)) {
      if (options.relationEvidenceFails) {
        await json(
          route,
          { error: { code: "PANEL_NOT_READY", retryable: true } },
          503,
        );
      } else {
        await json(route, { items: [], next_cursor: null });
      }
      return;
    }

    if (path === "/api/v1/topics") {
      await json(route, { items: [] });
      return;
    }

    await json(route, { items: [], next_cursor: null });
  });
}

async function searchAndChooseHbf(page: Page) {
  const search = page.getByRole("combobox", { name: "노드 검색" });
  await search.fill("HBF");
  await page.getByRole("option", { name: /HBF/ }).click();
}

test("A→B 503 keeps A until identical retry succeeds", async ({ page }) => {
  let bReads = 0;
  await installRoutes(page, async (route, centerId) => {
    if (centerId === B) {
      bReads += 1;
      if (bReads === 1) {
        await json(route, unavailable, 503);
        return;
      }
    }
    await json(route, exploration(centerId));
  });

  await page.goto(`/?center=${A}&range=90d`);
  await expect(page.getByRole("heading", { name: "SK하이닉스" })).toBeVisible();
  await searchAndChooseHbf(page);

  await expect(page.getByRole("alert")).toContainText("HBF를 열 수 없습니다.");
  await expect(page.getByRole("heading", { name: "SK하이닉스" })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`center=${A}`));

  await page.getByRole("button", { name: "다시 조회" }).click();
  await expect(page.getByRole("heading", { name: "HBF" })).toBeVisible({ timeout: 10_000 });
  await expect(page).toHaveURL(new RegExp(`center=${B}`));
  await expect(page.getByText("최신 공개 상태로 다시 불러왔습니다.")).toBeVisible();
});

test("range failure keeps successful selection and commits 1y only after retry", async ({ page }) => {
  let oneYearReads = 0;
  await installRoutes(page, async (route, centerId, range) => {
    if (centerId === A && range === "1y") {
      oneYearReads += 1;
      if (oneYearReads === 1) {
        await json(route, unavailable, 503);
        return;
      }
    }
    await json(route, exploration(centerId));
  });

  await page.goto(`/?center=${A}&range=90d`);
  await expect(page.getByRole("heading", { name: "SK하이닉스" })).toBeVisible();
  await page.getByRole("button", { name: "최근 1년" }).click();

  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByRole("button", { name: "최근 90일" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page.getByRole("button", { name: "최근 1년" })).toHaveAttribute(
    "aria-pressed",
    "false",
  );
  await expect(page).toHaveURL(/range=90d/);

  await page.getByRole("button", { name: "다시 조회" }).click();
  await expect(page.getByRole("button", { name: "최근 1년" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  await expect(page).toHaveURL(/range=1y/);
  await expect(page.getByText("최신 공개 상태로 다시 불러왔습니다.")).toBeVisible();
});

test("Back target failure keeps B and retry commits A without a new navigation", async ({ page }) => {
  let aReads = 0;
  await installRoutes(page, async (route, centerId) => {
    if (centerId === A) {
      aReads += 1;
      if (aReads === 2) {
        await json(route, unavailable, 503);
        return;
      }
    }
    await json(route, exploration(centerId));
  });

  await page.goto(`/?center=${A}&range=90d`);
  await expect(page.getByRole("heading", { name: "SK하이닉스" })).toBeVisible();
  await searchAndChooseHbf(page);
  await expect(page.getByRole("heading", { name: "HBF" })).toBeVisible({ timeout: 10_000 });
  await expect(page).toHaveURL(new RegExp(`center=${B}`));

  await page.goBack();
  await expect(page.getByRole("alert")).toBeVisible();
  await expect(page.getByRole("heading", { name: "HBF" })).toBeVisible();
  await expect(page).toHaveURL(new RegExp(`center=${A}`));

  await page.getByRole("button", { name: "다시 조회" }).click();
  await expect(page.getByRole("heading", { name: "SK하이닉스" })).toBeVisible({ timeout: 10_000 });
  await expect(page).toHaveURL(new RegExp(`center=${A}`));
  await expect(page.getByText("최신 공개 상태로 다시 불러왔습니다.")).toBeVisible();
});

test("Evidence first-read error stays modal and Escape restores opener focus", async ({ page }) => {
  await installRoutes(
    page,
    async (route, centerId) => json(route, exploration(centerId)),
    { relationEvidenceFails: true },
  );

  await page.goto(`/?center=${A}&range=90d`);
  await expect(page.getByRole("heading", { name: "SK하이닉스" })).toBeVisible();
  const opener = page
    .getByRole("navigation", { name: "지도 관계 목록" })
    .getByRole("button", { name: /SK하이닉스.*HBF/ });
  await expect(opener).toBeVisible();
  await opener.focus();
  await opener.press("Enter");

  await expect(page.getByRole("dialog")).toBeVisible();
  await expect(page.getByRole("alert")).toContainText(
    "현재 이 영역의 공개 자료를 불러올 수 없습니다.",
  );
  await expect(page.getByRole("button", { name: "다시 조회" })).toBeVisible();

  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(opener).toBeFocused();
});
