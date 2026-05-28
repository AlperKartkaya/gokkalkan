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
  await expect(page.getByRole('heading', { name: 'Emniyet' })).toBeVisible();
  await expect(page.getByTestId('operator-readiness-dashboard')).toHaveCount(0);
  await expect(page.getByText('Sistem Durumu')).toHaveCount(0);
  await expect(page.getByText('Beklenen mod')).toHaveCount(0);
  await expect(page.getByText('Kural')).toHaveCount(0);
  await expect(page.getByText('Manuel pan/tilt yönlendirme')).toHaveCount(0);
  await expect(page.getByTestId('manual-aim-controls')).toHaveCount(0);
  await expect(page.getByText('Seçili hedef')).toHaveCount(0);
  await expect(page.getByText('Safety açıklaması')).toHaveCount(0);
  await expect(page.getByText('Seçili iz ayrıntısı')).toHaveCount(0);
  await expect(page.getByText(/Aşama \d · Tur/)).toHaveCount(0);
  await expect(page.getByText(/^Backend:/)).toHaveCount(0);
  await expect(page.getByText(/^Perception:/)).toHaveCount(0);
  await expect(page.getByText(/^Radar\/LiDAR:/)).toHaveCount(0);
  await expect(page.getByText(/^Safety Gate:/)).toHaveCount(0);
  await expect(page.getByText(/^API:/)).toHaveCount(0);
  await expect(page.getByTestId('operator-track-scene')).toBeVisible();
  await expect(page.getByTestId('operator-steel-dome')).toBeVisible();
  await expect(page.getByTestId('operator-aim-line')).toBeVisible();
  await expect(page.locator('.operator-track-scene .target-silhouette')).toHaveCount(2);
  await expect(page.locator('.operator-track-scene .target-unknown-sphere')).toHaveCount(1);
  await expect(page.locator('.operator-track-scene .target-label-stack')).toHaveCount(0);
  await expect(page.getByTestId('operator-sensor-3d-canvas')).toBeVisible();
  await expect(page.getByTestId('operator-confidence-panel')).toContainText('DOĞRULUK');
  await expect(page.getByTestId('operator-confidence-panel')).not.toContainText('Güven');
  await expect(page.getByTestId('operator-confidence-DRY-RUN-UAV-03')).toHaveAttribute('data-identification', 'unknown');
  await expect(page.getByText('İzler')).toHaveCount(0);
  await expect(page.getByText('Sonuç')).toHaveCount(0);
  await expect(page.getByTestId('operator-hardware-result')).toHaveCount(0);
  await expect(page.getByText(/Puan/)).toHaveCount(0);

  await expect(page.getByTestId('operator-fire-button')).toBeEnabled();
  await expect(page.getByTestId('operator-stop-button')).toBeVisible();
  await expect(page.getByTestId('operator-maintenance-button')).toBeVisible();
  await page.getByTestId('operator-fire-button').click();
  await expect(page.getByTestId('operator-shot-trace')).toBeVisible();
  await expect(page.locator('article').filter({ hasText: 'FireIntent · Kabul' }).first()).toContainText('fiziksel çıkış üretilmedi');
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
});

