import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

async function openConsole(page: Page) {
  await page.goto('/?console=1');
  await page.getByRole('button', { name: 'Bu aşamada rehberi atla' }).click();
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
  await expect(page.getByRole('button', { name: 'Operatör Paneli' })).toBeVisible();
  await expect(page.getByText(/mock/i)).toHaveCount(0);
  await expect(page.getByText(/Enter\/Esc ile atla/i)).toHaveCount(0);
  await expect(page.locator('.radar-sweep')).toHaveCount(0);

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

  const startButtonContrast = await page.getByRole('button', { name: 'Simülatöre Başla' }).evaluate((button) => {
    const style = getComputedStyle(button);
    return { background: style.backgroundColor, color: style.color };
  });
  expect(startButtonContrast.color).toBe('rgb(0, 19, 25)');
});

test('console prioritizes parkour, guidance, and central fire action', async ({ page }) => {
  await openConsole(page);

  await expect(page.getByTestId('parkour-hero')).toBeVisible();
  await expect(page.locator('.parkour-hero > img')).toHaveCount(0);
  await expect(page.getByTestId('competition-guidance')).toContainText('Görev Paneli');
  await expect(page.getByText('Competition Guidance')).toHaveCount(0);
  await expect(page.getByTestId('fire-cluster')).toContainText('ATEŞ KİLİTLİ');
  await expect(page.getByTestId('competition-guidance')).toContainText('Seçili hedef yok');
  await expect(page.getByText('Telemetri / Debug')).toBeVisible();
  await expect(page.getByText('Güvenlik kapısı')).toBeHidden();

  await page.getByText('Telemetri / Debug').click();
  await expect(page.getByText('Güvenlik kapısı')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test('contextual onboarding pauses timer and is skippable', async ({ page }) => {
  await page.goto('/?console=1');

  await expect(page.getByTestId('tutorial-overlay')).toContainText('simülasyon duraklatıldı');
  await expect(page.getByTestId('tutorial-overlay')).toContainText('Aşama 1’de 5/10/15 m');
  await expect(headerMetrics(page)).toContainText('Süre 5:00');
  await page.waitForTimeout(900);
  await expect(headerMetrics(page)).toContainText('Süre 5:00');

  await page.getByRole('button', { name: 'Devam' }).last().click();
  await expect(page.getByTestId('tutorial-overlay')).toContainText('Menzil bantlarını izle');
  await page.getByRole('button', { name: 'Bu aşamada rehberi atla' }).click();
  await expect(page.getByTestId('tutorial-overlay')).toHaveCount(0);

  await page.getByRole('button', { name: 'Aşama 2' }).click();
  await expect(page.getByTestId('tutorial-overlay')).toBeVisible();
  await page.getByTestId('tutorial-overlay').getByRole('button', { name: 'Devam' }).click();
  await page.getByTestId('tutorial-overlay').getByRole('button', { name: 'Devam' }).click();
  await expect(page.getByTestId('tutorial-overlay')).toContainText('Aşama 2 otonom akıştır');
});

test('tutorial copy and buttons stay readable on narrow viewports', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/?console=1');

  await expect(page.getByTestId('tutorial-overlay')).toContainText('Aşama 1’de 5/10/15 m');
  await page.getByTestId('tutorial-overlay').getByRole('button', { name: 'Devam' }).click();
  await page.getByTestId('tutorial-overlay').getByRole('button', { name: 'Devam' }).click();
  await page.getByTestId('tutorial-overlay').getByRole('button', { name: 'Devam' }).click();
  await expect(page.getByTestId('tutorial-overlay')).toContainText('ATEŞ düğmesi');
  await expect(page.getByTestId('tutorial-overlay')).not.toContainText('FIRE');

  const readable = await page.evaluate(() => {
    const overlay = document.querySelector('[data-testid="tutorial-overlay"]');
    const card = document.querySelector('.tutorial-card');
    const buttons = Array.from(document.querySelectorAll('.tutorial-card button'));
    if (!overlay || !card || buttons.length === 0) return false;
    const color = getComputedStyle(overlay).backgroundColor;
    const rgbaAlpha = color.match(/rgba?\((?:[^,]+,\s*){3}([^,)]+)/)?.[1];
    const slashAlpha = color.match(/\/\s*([0-9.]+)\)?$/)?.[1];
    const overlayAlpha = Number.parseFloat(rgbaAlpha ?? slashAlpha ?? '1');
    const cardRect = card.getBoundingClientRect();
    const nextButton = buttons.find((button) => button.textContent?.toLocaleLowerCase('tr-TR').includes('devam'));
    const nextButtonColor = nextButton ? getComputedStyle(nextButton).color : '';
    return overlayAlpha >= 0.7 && nextButtonColor === 'rgb(7, 16, 22)' && buttons.every((button) => {
      const rect = button.getBoundingClientRect();
      return rect.left >= cardRect.left && rect.right <= cardRect.right && rect.height >= 40;
    });
  });
  expect(readable).toBe(true);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test('compact dashboard avoids horizontal overflow on desktop and narrow viewports', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await openConsole(page);
  await expect(page.getByTestId('bottom-action-bar')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);

  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload();
  await page.getByRole('button', { name: 'Bu aşamada rehberi atla' }).click();
  await expect(page.getByTestId('competition-guidance')).toContainText('Görev Paneli');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test('tutorial restart preserves the active stage context', async ({ page }) => {
  await openConsole(page);
  await page.getByRole('button', { name: 'Aşama 3' }).click();
  await page.getByRole('button', { name: 'Bu aşamada rehberi atla' }).click();

  await page.getByRole('button', { name: 'Rehber' }).click();
  await expect(page.getByTestId('tutorial-overlay')).toContainText('simülasyon duraklatıldı');
  await page.getByTestId('tutorial-overlay').getByRole('button', { name: 'Devam' }).click();
  await page.getByTestId('tutorial-overlay').getByRole('button', { name: 'Devam' }).click();
  await expect(page.getByTestId('tutorial-overlay')).toContainText('Dost hedefler korunur');
});

test('Aşama 1 applies manual target order and wrong-target penalty', async ({ page }) => {
  await openConsole(page);

  await page.getByRole('button', { name: /S1-3.*F16/ }).click();
  await expect(page.getByTestId('competition-guidance')).toContainText('yanlış hedef seçildi');
  await page.getByRole('button', { name: 'CEZA RİSKİ' }).click();
  await expect(headerMetrics(page)).toContainText('Puan -5');
  await expect(page.getByTestId('stage-1-order')).toContainText('Balistik');

  await page.getByRole('button', { name: /S1-1.*Balistik Füze/ }).click();
  await page.getByRole('button', { name: 'ATEŞ HAZIR' }).click();
  await expect(headerMetrics(page)).toContainText('Puan 0');
});

test('selection defaults are stage-specific and toggle off on second click', async ({ page }) => {
  await openConsole(page);

  await expect(page.getByTestId('competition-guidance')).toContainText('Seçili hedef yok');
  await page.getByRole('button', { name: /S1-1.*Balistik Füze/ }).click();
  await expect(page.getByTestId('competition-guidance')).toContainText('S1-1');
  await page.getByRole('button', { name: /S1-1.*Balistik Füze/ }).click();
  await expect(page.getByTestId('competition-guidance')).toContainText('Seçili hedef yok');

  await page.getByRole('button', { name: 'Aşama 3' }).click();
  await page.getByRole('button', { name: 'Bu aşamada rehberi atla' }).click();
  await expect(page.getByTestId('competition-guidance')).toContainText('Düşman');
});

test('Aşama 2 exposes practice rounds through Tur 8 and scores by destroyed count', async ({ page }) => {
  test.setTimeout(40_000);
  await openConsole(page);

  await page.getByRole('button', { name: 'Aşama 2' }).click();
  await page.getByRole('button', { name: 'Bu aşamada rehberi atla' }).click();
  await expect(headerMetrics(page)).toContainText('Mod Otonom');
  await expect(headerMetrics(page)).toContainText('Tur 1/8');
  await expect(page.locator('.stage-checklist.compact')).toContainText('Tur 8');
  await expect(page.getByRole('button', { name: /S2-R1-L/ })).toHaveCount(3);
  const initialRotation = Number(await page.getByTestId('steel-dome').getAttribute('data-rotation'));
  expect(initialRotation).toBeGreaterThan(35);
  expect(initialRotation).toBeLessThan(55);
  const movingTarget = page.getByRole('button', { name: /S2-R1-L1/ });
  const startBox = await movingTarget.boundingBox();
  await page.waitForTimeout(800);
  const movedBox = await movingTarget.boundingBox();
  expect(startBox).not.toBeNull();
  expect(movedBox).not.toBeNull();
  expect(Math.abs((movedBox?.x ?? 0) - (startBox?.x ?? 0)) + Math.abs((movedBox?.y ?? 0) - (startBox?.y ?? 0))).toBeGreaterThan(10);
  await expect(page.getByTestId('competition-guidance')).toContainText('Seçili hedef yok');
  await expect(page.getByText(/sınıflandırma beklenmez/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'OTONOM AKTİF' })).toBeDisabled();

  await page.waitForTimeout(200);
  await expect(headerMetrics(page)).toContainText('Puan 0');
  await expect.poll(() => headerText(page), { timeout: 15_000 }).not.toContain('Puan 0');
});

test('strict competition mode keeps Aşama 2 at the official 4 rounds', async ({ page }) => {
  await openConsole(page);

  await page.getByRole('button', { name: 'Aşama 2' }).click();
  await page.getByRole('button', { name: 'Bu aşamada rehberi atla' }).click();
  await page.getByRole('button', { name: 'Pratik' }).click();
  await expect(headerMetrics(page)).toContainText('Tur 1/4');
  await expect(page.locator('.stage-checklist.compact')).toContainText('Tur 4');
  await expect(page.locator('.stage-checklist.compact')).not.toContainText('Tur 5');
});

test('Aşama 3 protects friendly targets and exposes range-gate reasons', async ({ page }) => {
  await openConsole(page);

  await page.getByRole('button', { name: 'Aşama 3' }).click();
  await page.getByRole('button', { name: 'Bu aşamada rehberi atla' }).click();
  await expect(headerMetrics(page)).toContainText('Tur 1/8');
  const rotations: number[] = [];
  for (let index = 0; index < 4; index += 1) {
    await page.waitForTimeout(120);
    rotations.push(Number(await page.getByTestId('steel-dome').getAttribute('data-rotation')));
  }
  expect(rotations[0]).toBeGreaterThan(55);
  expect(Math.max(...rotations.slice(1).map((rotation, index) => Math.abs(rotation - rotations[index])))).toBeLessThan(20);
  await expect(page.getByRole('button', { name: /Düşman/ })).toHaveCount(1);
  await expect(page.getByRole('button', { name: /Dost/ })).toHaveCount(2);

  await page.getByRole('button', { name: /Dost/ }).first().click({ force: true });
  await expect(page.getByTestId('competition-guidance')).toContainText('dost hedef korunuyor');
  await expect(page.getByTestId('competition-guidance')).toContainText('-10 ceza riski');
});

test('emergency stop freezes simulator state and reports summary safety', async ({ page }) => {
  await openConsole(page);

  await page.getByRole('button', { name: 'Aşama 2' }).click();
  await page.getByRole('button', { name: 'Bu aşamada rehberi atla' }).click();
  await page.waitForTimeout(500);
  await page.getByRole('button', { name: 'Acil Durdur' }).click();
  await expect(headerMetrics(page)).toContainText('Acil Durdur aktif');
  const before = await headerText(page);
  await page.waitForTimeout(800);
  expect(await headerText(page)).toBe(before);
});


test('landing opens the dry-run real operator panel without live hardware claims', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: 'Operatör Paneli' }).click();
  await expect(page.getByTestId('operator-panel')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'GÖKKALKAN OPERATÖR PANELİ' })).toBeVisible();
  await expect(page.getByText('DRY-RUN AÇIK · fiziksel çıkış yok')).toBeVisible();
  await expect(page.getByText('UI doğrudan ateşleme/imha hattını enerjilendirmez.')).toBeVisible();
  await expect(page.getByText(/Puan/)).toHaveCount(0);

  await expect(page.getByRole('button', { name: 'FIRE INTENT KİLİTLİ' })).toBeDisabled();
  await page.getByRole('button', { name: 'Otonom' }).click();
  await expect(page.getByRole('button', { name: 'FIRE INTENT GÖNDER (DRY-RUN)' })).toBeEnabled();
  await page.getByRole('button', { name: 'FIRE INTENT GÖNDER (DRY-RUN)' }).click();
  await expect(page.locator('article').filter({ hasText: 'FireIntent · Kabul' }).first()).toContainText('fiziksel çıkış üretilmedi');
});

test('operator panel can be opened directly with query parameter and returns to simulator', async ({ page }) => {
  await page.goto('/?operator=1');

  await expect(page.getByTestId('operator-panel')).toBeVisible();
  await page.getByRole('button', { name: 'Simülatöre dön' }).click();
  await expect(page.getByTestId('tutorial-overlay')).toBeVisible();
  await expect(page.getByTestId('parkour-hero')).toBeVisible();
});
