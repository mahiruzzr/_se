const { test, expect } = require("@playwright/test");

async function addTask(page, title) {
  await page.getByLabel("任務名稱").fill(title);
  await page.getByRole("button", { name: "新增" }).click();
  await expect(page.getByRole("listitem").filter({ hasText: title })).toBeVisible();
}

test.beforeEach(async ({ request }) => {
  const response = await request.get("/api/tasks");
  const tasks = await response.json();

  for (const task of tasks) {
    await request.delete(`/api/tasks/${task.id}`);
  }
});

test("新增任務後可標記完成，重新載入仍保留", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "今日任務" })).toBeVisible();
  await expect(page.locator("#task-list")).toBeEmpty();

  await addTask(page, "買牛奶");

  const task = page.getByRole("listitem").filter({ hasText: "買牛奶" });
  await expect(task.getByRole("checkbox")).not.toBeChecked();
  await expect(page.locator("#count-active")).toHaveText("1");
  await expect(page.locator("#summary")).toContainText("還有 1 件進行中");

  await task.getByRole("checkbox").check();

  await expect(task).toHaveClass(/is-completed/);
  await expect(page.locator("#count-active")).toHaveText("0");
  await expect(page.locator("#count-completed")).toHaveText("1");

  await page.reload();

  const reloaded = page.getByRole("listitem").filter({ hasText: "買牛奶" });
  await expect(reloaded).toBeVisible();
  await expect(reloaded.getByRole("checkbox")).toBeChecked();
});

test("空白任務名稱顯示錯誤且不會新增", async ({ page }) => {
  await page.goto("/");

  await page.getByLabel("任務名稱").fill("   ");
  await page.getByRole("button", { name: "新增" }).click();

  await expect(page.getByRole("alert")).toHaveText("請先輸入任務名稱");
  await expect(page.getByRole("listitem")).toHaveCount(0);
  await expect(page.getByText("清單還是空的")).toBeVisible();
});

test("可以刪除指定任務且不影響其他任務", async ({ page }) => {
  await page.goto("/");

  await addTask(page, "買牛奶");
  await addTask(page, "寫週報");

  await page.getByRole("button", { name: "刪除「買牛奶」" }).click();

  await expect(page.getByRole("listitem").filter({ hasText: "買牛奶" })).toHaveCount(0);
  await expect(page.getByRole("listitem").filter({ hasText: "寫週報" })).toBeVisible();
  await expect(page.locator("#count-all")).toHaveText("1");
});

test("篩選器可在全部、進行中與已完成之間切換", async ({ page }) => {
  await page.goto("/");

  await addTask(page, "跑步");
  await addTask(page, "看書");
  await page.getByRole("checkbox", { name: /跑步/ }).check();

  await page.getByRole("button", { name: /進行中/ }).click();
  await expect(page.getByRole("listitem")).toHaveCount(1);
  await expect(page.getByRole("listitem")).toContainText("看書");
  await expect(page.getByRole("button", { name: /進行中/ })).toHaveAttribute("aria-pressed", "true");

  await page.getByRole("button", { name: /已完成/ }).click();
  await expect(page.getByRole("listitem")).toHaveCount(1);
  await expect(page.getByRole("listitem")).toContainText("跑步");

  await page.getByRole("button", { name: /全部/ }).click();
  await expect(page.getByRole("listitem")).toHaveCount(2);
});