test('operator panel final-phase layout renders dominant 3D fusion and compact mission side rail', async ({ page }) => {
  const apiBase = 'http://127.0.0.1:5173/final-phase-api';
  const telemetry = { path: 'telemetry_data/operator-api-dry-run.jsonl', exists: true, recordCount: 1 };
  const safety = {
    estop: false,
    motionZoneOk: true,
    fireZoneOk: true,
    targetGateOk: true,
    modeOk: true,
    backendConnected: true,
    perceptionConnected: false,
    sensorAdapterConnected: false,
    dryRun: true,
    liveArmEnabled: false,
    blockReason: 'ALLOWED',
    explanation: 'Dry-run güvenli.',
  };
  const stageTracks = {
    1: [
      { trackId: 'S1-ORDER-FUZE-01', stage: 1, round: 1, targetType: 'Balistik Füze', friendFoe: 'Düşman', rangeM: 15, bearingDeg: -24, confidence: 0.86, source: 'dry-run', updatedAt: '2026-05-25T20:20:00Z' },
    ],
    3: [
      { trackId: 'DRY-RUN-F16-01', stage: 3, round: 1, targetType: 'F16', friendFoe: 'Düşman', rangeM: 12.4, bearingDeg: -18, confidence: 0.96, source: 'fused', updatedAt: '2026-05-25T20:20:00Z' },
      { trackId: 'DRY-RUN-HEL-02', stage: 3, round: 1, targetType: 'Helikopter', friendFoe: 'Dost', rangeM: 8.1, bearingDeg: 4, confidence: 0.91, source: 'fused', updatedAt: '2026-05-25T20:20:00Z' },
      { trackId: 'DRY-RUN-UAV-03', stage: 3, round: 1, targetType: 'Mini/Micro İHA', friendFoe: 'Bilinmeyen', rangeM: 4.2, bearingDeg: 23, confidence: 0.42, source: 'radar-lidar', updatedAt: '2026-05-25T20:20:00Z' },
    ],
  } as const;
  const sensorFrames = [
    {
      frameId: 'SENS-3-1-F16-FUSION',
      stage: 3,
      round: 1,
      trackId: 'DRY-RUN-F16-01',
      sensor: 'fusion',
      timestamp: '2026-05-25T20:20:00Z',
      rangeM: 12.4,
      bearingDeg: -18,
      elevationDeg: 0.5,
      radialVelocityMps: -4.6,
      rcsDbsm: 12.4,
      snrDb: 22.1,
      pointCount: 118,
      quality: 0.96,
      targetType: 'F16',
      friendFoe: 'Düşman',
      classificationConfidence: 0.96,
      rangeGate: 'Uygun',
      recommendation: 'Aşama 3: düşman ve menzil uygun; Safety Gate beklenir.',
      sourceDataset: 'Gökkalkan recorded-style radar/LiDAR replay fixture.',
      replayOnly: true,
      rawSampleRef: 'fixture/fusion/f16',
    },
    {
      frameId: 'SENS-3-1-HEL-FUSION',
      stage: 3,
      round: 1,
      trackId: 'DRY-RUN-HEL-02',
      sensor: 'fusion',
      timestamp: '2026-05-25T20:20:00Z',
      rangeM: 8.1,
      bearingDeg: 4,
      elevationDeg: 0.3,
      radialVelocityMps: -2.1,
      rcsDbsm: 5,
      snrDb: 18.2,
      pointCount: 160,
      quality: 0.91,
      targetType: 'Helikopter',
      friendFoe: 'Dost',
      classificationConfidence: 0.91,
      rangeGate: 'Kilitli',
      recommendation: 'Dost unsur korunur; FireIntent kilitli.',
      sourceDataset: 'Gökkalkan recorded-style radar/LiDAR replay fixture.',
      replayOnly: true,
      rawSampleRef: 'fixture/fusion/hel',
    },
    {
      frameId: 'SENS-3-1-UAV-FUSION',
      stage: 3,
      round: 1,
      trackId: 'DRY-RUN-UAV-03',
      sensor: 'fusion',
      timestamp: '2026-05-25T20:20:00Z',
      rangeM: 4.2,
      bearingDeg: 23,
      elevationDeg: 0.7,
      radialVelocityMps: -1.2,
      rcsDbsm: 2.2,
      snrDb: 15.5,
      pointCount: 84,
      quality: 0.58,
      targetType: 'Mini/Micro İHA',
      friendFoe: 'Bilinmeyen',
      classificationConfidence: 0.42,
      rangeGate: 'Kimlik bekleniyor',
      recommendation: 'Kimlik kesinleşmeden FireIntent kilitli.',
      sourceDataset: 'Gökkalkan recorded-style radar/LiDAR replay fixture.',
      replayOnly: true,
      rawSampleRef: 'fixture/fusion/uav-unknown',
    },
  ];
  let statePayload = {
    app: 'gokkalkan-operator-api',
    version: 1,
    mode: 'manual',
    stage: 1,
    round: 1,
    dryRun: true,
    liveArmEnabled: false,
    tracks: [...stageTracks[1]],
    sensorFrames: [],
    sensorHealth: {
      schemaVersion: 1,
      status: 'replay',
      adapterConnected: false,
      perceptionConnected: false,
      replayOnly: true,
      sourceDataset: 'Gökkalkan recorded-style dry-run fixture.',
      latestFrameAt: '2026-05-25T20:20:00Z',
      frameCount: 0,
      physicalOutputEnabled: false,
    },
    safety,
    commandResults: [],
    events: [],
    physicalOutputEnabled: false,
    telemetry,
  };

  await page.route(`${apiBase}/state`, async (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(statePayload) }));
  await page.route(`${apiBase}/readiness`, async (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      schemaVersion: 1,
      generatedAt: '2026-05-25T20:21:00Z',
      summary: 'Operatör UI hazır; canlı sensör/donanım entegrasyonu bekliyor.',
      scoreBasis: 'Bu yüzde resmi yarışma uygunluk skoru değildir; repo içi entegrasyon kontrol listesidir.',
      readinessPercent: 55,
      physicalOutputEnabled: false,
      mode: statePayload.mode,
      dryRun: true,
      items: [
        { id: 'operator_panel_ui', label: 'Operatör Paneli UI', status: 'ready', owner: 'Frontend', evidence: 'Aşama/tur ve sensor replay yüzeyleri hazır.', nextStep: 'Canlı kiosk doğrula.', ktrInterface: 'StageRequest, SensorFrame' },
        { id: 'radar_lidar_adapter', label: 'Radar/LiDAR Adapter', status: 'tbd', owner: 'Sensör', evidence: 'SensorFrame replay var; gerçek protokol seçilmedi.', nextStep: 'Seçilen sensörün güç/veri arayüzünü doldur.', ktrInterface: 'SensorFrame' },
        { id: 'live_arming', label: 'Canlı Arming / Fiziksel Çıkış', status: 'blocked', owner: 'Safety + Elektronik', evidence: 'Canlı arming kapalı.', nextStep: 'Interlock doğrula.', ktrInterface: 'ArmingState' },
      ],
      nextCriticalActions: ['Seçilen sensörün güç/veri arayüzünü doldur.'],
    }),
  }));
  await page.route(`${apiBase}/stage`, async (route) => {
    const payload = route.request().postDataJSON();
    statePayload = {
      ...statePayload,
      mode: payload.stage === 1 ? 'manual' : 'autonomous',
      stage: payload.stage,
      round: payload.round,
      tracks: payload.stage === 3 ? [...stageTracks[3]] : [...stageTracks[1]],
      sensorFrames: payload.stage === 3 ? sensorFrames : [],
      sensorHealth: {
        ...statePayload.sensorHealth,
        frameCount: payload.stage === 3 ? sensorFrames.length : 0,
        sourceDataset: payload.stage === 3 ? 'Gökkalkan recorded-style radar/LiDAR replay fixture.' : 'Gökkalkan recorded-style dry-run fixture.',
      },
    };
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        result: { commandId: 'CMD-STAGE-3', kind: 'StageRequest', accepted: true, completed: true, dryRun: true, safetyBlockReason: 'ALLOWED', message: 'Dry-run komut niyeti backend tarafından kaydedildi; fiziksel çıkış üretilmedi.', physicalOutput: false, createdAt: '2026-05-25T20:20:01Z' },
        safety,
        state: statePayload,
      }),
    });
  });

  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto(`/?operator=1&operatorApi=${encodeURIComponent(apiBase)}`);
  const stageControl = page.getByTestId('operator-stage-control');
  await expect(stageControl).toContainText('Aşama 1');
  await expect(stageControl).not.toContainText('Beklenen mod');
  await expect(stageControl).not.toContainText('Kural');
  const sensorPanel = page.getByTestId('operator-sensor-fusion-panel');
  await expect(sensorPanel).toContainText('0 frame');
  await expect(sensorPanel).toContainText('SensorFrame yok');
  const sensorTopBefore = await sensorPanel.evaluate((element) => Math.round(element.getBoundingClientRect().top + window.scrollY));
  await page.getByRole('button', { name: 'Aşama 3' }).click();

  await expect(stageControl).toContainText('Tur 8');
  const roundBoxes = await stageControl.locator('.operator-round-grid button').evaluateAll((buttons) => buttons.map((button) => Math.round(button.getBoundingClientRect().top)));
  expect(new Set(roundBoxes).size).toBe(1);
  await expect(sensorPanel).toContainText('replayOnly=true');
  await expect(sensorPanel.getByText('Menzil · Açı · Sınıf')).toHaveCount(0);
  await expect(sensorPanel.getByText('F16')).toHaveCount(0);
  await expect(sensorPanel.getByText('Düşman')).toHaveCount(0);
  await expect(page.getByTestId('operator-confidence-panel')).toContainText('DOĞRULUK');
  await expect(page.getByTestId('operator-accuracy-DRY-RUN-F16-01-color')).toContainText('96%');
  await expect(page.getByTestId('operator-accuracy-DRY-RUN-UAV-03-type')).toContainText('42%');
  await expect(page.getByTestId('operator-confidence-DRY-RUN-UAV-03')).toHaveAttribute('data-identification', 'unknown');
  await expect(page.getByText('İzler')).toHaveCount(0);
  await expect(page.locator('.operator-track-scene .target-label-stack')).toHaveCount(0);
  await expect(page.locator('.operator-track-scene .target-silhouette')).toHaveCount(2);
  await expect(page.locator('.operator-track-scene .target-unknown-sphere')).toHaveCount(1);
  await expect(page.getByTestId('operator-steel-dome')).toHaveAttribute('data-rotation', /-?\d+\.\d/);
  const trackSceneBox = await page.getByTestId('operator-track-scene').boundingBox();
  const operatorDomeBox = await page.getByTestId('operator-steel-dome').boundingBox();
  const sensorPanelBox = await sensorPanel.boundingBox();
  expect(trackSceneBox).not.toBeNull();
  expect(operatorDomeBox).not.toBeNull();
  expect(sensorPanelBox).not.toBeNull();
  expect((sensorPanelBox?.width ?? 0)).toBeGreaterThan((trackSceneBox?.width ?? Number.MAX_SAFE_INTEGER) * 1.35);
  expect((sensorPanelBox?.height ?? 0)).toBeGreaterThan(520);
  expect((trackSceneBox ? trackSceneBox.x + trackSceneBox.width : 0) - (operatorDomeBox ? operatorDomeBox.x + operatorDomeBox.width : 0)).toBeLessThanOrEqual(12);

  const sensor3dView = page.getByTestId('operator-sensor-3d-view');
  await expect(sensor3dView).toBeVisible();
  await expect(sensor3dView).toHaveAttribute('data-renderer', 'webgl');
  await expect(sensor3dView).toContainText('Sürükle');
  await expect(sensor3dView).toContainText('Tekerlek');
  const f16Box = await page.getByTestId('operator-sensor-3d-target-DRY-RUN-F16-01').boundingBox();
  expect(f16Box).not.toBeNull();
  await expect(page.getByTestId('operator-sensor-3d-dome')).toHaveCount(0);
  await expect(page.getByTestId('operator-sensor-3d-target-DRY-RUN-UAV-03')).toHaveAttribute('data-identification', 'unknown');
  await expect(page.getByTestId('operator-sensor-3d-target-DRY-RUN-HEL-02')).toHaveAttribute('data-affiliation', 'Dost');

  const viewBox = await sensor3dView.boundingBox();
  expect(viewBox).not.toBeNull();
  const zoomBefore = await sensor3dView.getAttribute('data-zoom');
  await sensor3dView.dispatchEvent('wheel', { deltaY: -240, bubbles: true, cancelable: true });
  await expect.poll(() => sensor3dView.getAttribute('data-zoom')).not.toBe(zoomBefore);
  const zoomAfter = Number(await sensor3dView.getAttribute('data-zoom'));
  expect(Math.abs(zoomAfter - Number(zoomBefore))).toBeLessThanOrEqual(0.06);
  await page.getByTestId('operator-sensor-3d-reset').click();
  await expect(sensor3dView).toHaveAttribute('data-zoom', '1.00');

  const rotateBefore = await sensor3dView.getAttribute('data-rotate-z');
  await page.mouse.move((viewBox?.x ?? 0) + 24, (viewBox?.y ?? 0) + (viewBox?.height ?? 0) - 38);
  await page.mouse.down();
  await page.mouse.move((viewBox?.x ?? 0) + (viewBox?.width ?? 0) - 24, (viewBox?.y ?? 0) + (viewBox?.height ?? 0) - 64, { steps: 6 });
  await page.mouse.up();
  const rotateAfter = await sensor3dView.getAttribute('data-rotate-z');
  expect(rotateAfter).not.toBe(rotateBefore);
  expect(Math.abs(Number(rotateAfter) - Number(rotateBefore))).toBeGreaterThan(180);

  const sensorTopAfterStage = await sensorPanel.evaluate((element) => Math.round(element.getBoundingClientRect().top + window.scrollY));
  expect(Math.abs(sensorTopAfterStage - sensorTopBefore)).toBeLessThanOrEqual(1);
  const helTrack = page.getByTestId('operator-track-DRY-RUN-HEL-02');
  const helTrackBoxBefore = await helTrack.boundingBox();
  const helTrackColorBefore = await helTrack.evaluate((element) => getComputedStyle(element).color);
  await helTrack.click();
  const helTrackBoxAfter = await helTrack.boundingBox();
  const helTrackColorAfter = await helTrack.evaluate((element) => getComputedStyle(element).color);
  expect(helTrackBoxAfter).not.toBeNull();
  expect(helTrackBoxBefore).not.toBeNull();
  expect(Math.abs((helTrackBoxAfter?.x ?? 0) - (helTrackBoxBefore?.x ?? 0))).toBeLessThanOrEqual(1);
  expect(Math.abs((helTrackBoxAfter?.y ?? 0) - (helTrackBoxBefore?.y ?? 0))).toBeLessThanOrEqual(1);
  expect(helTrackColorAfter).toBe(helTrackColorBefore);
  const sensorTopAfterTrackSelect = await sensorPanel.evaluate((element) => Math.round(element.getBoundingClientRect().top + window.scrollY));
  expect(Math.abs(sensorTopAfterTrackSelect - sensorTopBefore)).toBeLessThanOrEqual(1);
  const actionBox = await page.getByTestId('operator-action-strip').boundingBox();
  const trackBoxAfter = await page.getByTestId('operator-track-scene').boundingBox();
  expect(actionBox).not.toBeNull();
  expect(trackBoxAfter).not.toBeNull();
  expect((actionBox?.y ?? 0)).toBeGreaterThanOrEqual((trackBoxAfter?.y ?? 0) + (trackBoxAfter?.height ?? 0) - 2);
  await expect(page.getByTestId('operator-hardware-result')).toHaveCount(0);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth)).toBe(true);
  await expect(page.getByText(/physicalOutput=true/)).toHaveCount(0);
});

