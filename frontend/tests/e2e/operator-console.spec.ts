import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

async function openConsole(page: Page) {
  await page.goto('/?console=1');
  await page.getByRole('button', { name: 'Rehberi atla' }).click();
}

function headerMetrics(page: Page) {
  return page.locator('.header-metrics');
}

async function headerText(page: Page) {
  return (await headerMetrics(page).textContent()) ?? '';
}

test('landing is simulator-branded and removes mock/keyboard skip copy', async ({ page }) => {
  await page.goto('/');

  await expect(page.getByText('GÖKKALKAN')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Simülatöre Başla' })).toBeVisible();
  await expect(page.getByText(/mock/i)).toHaveCount(0);
  await expect(page.getByText(/Enter\/Esc ile atla/i)).toHaveCount(0);

  const fits = await page.evaluate(() => {
    const title = document.querySelector('.signal');
    const card = document.querySelector('.boot-card');
    if (!title || !card) return false;
    const titleRect = title.getBoundingClientRect();
    const cardRect = card.getBoundingClientRect();
    const lineHeight = Number.parseFloat(window.getComputedStyle(title).lineHeight);
    return titleRect.left >= cardRect.left && titleRect.right <= cardRect.right && titleRect.height <= lineHeight * 1.25;
  });
  expect(fits).toBe(true);
});

test('console prioritizes parkour, guidance, and central fire action', async ({ page }) => {
  await openConsole(page);

  await expect(page.getByTestId('parkour-hero')).toBeVisible();
  await expect(page.getByTestId('competition-guidance')).toContainText('Competition Guidance');
  await expect(page.getByTestId('fire-cluster')).toContainText('FIRE');
  await expect(page.getByText('Advanced / Debug')).toBeVisible();
  await expect(page.getByText('Safety gate')).toBeHidden();

  await page.getByText('Advanced / Debug').click();
  await expect(page.getByText('Safety gate')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test('contextual onboarding pauses timer and is skippable', async ({ page }) => {
  await page.goto('/?console=1');

  await expect(page.getByTestId('tutorial-overlay')).toContainText('simülasyon duraklatıldı');
  await expect(headerMetrics(page)).toContainText('Süre 5:00');
  await page.waitForTimeout(900);
  await expect(headerMetrics(page)).toContainText('Süre 5:00');

  await page.getByRole('button', { name: 'Devam' }).last().click();
  await expect(page.getByTestId('tutorial-overlay')).toContainText('Menzil bantlarını izle');
  await page.getByRole('button', { name: 'Rehberi atla' }).click();
  await expect(page.getByTestId('tutorial-overlay')).toHaveCount(0);
});

test('Aşama 1 applies manual target order and wrong-target penalty', async ({ page }) => {
  await openConsole(page);

  await page.getByRole('button', { name: /S1-3 F16/ }).click();
  await expect(page.getByTestId('competition-guidance')).toContainText('wrong target selected');
  await page.getByRole('button', { name: 'FIRE' }).click();
  await expect(headerMetrics(page)).toContainText('Puan -5');
  await expect(page.getByTestId('stage-1-order')).toContainText('Balistik Füze');

  await page.getByRole('button', { name: /S1-1 Balistik Füze/ }).click();
  await page.getByRole('button', { name: 'FIRE' }).click();
  await expect(headerMetrics(page)).toContainText('Puan 0');
});

test('Aşama 2 shows four autonomous rounds and scores by destroyed count', async ({ page }) => {
  await openConsole(page);

  await page.getByRole('button', { name: 'Aşama 2' }).click();
  await expect(headerMetrics(page)).toContainText('Mod Otonom');
  await expect(headerMetrics(page)).toContainText('Tur 1/4');
  await expect(page.getByRole('button', { name: /S2-R1-L/ })).toHaveCount(3);
  await expect(page.getByText(/sınıflandırma beklenmez/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'OTONOM ATEŞ' })).toBeDisabled();

  await expect.poll(() => headerText(page), { timeout: 8_000 }).not.toContain('Puan 0');
});

test('Aşama 3 protects friendly targets and exposes range-gate reasons', async ({ page }) => {
  await openConsole(page);

  await page.getByRole('button', { name: 'Aşama 3' }).click();
  await expect(headerMetrics(page)).toContainText('Tur 1/8');
  await expect(page.getByRole('button', { name: /Düşman/ })).toHaveCount(1);
  await expect(page.getByRole('button', { name: /Dost/ })).toHaveCount(2);

  await page.getByRole('button', { name: /Dost/ }).first().click();
  await expect(page.getByTestId('competition-guidance')).toContainText('friendly target protected');
  await expect(page.getByTestId('competition-guidance')).toContainText('-10 ceza riski');
});

test('emergency stop freezes simulator state and reports summary safety', async ({ page }) => {
  await openConsole(page);

  await page.getByRole('button', { name: 'Aşama 2' }).click();
  await page.waitForTimeout(500);
  await page.getByRole('button', { name: 'Acil Durdur' }).click();
  await expect(headerMetrics(page)).toContainText('Acil Durdur aktif');
  const before = await headerText(page);
  await page.waitForTimeout(800);
  expect(await headerText(page)).toBe(before);
});
