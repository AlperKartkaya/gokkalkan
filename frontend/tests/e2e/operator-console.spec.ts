import { expect, test } from '@playwright/test';
import type { Page } from '@playwright/test';

async function holdManualArm(page: Page) {
  const arm = page.getByRole('button', { name: 'Basılı Kur' });
  await arm.dispatchEvent('pointerdown');
  await expect(page.getByText(/Atış hattı:/)).toContainText('Kuruluyor');
  await page.waitForTimeout(550);
  await expect(page.getByText(/Atış hattı:/)).toContainText('Atış hattı kuruldu');
  await arm.dispatchEvent('pointerup');
}

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
  await expect(page.getByText(/ceza riski/)).toBeVisible();
  await holdManualArm(page);
  await page.getByRole('button', { name: 'ATEŞ' }).click();
  await expect(page.locator('.mission-metrics')).toContainText('Hedef 1/4');
  await expect(page.locator('.mission-metrics')).toContainText('Puan -5');
  await expect(page.getByText('WRONG_ORDER').first()).toBeVisible();
});

test('Aşama 1 manual pan tilt buttons update mechanical readouts', async ({ page }) => {
  await page.goto('/?console=1');
  await page.getByRole('button', { name: /Manuel/ }).click();
  await page.getByRole('button', { name: '▶' }).click();
  await page.getByRole('button', { name: '▲' }).click();
  await expect(page.getByText(/PAN \+2\.0°/)).toBeVisible();
  await expect(page.getByText(/TILT \+2\.0°/)).toBeVisible();
});

test('Aşama 1 fire button requires held arming command', async ({ page }) => {
  await page.goto('/?console=1');
  await page.getByRole('button', { name: /Manuel/ }).click();
  const fire = page.getByRole('button', { name: 'ATEŞ' });
  await expect(fire).toBeDisabled();

  const arm = page.getByRole('button', { name: 'Basılı Kur' });
  await arm.dispatchEvent('pointerdown');
  await expect(page.getByText(/Atış hattı:/)).toContainText('Kuruluyor');
  await expect(fire).toBeDisabled();
  await page.waitForTimeout(550);
  await expect(page.getByText(/Atış hattı:/)).toContainText('Atış hattı kuruldu');
  await expect(fire).toBeEnabled();
  await arm.dispatchEvent('pointerup');
});

test('Aşama 1 arming also works with deliberate click for accessibility', async ({ page }) => {
  await page.goto('/?console=1');
  await page.getByRole('button', { name: /Manuel/ }).click();
  const fire = page.getByRole('button', { name: 'ATEŞ' });
  await expect(fire).toBeDisabled();
  await page.getByRole('button', { name: 'Basılı Kur' }).click();
  await page.waitForTimeout(550);
  await expect(page.getByText(/Atış hattı:/)).toContainText('Atış hattı kuruldu');
  await expect(fire).toBeEnabled();
});

test('Aşama 2 fire-zone scenario blocks autonomous engagement', async ({ page }) => {
  await page.goto('/?console=1');
  await page.getByRole('button', { name: 'Aşama 2' }).click();
  await page.getByRole('button', { name: 'Otonom Başlat' }).click();
  await page.getByLabel('Blok senaryosu').selectOption('BLOCKED_FIRE_ZONE');
  await expect(page.getByText(/BLOCKED_FIRE_ZONE/).first()).toBeVisible();
  await expect(page.getByText('fire_enable').locator('..')).toContainText('blocked');
  await expect(page.getByTestId('mock-strike')).toHaveCount(0);
});