test('operator panel uses fire, stop, and bakım actions without manual pan tilt controls', async ({ page }) => {
  await page.goto('/?operator=1');

  await expect(page.getByTestId('manual-aim-controls')).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Manuel' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Otonom' })).toHaveCount(0);
  await expect(page.getByTestId('operator-fire-button')).toBeEnabled();
  await page.getByTestId('operator-fire-button').click();
  await expect(page.getByTestId('operator-shot-trace')).toBeVisible();
  await expect(page.getByTestId('operator-hardware-result')).toHaveCount(0);
  await expect(page.getByText('Sonuç')).toHaveCount(0);

  await page.getByTestId('operator-stop-button').click();
  await expect(page.getByTestId('operator-stop-button')).toContainText('STOP');
  await expect(page.getByTestId('operator-fire-button')).toBeDisabled();
  await expect(page.getByTestId('operator-safety-state')).toContainText('AKTİF');

  await page.getByTestId('operator-maintenance-button').click();
  await expect(page.getByTestId('operator-maintenance-drawer')).toBeVisible();
  await expect(page.getByTestId('operator-lidar-diagnostics')).toContainText('SDK/driver → SensorFrame → Backend');
});

test('operator panel keeps unknown targets white/spherical and fire-locked until identified', async ({ page }) => {
  await page.goto('/?operator=1');

  const unknownTrack = page.getByTestId('operator-track-DRY-RUN-UAV-03');
  await expect(unknownTrack).toHaveAttribute('data-identification', 'unknown');
  await expect(unknownTrack).toHaveAttribute('data-affiliation', 'Bilinmeyen');
  await expect(page.getByTestId('operator-sensor-3d-target-DRY-RUN-UAV-03')).toHaveAttribute('data-identification', 'unknown');
  await expect(page.getByTestId('operator-confidence-DRY-RUN-UAV-03')).toContainText('Tip');
  await expect(page.getByTestId('operator-confidence-DRY-RUN-UAV-03')).toContainText('42%');

  await unknownTrack.click();
  await expect(page.getByTestId('operator-fire-button')).toBeDisabled();
  await expect(page.getByTestId('fire-cluster')).toContainText('Hedef, dost/düşman veya menzil kapısı uygun değil.');
});

