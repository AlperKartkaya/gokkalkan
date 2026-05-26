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
  await expect(page.getByTestId('operator-readiness-dashboard')).toContainText('Finale Hazırlık');
  await expect(page.getByTestId('operator-readiness-dashboard')).toContainText('Gerçek sisteme yakınlık');
  await expect(page.getByTestId('operator-readiness-dashboard')).toContainText('Radar/LiDAR Adapter');
  await expect(page.getByTestId('operator-readiness-dashboard')).toContainText('Canlı Arming / Fiziksel Çıkış');
  await expect(page.getByText(/Puan/)).toHaveCount(0);

  await expect(page.getByRole('button', { name: 'FIRE INTENT KİLİTLİ' })).toBeDisabled();
  await page.getByRole('button', { name: 'Otonom' }).click();
  await expect(page.getByRole('button', { name: 'FIRE INTENT GÖNDER (DRY-RUN)' })).toBeEnabled();
  await page.getByRole('button', { name: 'FIRE INTENT GÖNDER (DRY-RUN)' }).click();
  await expect(page.locator('article').filter({ hasText: 'FireIntent · Kabul' }).first()).toContainText('fiziksel çıkış üretilmedi');
});

test('operator panel sends manual aim only after manual mode and deadman are active', async ({ page }) => {
  const apiBase = 'http://127.0.0.1:5173/manual-aim-api';
  const telemetry = { path: 'telemetry_data/operator-api-dry-run.jsonl', exists: true, recordCount: 1 };
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
  const baseSafety = {
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
  let statePayload = {
    app: 'gokkalkan-operator-api',
    version: 1,
    mode: 'safe',
    stage: 3,
    round: 1,
    dryRun: true,
    liveArmEnabled: false,
    tracks: [track],
    safety: { ...baseSafety, modeOk: false, blockReason: 'BLOCKED_MODE', explanation: 'Safe mod.' },
    commandResults: [],
    events: [],
    physicalOutputEnabled: false,
    telemetry,
  };
  let manualAimPayload: unknown;

  await page.route(`${apiBase}/state`, async (route) => route.fulfill({ contentType: 'application/json', body: JSON.stringify(statePayload) }));
  await page.route(`${apiBase}/readiness`, async (route) => route.fulfill({
    contentType: 'application/json',
    body: JSON.stringify({
      schemaVersion: 1,
      generatedAt: '2026-05-25T20:21:00Z',
      summary: 'Dry-run operatör UI tamam; adaptörler TBD.',
      scoreBasis: 'Bu yüzde resmi yarışma uygunluk skoru değildir; repo içi entegrasyon kontrol listesidir.',
      readinessPercent: 52,
      physicalOutputEnabled: false,
      mode: statePayload.mode,
      dryRun: true,
      items: [
        { id: 'operator_panel_ui', label: 'Operatör Paneli UI', status: 'ready', owner: 'Frontend', evidence: 'ManualAimCommand ve FireIntent yüzeyleri hazır.', nextStep: 'Canlı donanımla kiosk doğrula.', ktrInterface: 'Kullanıcı Arayüzü' },
        { id: 'radar_lidar_adapter', label: 'Radar/LiDAR Adapter', status: 'tbd', owner: 'Sensör', evidence: 'Gerçek sensör protokolü seçilmedi.', nextStep: 'Seçilen sensörün güç/veri arayüzünü doldur.', ktrInterface: 'SensorFrame' },
        { id: 'hardware_adapter', label: 'Hardware Adapter', status: 'partial', owner: 'Backend + Elektronik', evidence: 'Dry-run adapter physicalOutput=false döndürüyor.', nextStep: 'MCU haberleşme protokolünü bağla.', ktrInterface: 'HardwareCommand' },
        { id: 'live_arming', label: 'Canlı Arming / Fiziksel Çıkış', status: 'blocked', owner: 'Safety + Elektronik', evidence: 'Canlı arming kapalı.', nextStep: 'İki aşamalı arming ve interlock doğrulaması gerekir.', ktrInterface: 'ArmingState' },
      ],
      nextCriticalActions: ['Seçilen sensörün güç/veri arayüzünü doldur.'],
    }),
  }));
  await page.route(`${apiBase}/mode`, async (route) => {
    statePayload = { ...statePayload, mode: 'manual', safety: { ...baseSafety } };
    await route.fulfill({
      contentType: 'application/json',
      body: JSON.stringify({
        result: { commandId: 'CMD-00001', kind: 'ModeRequest', accepted: true, completed: true, dryRun: true, safetyBlockReason: 'ALLOWED', message: 'Dry-run komut niyeti backend tarafından kaydedildi; fiziksel çıkış üretilmedi.', physicalOutput: false, createdAt: '2026-05-25T20:20:01Z' },
        safety: baseSafety,
        state: statePayload,
      }),
    });
  });
  await page.route(`${apiBase}/manual-aim`, async (route) => {
    manualAimPayload = route.request().postDataJSON();
    const result = { commandId: 'CMD-00002', kind: 'ManualAimCommand', accepted: true, completed: true, dryRun: true, safetyBlockReason: 'ALLOWED', message: 'Dry-run komut niyeti backend tarafından kaydedildi; fiziksel çıkış üretilmedi.', physicalOutput: false, createdAt: '2026-05-25T20:20:02Z' };
    const hardwareResult = { adapter: 'hardware_mock.dry_run', commandId: 'CMD-00002', kind: 'ManualAimCommand', accepted: true, completed: true, physicalOutput: false, message: 'Dry-run hardware adapter komutu kaydetti; fiziksel çıkış üretilmedi.', createdAt: '2026-05-25T20:20:02Z' };
    statePayload = { ...statePayload, commandResults: [result] };
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify({ result, safety: baseSafety, hardwareResult, state: statePayload }) });
  });

  await page.goto(`/?operator=1&operatorApi=${encodeURIComponent(apiBase)}`);
  const manualControls = page.getByTestId('manual-aim-controls');
  await expect(manualControls).toContainText('Manuel pan/tilt yönlendirme');
  await expect(manualControls.getByRole('button', { name: 'SAĞA 2°' })).toBeDisabled();

  await page.getByRole('button', { name: 'Manuel' }).click();
  await manualControls.getByRole('button', { name: 'DEADMAN PASİF' }).click();
  await expect(manualControls.getByRole('button', { name: 'SAĞA 2°' })).toBeEnabled();
  await manualControls.getByRole('button', { name: 'SAĞA 2°' }).click();

  expect(manualAimPayload).toMatchObject({ kind: 'ManualAimCommand', panDeltaDeg: 2, tiltDeltaDeg: 0, deadmanActive: true, dryRun: true });
  await expect(page.locator('article').filter({ hasText: 'ManualAimCommand · Kabul' }).first()).toContainText('fiziksel çıkış üretilmedi');
  await expect(page.getByTestId('operator-hardware-result')).toContainText('hardware_mock.dry_run');
  await expect(page.getByTestId('operator-hardware-result')).toContainText('physicalOutput=false');
  await expect(page.getByTestId('operator-maintenance-drawer')).toContainText('Mekanik + Elektronik rehberi bekliyor');
});

