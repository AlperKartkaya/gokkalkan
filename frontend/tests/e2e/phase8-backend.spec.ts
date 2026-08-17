import { expect, test } from '@playwright/test';

const API = 'http://127.0.0.1:8088';

test.beforeEach(async ({ request }) => {
  await request.post(`${API}/estop/reset`, {
    data: { operatorId: 'PW-PHASE8' },
  });
  await request.post(`${API}/telemetry/reset`);
  await request.post(`${API}/mission/resume`, {
    data: { reason: 'PW-PHASE8-RESET' },
  });
  await request.post(`${API}/stage`, {
    data: { stage: 1, round: 1, reason: 'PW-PHASE8' },
  });
});

test('operator panel follows real backend stage, deadman, stop and maintenance state', async ({ page }) => {
  await page.goto(`/?operator=1&operatorApi=${encodeURIComponent(API)}`);

  await expect(page.getByTestId('operator-track-list')).toContainText('BACKEND ÖNCELİĞİ');
  await expect(page.getByTestId('operator-fire-button')).toBeEnabled();
  await expect(page.getByTestId('operator-manual-aim')).toBeVisible();
  await expect(page.getByTestId('operator-aim-right')).toBeDisabled();

  await page.keyboard.down('Space');
  await expect(page.getByTestId('operator-aim-right')).toBeEnabled();
  await page.keyboard.press('ArrowRight');
  await page.keyboard.up('Space');
  await expect(page.getByTestId('operator-aim-right')).toBeDisabled();
  await expect(
    page.locator('article').filter({ hasText: 'ManualAimCommand · Kabul' }).first(),
  ).toBeVisible();

  await page.getByTestId('operator-stop-button').click();
  await expect(page.getByTestId('operator-stop-overlay')).toContainText('ACİL DURDUR');
  await page.request.post(`${API}/estop/reset`, { data: { operatorId: 'PW-PHASE8' } });
  await page.request.post(`${API}/mission/resume`, { data: { reason: 'PW-PHASE8-RESET' } });
  await expect(page.getByTestId('operator-stop-overlay')).toHaveCount(0);

  await page.getByTestId('operator-maintenance-button').click();
  await expect(page.getByTestId('operator-maintenance-overlay')).toContainText('BAKIM');
  await page.getByTestId('operator-maintenance-finish-button').click();
  await expect(page.getByTestId('operator-stop-overlay')).toHaveCount(0);

  await expect(page.getByLabel('Donanım Sağlık Durumu')).toContainText('Çalışma profili: SIM');
  await expect(page.getByLabel('Donanım Sağlık Durumu')).toContainText('Safety kararı:');
});

test('real backend SSE resynchronizes after authoritative stage and track updates', async ({ page, request }) => {
  await page.goto(`/?operator=1&operatorApi=${encodeURIComponent(API)}`);
  await expect(page.locator('.operator-track-scene .stage1-title')).toHaveText('MANUEL ATIŞ');

  await request.post(`${API}/stage`, {
    data: { stage: 2, round: 1, reason: 'PW-SSE' },
  });
  await request.post(`${API}/tracks/update`, {
    data: {
      source: 'perception',
      tracks: [
        {
          trackId: 'PW-FAR',
          friendFoe: 'Bilinmeyen',
          rangeM: 12,
          bearingDeg: 4,
          confidence: 0.8,
        },
        {
          trackId: 'PW-NEAR',
          friendFoe: 'Bilinmeyen',
          rangeM: 4,
          bearingDeg: -2,
          confidence: 0.7,
        },
      ],
    },
  });

  await expect(page.getByTestId('operator-stage-control')).toContainText('Aşama 2');
  await expect(page.getByTestId('operator-track-list')).toContainText('PW-NEAR');
  await expect(
    page.getByTestId('operator-track-row-PW-NEAR'),
  ).toContainText('BACKEND ÖNCELİĞİ');
});

test('real backend E-Stop remains latched until controlled reset and resume', async ({ page, request }) => {
  await page.goto(`/?operator=1&operatorApi=${encodeURIComponent(API)}`);
  await page.getByLabel('Acil Durdur — Yazılım E-Stop').click();

  await expect(page.getByTestId('operator-stop-overlay')).toContainText('ACİL DURDUR');
  await expect(page.getByTestId('operator-stop-resume-button')).toHaveCount(0);
  await expect(page.getByTestId('operator-fire-button')).toBeDisabled();

  await request.post(`${API}/estop/reset`, {
    data: { operatorId: 'PW-PHASE8' },
  });
  await expect(page.getByTestId('operator-stop-overlay')).toContainText('GÖREV DURAKLATILDI');
  await page.getByTestId('operator-stop-resume-button').click();
  await expect(page.getByTestId('operator-stop-overlay')).toHaveCount(0);
});