test('operator panel can be opened directly with query parameter and returns to simulator', async ({ page }) => {
  await page.goto('/?operator=1');

  await expect(page.getByTestId('operator-panel')).toBeVisible();
  await page.getByRole('button', { name: 'Simülatöre dön' }).click();
  await expect(page.getByTestId('tutorial-overlay')).toBeVisible();
  await expect(page.getByTestId('parkour-hero')).toBeVisible();
});

test('desktop operator shell keeps LiDAR vendor tools diagnostic-only', async ({ page }) => {
  await page.goto('/?operator=1&desktop=1');

  await expect(page.getByTestId('operator-panel')).toBeVisible();
  await expect(page.getByTestId('operator-panel')).toHaveAttribute('data-desktop-shell', 'true');
  await expect(page.getByText('Kabuk: Desktop')).toHaveCount(0);
  await expect(page.getByTestId('operator-sensor-fusion-panel')).toContainText('Radar / LiDAR');
  await expect(page.getByTestId('operator-sensor-fusion-panel')).toContainText('SensorFrame');

  await page.getByTestId('operator-maintenance-drawer').locator('summary').click();
  const lidarDiagnostics = page.getByTestId('operator-lidar-diagnostics');
  await expect(lidarDiagnostics).toContainText('LiDAR viewer');
  await expect(lidarDiagnostics).toContainText('Dış diagnostic / görev UI değil');
  await expect(lidarDiagnostics).toContainText('RPLIDAR / Livox');
  await expect(lidarDiagnostics).toContainText('SDK/driver → SensorFrame → Backend');
  await expect(page.getByText('RPLIDAR Viewer').or(page.getByText('Livox Viewer'))).toHaveCount(0);
});