test('operator panel can be opened directly with query parameter and returns to simulator', async ({ page }) => {
  await page.goto('/?operator=1');

  await expect(page.getByTestId('operator-panel')).toBeVisible();
  await page.getByRole('button', { name: 'Simülatöre dön' }).click();
  await expect(page.getByTestId('tutorial-overlay')).toBeVisible();
  await expect(page.getByTestId('parkour-hero')).toBeVisible();
});

test('operator panel readiness dashboard reads backend final-phase gap report', async ({ page }) => {
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

  const dashboard = page.getByTestId('operator-readiness-dashboard');
  await expect(dashboard).toContainText('Gerçek sisteme yakınlık: %43');
  await expect(dashboard).toContainText('resmi yarışma uygunluk skoru değildir');
  await expect(dashboard).toContainText('Radar/LiDAR Adapter');
  await expect(dashboard).toContainText('TBD');
  await expect(dashboard).toContainText('Canlı Arming / Fiziksel Çıkış');
  await expect(dashboard).toContainText('Kilitli');
  await expect(dashboard).toContainText('Sıradaki kritik adım');
  await expect(dashboard).toContainText('Seçilen sensörün güç/veri arayüzünü doldur.');
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
  await page.getByText('Kanıt / Replay').click();
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
  await page.getByText('Kanıt / Replay').click();
  await page.getByRole('button', { name: 'Kanıtı Yenile' }).click();

  await expect(page.getByText('Operator API 503: Service Unavailable')).toBeVisible();
  await expect(page.getByText('Kanıt paketi güncellendi; replay yalnız kayıt okur.')).toHaveCount(0);
});
