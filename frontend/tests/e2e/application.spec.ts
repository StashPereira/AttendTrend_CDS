import { test, expect } from "@playwright/test";

test("signup → academic setup → schedule → attendance → analytics → reconciliation → logout", async ({
  page,
}) => {
  const errors: string[] = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("/");
  await page
    .getByRole("button", { name: "New here? Create an account" })
    .click();
  await page.getByLabel("Name", { exact: true }).fill("Alex Student");
  await page
    .getByLabel("Email", { exact: true })
    .fill(`e2e-${Date.now()}@example.com`);
  await page
    .getByLabel("Password", { exact: false })
    .fill("E2eLongPassword!123");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Welcome to AttendTrend" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Create semester", exact: true })
    .click();
  await page
    .getByRole("dialog")
    .getByLabel("Name", { exact: true })
    .fill("E2E Term");
  await page.getByLabel("Start date", { exact: true }).fill("2020-01-01");
  await page.getByLabel("End date", { exact: true }).fill("2020-06-30");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(
    page.getByText("Overall Attendance", { exact: true }),
  ).toBeVisible();
  await expect(page.getByText("0 of 0 classes attended")).toBeVisible();
  await page
    .getByRole("button", { name: "Data & Reconciliation", exact: true })
    .click();
  await page.getByRole("button", { name: "Subjects", exact: true }).click();
  await page.getByRole("button", { name: "Subject", exact: true }).click();
  await page
    .getByRole("dialog")
    .getByLabel("Name", { exact: true })
    .fill("Mathematics");
  await page.getByLabel("Course code", { exact: true }).fill("M101");
  await page.getByLabel("Instructor", { exact: true }).fill("Dr Teacher");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "M101", exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Calendar & Timetable", exact: true })
    .click();
  await page.getByRole("button", { name: "Timetable", exact: true }).click();
  await page.getByRole("button", { name: "+ Slot", exact: true }).click();
  await page.getByLabel("Start time", { exact: true }).fill("09:00");
  await page.getByLabel("End time", { exact: true }).fill("10:00");
  await page.getByLabel("Room", { exact: true }).fill("A1");
  await page.getByRole("button", { name: "Create", exact: true }).click();
  await expect(
    page.getByRole("cell", { name: "09:00–10:00", exact: true }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Attendance", exact: true }).click();
  await page.getByLabel("Attendance date").fill("2020-01-06");
  await page.getByLabel("Status for Mathematics").selectOption("present");
  await page.getByRole("button", { name: "Save day" }).click();
  await expect(page.getByText("1 of 1 classes attended")).toBeVisible();
  await page
    .getByRole("button", { name: "Insights & Analytics", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Subject Breakdown" }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Planning & Recovery", exact: true })
    .click();
  await page.getByLabel("Attend classes", { exact: true }).fill("0");
  await page.getByLabel("Miss classes", { exact: true }).fill("0");
  await page.getByRole("button", { name: "Calculate scenario" }).click();
  await expect(page.getByText(/Target met · 1\/1 classes/)).toBeVisible();
  await page.getByRole("button", { name: "Predictions", exact: true }).click();
  await expect(
    page.getByText("Limited history: smoothed statistical fallback"),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Data & Reconciliation", exact: true })
    .click();
  await page
    .getByLabel("Document", { exact: true })
    .setInputFiles({
      name: "university.csv",
      mimeType: "text/csv",
      buffer: Buffer.from(
        "code,name,attended,conducted,through_date\nM101,Mathematics,0,1,2020-01-06\n",
      ),
    });
  await page.getByRole("button", { name: "Upload", exact: true }).click();
  await page
    .getByRole("button", { name: "Review & confirm", exact: true })
    .click({ timeout: 30000 });
  await page.getByLabel("Use these counts as").selectOption("reconciliation");
  await page.getByRole("button", { name: "Confirm 1 reviewed rows" }).click();
  await page
    .getByRole("button", { name: "Reconciliation", exact: true })
    .click();
  await expect(page.getByText("mismatch", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Dashboard", exact: true }).click();
  await expect(page.getByText("1 of 1 classes attended")).toBeVisible();
  await page.screenshot({
    path: "test-results/dashboard-desktop.png",
    fullPage: true,
  });
  await page
    .getByRole("button", { name: "Notifications", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "Notifications", exact: true }).first(),
  ).toBeVisible();
  await page.getByRole("button", { name: "Profile", exact: true }).click();
  await page.getByLabel("Section", { exact: true }).fill("A");
  await page.getByRole("button", { name: "Save settings" }).click();
  await expect(page.getByRole("status")).toHaveText("Profile saved");
  await page.getByRole("button", { name: "Sign out", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Sign in", exact: true }),
  ).toBeVisible();
  expect(errors).toEqual([]);
});

test("mobile navigation and empty account have no horizontal overflow", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/");
  await page
    .getByRole("button", { name: "New here? Create an account" })
    .click();
  await page.getByLabel("Name", { exact: true }).fill("Mobile Student");
  await page
    .getByLabel("Email", { exact: true })
    .fill(`mobile-${Date.now()}@example.com`);
  await page
    .getByLabel("Password", { exact: false })
    .fill("E2eLongPassword!123");
  await page
    .getByRole("button", { name: "Create account", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Welcome to AttendTrend" }),
  ).toBeVisible();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page
    .getByRole("button", { name: "Notifications", exact: true })
    .last()
    .click();
  await expect(page.getByText("All caught up", { exact: true })).toBeVisible();
  const width = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    client: document.documentElement.clientWidth,
  }));
  expect(width.scroll).toBeLessThanOrEqual(width.client);
  await page.screenshot({
    path: "test-results/mobile-notifications.png",
    fullPage: true,
  });
});