test('operator panel keeps backend readiness diagnostic-only outside the operator view', async ({ page }) => {
  const apiBase = 'http://127.0.0.1:5173/readiness-api';
  await page.route(`${apiBase}/state`, async (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      app: 'gokkalkan-operator-api',
      version: 1,
      mode: 'safe',
      stage: 3,
      round: 1,
      dryRun: true,
      liveArmEnabled: false,
      tracks: [],
      safety: {
        estop: false,
        motionZoneOk: true,
        fireZoneOk: true,
        targetGateOk: false,
        modeOk: false,
        backendConnected: true,
        perceptionConnected: false,
        sensorAdapterConnected: false,
        dryRun: true,
        liveArmEnabled: false,
        blockReason: 'BLOCKED_MODE',
        explanation: 'Safe mod.',
      },
      commandResults: [],
      events: [],
      physicalOutputEnabled: false,
      telemetry: { path: 'telemetry_data/operator-api-dry-run.jsonl', exists: true, recordCount: 1 },
    }),
  }));
  await page.route(`${apiBase}/readiness`, async (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      schemaVersion: 1,
      generatedAt: '2026-05-25T20:30:00Z',
      summary: 'Dry-run zinciri çalışıyor; final fazı için sensör ve MCU bağlantıları bekliyor.',
      scoreBasis: 'Bu yüzde resmi yarışma uygunluk skoru değildir; repo içi entegrasyon kontrol listesidir.',
      readinessPercent: 43,
      physicalOutputEnabled: false,
      mode: 'safe',
      dryRun: true,
      items: [
        { id: 'backend_api', label: 'Backend Operatör API', status: 'ready', owner: 'Backend', evidence: 'State ve command endpointleri çalışıyor.', nextStep: 'Oturum/imza katmanı ekle.', ktrInterface: 'ModeRequest' },
        { id: 'radar_lidar_adapter', label: 'Radar/LiDAR Adapter', status: 'tbd', owner: 'Sensör', evidence: 'Gerçek sensör protokolü seçilmedi.', nextStep: 'Seçilen sensörün güç/veri arayüzünü doldur.', ktrInterface: 'SensorFrame' },
        { id: 'hardware_adapter', label: 'Hardware Adapter', status: 'partial', owner: 'Backend + Elektronik', evidence: 'Dry-run adapter physicalOutput=false döndürüyor.', nextStep: 'MCU haberleşme protokolünü bağla.', ktrInterface: 'HardwareCommand' },
        { id: 'live_arming', label: 'Canlı Arming / Fiziksel Çıkış', status: 'blocked', owner: 'Safety + Elektronik', evidence: 'Canlı arming kapalı.', nextStep: 'İki aşamalı arming ve interlock doğrulaması gerekir.', ktrInterface: 'ArmingState' },
      ],
      nextCriticalActions: ['Seçilen sensörün güç/veri arayüzünü doldur.', 'MCU haberleşme protokolünü bağla.'],
    }),
  }));

  await page.goto(`/?operator=1&operatorApi=${encodeURIComponent(apiBase)}`);

  await expect(page.getByTestId('operator-readiness-dashboard')).toHaveCount(0);
  await expect(page.getByText('Sistem Durumu')).toHaveCount(0);
  await expect(page.getByText('Hazırlık %43')).toHaveCount(0);
  await expect(page.getByText('Sonraki iş')).toHaveCount(0);
  await expect(page.getByText('Seçilen sensörün güç/veri arayüzünü doldur.')).toBeHidden();
  await expect(page.getByTestId('operator-track-scene')).toBeVisible();
  await expect(page.getByTestId('operator-sensor-fusion-panel')).toBeVisible();
  await expect(page.getByText('tamamen hazır')).toHaveCount(0);
});