test('Aşama 3 friend target keeps fire gate blocked', async ({ page }) => {
  await page.goto('/?console=1');
  await page.getByRole('button', { name: 'Aşama 3' }).click();
  await page.getByRole('button', { name: 'Otonom Başlat' }).click();
  await page.getByRole('button', { name: /S3-F/ }).first().click();
  await expect(page.getByText('Dost ateş kilidi').locator('..')).toContainText('Kilitli');
  await expect(page.getByText(/BLOCKED_TARGET_GATE/).first()).toBeVisible();
  await expect(page.getByText('fire_enable').locator('..')).toContainText('blocked');
  await expect(page.getByTestId('mock-strike')).toHaveCount(0);
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

test('real-world competition simulation runs through Aşama 1-3', async ({ page }) => {
  await page.goto('/?console=1');
  await page.getByRole('button', { name: 'Tam Yarışma Simülasyonu' }).click();
  await expect(page.getByText(/GERÇEK YARIŞMA SİM/)).toBeVisible();
  await expect(page.getByText('Yarışma Provası')).toBeVisible();
  await expect(page.getByText('REALWORLD_SIM_ON').first()).toBeVisible();
  await expect(page.getByTestId('sensor-fusion-panel')).toContainText('LiDAR MOCK');
  await expect(page.getByTestId('sensor-fusion-panel')).toContainText('Radar MOCK');
  await expect(page.getByTestId('competition-course')).toBeVisible();
  await expect(page.getByTestId('course-point-a')).toBeVisible();
  await expect(page.getByTestId('course-point-b')).toBeVisible();
  await expect(page.getByTestId('range-5m')).toBeVisible();
  await expect(page.getByTestId('range-10m')).toBeVisible();
  await expect(page.getByTestId('range-15m')).toBeVisible();

  await page.getByRole('button', { name: /Manuel/ }).click();
  let checkedStrike = false;
  for (const target of [/M-1/, /M-2/, /M-3/, /M-4/]) {
    await page.getByRole('button', { name: target }).click();
    await page.getByRole('button', { name: '▶' }).click();
    await holdManualArm(page);
    await page.getByRole('button', { name: 'ATEŞ' }).click();
    if (!checkedStrike) {
      await expect(page.getByTestId('mock-strike').first()).toBeVisible();
      checkedStrike = true;
    }
  }
  await expect(page.locator('.mission-metrics')).toContainText('Hedef 4/4');
  await expect(page.locator('.mission-metrics')).toContainText(/Puan (5[0-9]|[6-9][0-9])/);

  await page.getByRole('button', { name: 'Aşama 2' }).click();
  await page.getByRole('button', { name: 'Otonom Başlat' }).click();
  await page.getByRole('button', { name: 'ANGAJMAN' }).click();
  await page.getByRole('button', { name: 'ANGAJMAN' }).click();
  await page.getByRole('button', { name: 'ANGAJMAN' }).click();
  await page.getByRole('button', { name: 'Turu Bitir' }).click();
  await expect(page.getByText('ROUND_SCORE').first()).toBeVisible();

  await page.getByRole('button', { name: 'Aşama 3' }).click();
  await page.getByRole('button', { name: 'Otonom Başlat' }).click();
  await page.locator('.track-box.candidate').first().click();
  await expect(page.getByText(/Düşman hedef.*menzil uygun/)).toBeVisible();
  const stage3Engage = page.getByRole('button', { name: 'ANGAJMAN' });
  await stage3Engage.click();
  await expect(page.getByText('AUTO_ENGAGE').first()).toBeVisible();
  await expect(page.getByTestId('mock-strike').first()).toBeVisible();
  await expect(stage3Engage).toBeDisabled();
  await expect(page.getByText('fire_enable').locator('..')).toContainText('blocked');
});

test('landing Gökkalkan title fits inside boot card', async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto('/');
  const fits = await page.evaluate(() => {
    const title = document.querySelector('.signal');
    const card = document.querySelector('.boot-card');
    if (!title || !card) return false;
    const titleRect = title.getBoundingClientRect();
    const cardRect = card.getBoundingClientRect();
    return titleRect.left >= cardRect.left && titleRect.right <= cardRect.right;
  });
  expect(fits).toBe(true);
});

test('stage selection auto-configures Şartname mode expectations', async ({ page }) => {
  await page.goto('/?console=1');
  await page.getByRole('button', { name: 'Aşama 1' }).click();
  await expect(page.locator('.modebar').getByRole('button', { name: /Manuel/ })).toHaveClass(/active/);
  await page.getByRole('button', { name: 'Aşama 2' }).click();
  await expect(page.locator('.modebar').getByRole('button', { name: /Otonom/ })).toHaveClass(/active/);
  await expect(page.getByText('Otonom Takip').first()).toBeVisible();
  await page.getByRole('button', { name: 'Aşama 3' }).click();
  await expect(page.locator('.modebar').getByRole('button', { name: /Otonom/ })).toHaveClass(/active/);
});

test('hands-off replay loads scenario files and advances visible outcome state', async ({ page }) => {
  await page.goto('/?console=1&handsOff=1&speed=4');
  await expect(page.getByTestId('hands-off-replay')).toContainText('Hands-off Yarışma Replay');
  await expect(page.getByText('REPLAY_START').first()).toBeVisible();
  await expect(page.getByTestId('replay-current')).toContainText(/Aşama 1|M-1|Manuel|isabet/i);
  await page.getByRole('button', { name: '4x' }).click();
  await expect(page.getByText('SCENARIO_HIT').first()).toBeVisible({ timeout: 8_000 });
  await expect(page.getByTestId('mock-strike').first()).toBeVisible();
  await expect(page.locator('.mission-metrics')).toContainText(/Puan (5|15|35|55)/);
});

test('hands-off Aşama 3 friend/range gate blocks strike in replay state', async ({ page }) => {
  await page.goto('/?console=1&handsOff=1&stage=3&t=55&speed=1');
  await expect(page.getByTestId('hands-off-replay')).toContainText('Aşama 3');
  await expect(page.getByTestId('replay-current')).toContainText('Dost hedef ateş kilidi');
  await expect(page.getByText('DOST HEDEF — ATEŞ KİLİTLİ')).toBeVisible();
  await expect(page.getByText('fire_enable').locator('..')).toContainText('blocked');
  await expect(page.getByTestId('mock-strike')).toHaveCount(0);
});

