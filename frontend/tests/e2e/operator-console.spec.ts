import { expect, test } from '@playwright/test';

test('landing enters console', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('GÖKKALKAN')).toBeVisible();
  await page.getByRole('button', { name: 'Konsola Geç' }).click();
  await expect(page.getByText('Operatör Konsolu · hardware_mock')).toBeVisible();
  await expect(page.getByText('MOCK KAMERA')).toBeVisible();
});

test('Aşama 1 wrong-order fire logs penalty and does not advance', async ({ page }) => {
  await page.goto('/?console=1');
  await page.getByRole('button', { name: /Manuel/ }).click();
  await page.getByRole('button', { name: /M-3/ }).click();
  await page.getByRole('button', { name: 'ATEŞ' }).click();
  await expect(page.locator('.mission-metrics')).toContainText('Hedef 1/4');
  await expect(page.locator('.mission-metrics')).toContainText('Puan -5');
  await expect(page.getByText('WRONG_ORDER').first()).toBeVisible();
});

test('Aşama 2 fire-zone scenario blocks autonomous engagement', async ({ page }) => {
  await page.goto('/?console=1');
  await page.getByRole('button', { name: 'Aşama 2' }).click();
  await page.getByRole('button', { name: 'Otonom Başlat' }).click();
  await page.getByLabel('Blok senaryosu').selectOption('BLOCKED_FIRE_ZONE');
  await expect(page.getByText(/BLOCKED_FIRE_ZONE/).first()).toBeVisible();
  await expect(page.getByText('fire_enable').locator('..')).toContainText('blocked');
});

test('Aşama 3 friend target keeps fire gate blocked', async ({ page }) => {
  await page.goto('/?console=1');
  await page.getByRole('button', { name: 'Aşama 3' }).click();
  await page.getByRole('button', { name: 'Otonom Başlat' }).click();
  await page.getByRole('button', { name: /S3-F/ }).first().click();
  await expect(page.getByText('Dost ateş kilidi').locator('..')).toContainText('Kilitli');
  await expect(page.getByText(/BLOCKED_TARGET_GATE/).first()).toBeVisible();
  await expect(page.getByText('fire_enable').locator('..')).toContainText('blocked');
});

test('E-stop overlay is impossible to miss', async ({ page }) => {
  await page.goto('/?console=1');
  await page.getByRole('button', { name: /acil durdur/i }).first().click();
  await expect(page.getByText(/ACİL DURDUR AKTİF/)).toBeVisible();
});

test('1366 viewport keeps telemetry and command queue reachable', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto('/?console=1');
  await expect(page.getByText('KOMUT KUYRUĞU')).toBeVisible();
  await expect(page.getByText(/telemetri/i)).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});
