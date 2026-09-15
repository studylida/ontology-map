import { expect, test } from "@playwright/test";

test.use({ baseURL: "http://127.0.0.1:4173" });

const unavailable = {
  error: { code: "PUBLICATION_NOT_READY", retryable: true },
};

async function installTopicRoute(page: import("@playwright/test").Page) {
  await page.route("**/api/v1/topics", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        items: [
          {
            node_id: "9001",
            canonical_display_name: "AI 인프라",
            is_active: true,
          },
        ],
      }),
    });
  });
}

test("no-center is a normal re-entry state and Topic picker works", async ({ page }) => {
  await installTopicRoute(page);
  await page.goto("/?range=90d");

  await expect(
    page.getByText("탐색할 Node를 검색하거나 주제를 선택해 주세요.").first(),
  ).toBeVisible();
  await expect(page.getByRole("combobox", { name: "노드 검색" })).toBeEnabled();

  await page.getByRole("button", { name: "주제 목록 열기" }).click();
  await expect(page.getByRole("listbox", { name: "주제 목록" })).toBeVisible();
  await expect(page.getByRole("option", { name: "AI 인프라" })).toBeVisible();
});

test("initial 503 keeps re-entry controls and retries the identical read request", async ({ page }) => {
  let reads = 0;
  await installTopicRoute(page);
  await page.route("**/api/v1/exploration/222?time_window=RECENT_90_DAYS", async (route) => {
    reads += 1;
    await route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify(unavailable),
    });
  });

  await page.goto("/?center=222&range=90d");
  await expect(
    page.getByText("현재 이 Node의 공개 탐색 자료를 불러올 수 없습니다."),
  ).toBeVisible();
  await expect(page.getByRole("combobox", { name: "노드 검색" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "주제 목록 열기" })).toBeVisible();
  await expect(page.getByRole("button", { name: "다시 조회" })).toBeVisible();

  await page.getByRole("button", { name: "다시 조회" }).click();
  await expect.poll(() => reads).toBe(2);
  await expect(page).toHaveURL(/center=222/);
  await expect(page).toHaveURL(/range=90d/);
});

test("initial INVALID_REQUEST is non-retryable and distinct from network failure", async ({ page }) => {
  await installTopicRoute(page);
  await page.route("**/api/v1/exploration/333?time_window=RECENT_90_DAYS", async (route) => {
    await route.fulfill({
      status: 422,
      contentType: "application/json",
      body: JSON.stringify({
        error: { code: "INVALID_REQUEST", retryable: false },
      }),
    });
  });

  await page.goto("/?center=333&range=90d");
  await expect(
    page.getByText(
      "요청을 확인할 수 없습니다. 다른 Node를 검색하거나 주제를 선택해 주세요.",
    ),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "다시 조회" })).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "노드 검색" })).toBeEnabled();
  await expect(page.getByRole("button", { name: "주제 목록 열기" })).toBeVisible();
});