test('operator panel evidence drawer reads backend telemetry export and replay safely', async ({ page }) => {
  const apiBase = 'http://127.0.0.1:5173/operator-api';
  const telemetry = { path: 'telemetry_data/operator-api-dry-run.jsonl', exists: true, recordCount: 6 };
  const track = {
    trackId: 'DRY-RUN-F16-01',
    stage: 3,
    round: 1,
    targetType: 'F16',
    friendFoe: 'Düşman',
    rangeM: 12.4,
    bearingDeg: -18,
    confidence: 0.96,
    source: 'dry-run',
    updatedAt: '2026-05-25T20:20:00Z',
  };
  const safety = {
    estop: false,
    motionZoneOk: true,
    fireZoneOk: true,
    targetGateOk: true,
    modeOk: true,
    backendConnected: true,
    perceptionConnected: false,
    sensorAdapterConnected: false,
    dryRun: true,
    liveArmEnabled: false,
    blockReason: 'ALLOWED',
    explanation: 'Dry-run güvenli.',
  };
  const commandResult = {
    commandId: 'CMD-00002',
    kind: 'FireIntent',
    accepted: true,
    completed: true,
    dryRun: true,
    safetyBlockReason: 'ALLOWED',
    message: 'Dry-run komut niyeti backend tarafından kaydedildi; fiziksel çıkış üretilmedi.',
    physicalOutput: false,
    createdAt: '2026-05-25T20:20:00Z',
  };
  let statePayload = {
    app: 'gokkalkan-operator-api',
    version: 1,
    mode: 'autonomous',
    stage: 3,
    round: 1,
    dryRun: true,
    liveArmEnabled: false,
    tracks: [track],
    safety,
    commandResults: [commandResult],
    events: [],
    physicalOutputEnabled: false,
    telemetry,
  };
  const entries = [
    { recordId: 1, timestamp: '2026-05-25T20:20:00Z', recordType: 'event', payload: { decision: 'BOOT', physicalOutput: false } },
    { recordId: 2, timestamp: '2026-05-25T20:20:01Z', recordType: 'command_result', payload: commandResult },
    { recordId: 3, timestamp: '2026-05-25T20:20:02Z', recordType: 'hardware_result', payload: { commandId: 'CMD-00002', physicalOutput: false } },
  ];
  let exportPayload = {
    schemaVersion: 1,
    generatedAt: '2026-05-25T20:21:00Z',
    physicalOutputEnabled: false,
    telemetry,
    state: statePayload,
    events: [],
    commandResults: [commandResult],
    entries,
  };
  let replayPayload = {
    schemaVersion: 1,
    generatedAt: '2026-05-25T20:21:00Z',
    sourceLogPath: telemetry.path,
    physicalOutputEnabled: false,
    replayOnly: true,
    entries,
    events: [{ decision: 'BOOT', physicalOutput: false }],
    commandResults: [commandResult],
    hardwareResults: [{ commandId: 'CMD-00002', physicalOutput: false }],
  };

  await page.route(`${apiBase}/state`, async (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(statePayload) }));
  await page.route(`${apiBase}/readiness`, async (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      schemaVersion: 1,
      generatedAt: '2026-05-25T20:21:00Z',
      summary: 'Dry-run operatör zinciri çalışıyor; final adaptörleri bekliyor.',
      scoreBasis: 'Bu yüzde resmi yarışma uygunluk skoru değildir; repo içi entegrasyon kontrol listesidir.',
      readinessPercent: 44,
      physicalOutputEnabled: false,
      mode: 'autonomous',
      dryRun: true,
      items: [
        { id: 'backend_api', label: 'Backend Operatör API', status: 'ready', owner: 'Backend', evidence: 'API yanıt veriyor.', nextStep: 'Oturum katmanı ekle.', ktrInterface: 'ModeRequest' },
        { id: 'live_arming', label: 'Canlı Arming / Fiziksel Çıkış', status: 'blocked', owner: 'Safety + Elektronik', evidence: 'Canlı arming kapalı.', nextStep: 'Interlock doğrula.', ktrInterface: 'ArmingState' },
      ],
      nextCriticalActions: ['Interlock doğrula.'],
    }),
  }));
  await page.route(`${apiBase}/telemetry/export`, async (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(exportPayload) }));
  await page.route(`${apiBase}/replay`, async (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(replayPayload) }));
  await page.route(`${apiBase}/telemetry/reset`, async (route) => {
    const resetTelemetry = { ...telemetry, recordCount: 1 };
    statePayload = { ...statePayload, mode: 'safe', commandResults: [], telemetry: resetTelemetry };
    exportPayload = { ...exportPayload, telemetry: resetTelemetry, state: statePayload, commandResults: [], entries: [{ recordId: 1, timestamp: '2026-05-25T20:22:00Z', recordType: 'event', payload: { decision: 'RESET', physicalOutput: false } }] };
    replayPayload = { ...replayPayload, entries: exportPayload.entries, events: [{ decision: 'RESET', physicalOutput: false }], commandResults: [], hardwareResults: [] };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ ok: true, physicalOutputEnabled: false, telemetry: resetTelemetry, state: statePayload }) });
  });

  await page.goto(`/?operator=1&operatorApi=${encodeURIComponent(apiBase)}`);
  await expect(page.getByTestId('operator-panel')).toBeVisible();
  await page.getByTestId('operator-evidence-drawer').locator('summary').click();
  await expect(page.getByText('JSONL kayıt yolu')).toBeVisible();
  await page.getByRole('button', { name: 'Kanıtı Yenile' }).click();
  await expect(page.getByText('Kanıt paketi güncellendi; replay yalnız kayıt okur.')).toBeVisible();
  await expect(page.getByText('telemetry_data/operator-api-dry-run.jsonl')).toBeVisible();
  await expect(page.getByText('1 olay · 1 komut · 1 dry-run hardware sonucu')).toBeVisible();
  await expect(page.getByText('KAPALI / YOK')).toBeVisible();
  await expect(page.getByText('hardware_result')).toBeVisible();

  await page.getByRole('button', { name: 'Telemetriyi Sıfırla' }).click();
  await expect(page.getByText('Telemetri sıfırlandı; safe moda dönüldü ve fiziksel çıkış üretilmedi.')).toBeVisible();
  await expect(page.getByText('1 olay · 0 komut · 0 dry-run hardware sonucu')).toBeVisible();
  await expect(page.getByText('RESET')).toBeVisible();
});

test('operator panel evidence drawer surfaces backend telemetry failures without false success', async ({ page }) => {
  const apiBase = 'http://127.0.0.1:5173/bad-operator-api';
  await page.route(`${apiBase}/state`, async (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      app: 'gokkalkan-operator-api',
      version: 1,
      mode: 'safe',
      stage: 3,
      round: 1,
      dryRun: true,
      liveArmEnabled: false,
      tracks: [],
      safety: {
        estop: false,
        motionZoneOk: true,
        fireZoneOk: true,
        targetGateOk: false,
        modeOk: false,
        backendConnected: true,
        perceptionConnected: false,
        sensorAdapterConnected: false,
        dryRun: true,
        liveArmEnabled: false,
        blockReason: 'BLOCKED_MODE',
        explanation: 'Safe mod.',
      },
      commandResults: [],
      events: [],
      physicalOutputEnabled: false,
      telemetry: { path: 'telemetry_data/operator-api-dry-run.jsonl', exists: true, recordCount: 1 },
    }),
  }));
  await page.route(`${apiBase}/telemetry/export`, async (route) => route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ error: 'telemetry unavailable' }) }));
  await page.route(`${apiBase}/replay`, async (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify({ schemaVersion: 1, replayOnly: true, entries: [], events: [], commandResults: [], hardwareResults: [], physicalOutputEnabled: false }) }));

  await page.goto(`/?operator=1&operatorApi=${encodeURIComponent(apiBase)}`);
  await expect(page.getByTestId('operator-panel')).toBeVisible();
  await page.getByTestId('operator-evidence-drawer').locator('summary').click();
  await page.getByRole('button', { name: 'Kanıtı Yenile' }).click();

  await expect(page.getByText('Operator API 503: Service Unavailable')).toBeVisible();
  await expect(page.getByText('Kanıt paketi güncellendi; replay yalnız kayıt okur.')).toHaveCount(0);
});
