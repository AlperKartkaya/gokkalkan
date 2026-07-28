import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  fetchOperatorReplay,
  fetchOperatorReadiness,
  fetchOperatorSensorFrames,
  fetchOperatorSnapshot,
  fetchOperatorTelemetryExport,
  normalizeOperatorApiBaseUrl,
  operatorStateStreamUrl,
  resetOperatorTelemetry,
  sendOperatorFireIntent,
  sendOperatorManualAimCommand,
  sendOperatorModeRequest,
  sendOperatorStageRequest,
} from './operatorApiClient';

const originalFetch = globalThis.fetch;

function mockFetch(payload: unknown, ok = true) {
  globalThis.fetch = vi.fn(async () => ({
    ok,
    status: ok ? 200 : 503,
    statusText: ok ? 'OK' : 'Service Unavailable',
    json: async () => payload,
  })) as unknown as typeof fetch;
}

afterEach(() => {
  globalThis.fetch = originalFetch;
  vi.restoreAllMocks();
});

describe('operator API client', () => {
  it('normalizes trailing slashes from API base URLs', () => {
    expect(normalizeOperatorApiBaseUrl(' http://127.0.0.1:8088/// ')).toBe('http://127.0.0.1:8088');
    expect(operatorStateStreamUrl('http://127.0.0.1:8088/', 12.9)).toBe('http://127.0.0.1:8088/state/stream?after=12');
  });

  it('fetches the backend state snapshot', async () => {
    mockFetch({ app: 'gokkalkan-operator-api', dryRun: true, physicalOutputEnabled: false });

    const snapshot = await fetchOperatorSnapshot('http://127.0.0.1:8088/');

    expect(snapshot).toMatchObject({ app: 'gokkalkan-operator-api', dryRun: true, physicalOutputEnabled: false });
    expect(globalThis.fetch).toHaveBeenCalledWith('http://127.0.0.1:8088/state', expect.objectContaining({ method: 'GET' }));
  });

  it('fetches the backend readiness report without treating it as official compliance', async () => {
    mockFetch({
      schemaVersion: 1,
      readinessPercent: 42,
      physicalOutputEnabled: false,
      scoreBasis: 'repo içi entegrasyon kontrol listesi',
      items: [{ id: 'radar_lidar_adapter', status: 'tbd', label: 'TFA50-L 1D LiDAR' }],
      nextCriticalActions: ['TFA50-L fiziksel kabulünü tamamla.'],
    });

    const readiness = await fetchOperatorReadiness('http://127.0.0.1:8088/');

    expect(readiness.readinessPercent).toBe(42);
    expect(readiness.physicalOutputEnabled).toBe(false);
    expect(readiness.items[0]).toMatchObject({ id: 'radar_lidar_adapter', status: 'tbd' });
    expect(globalThis.fetch).toHaveBeenCalledWith('http://127.0.0.1:8088/readiness', expect.objectContaining({ method: 'GET' }));
  });

  it('fetches sensor frames and posts stage requests', async () => {
    mockFetch({
      schemaVersion: 1,
      stage: 3,
      round: 1,
      replayOnly: true,
      physicalOutputEnabled: false,
      sensorHealth: { status: 'replay', replayOnly: true, physicalOutputEnabled: false },
      frames: [{ frameId: 'SENS-1', sensor: 'fusion', targetType: 'F16', friendFoe: 'Düşman' }],
      result: { accepted: true, physicalOutput: false },
      state: { stage: 3, round: 1, dryRun: true },
    });

    const frames = await fetchOperatorSensorFrames('http://127.0.0.1:8088/');
    await sendOperatorStageRequest('http://127.0.0.1:8088/', {
      kind: 'StageRequest',
      stage: 3,
      round: 1,
      operatorId: 'OP-UI-1',
      timestamp: '2026-05-25T20:20:00Z',
      reason: 'unit-test',
      dryRun: true,
    });

    expect(frames.replayOnly).toBe(true);
    expect(frames.frames[0]).toMatchObject({ sensor: 'fusion', friendFoe: 'Düşman' });
    expect(globalThis.fetch).toHaveBeenNthCalledWith(1, 'http://127.0.0.1:8088/sensor-frames', expect.objectContaining({ method: 'GET' }));
    expect(globalThis.fetch).toHaveBeenNthCalledWith(2, 'http://127.0.0.1:8088/stage', expect.objectContaining({ method: 'POST', headers: { 'Content-Type': 'application/json' } }));
  });

  it('posts mode, manual-aim, and fire-intent commands as JSON', async () => {
    mockFetch({ result: { accepted: true, physicalOutput: false }, state: { dryRun: true } });

    await sendOperatorModeRequest('http://127.0.0.1:8088', {
      kind: 'ModeRequest',
      requestedMode: 'autonomous',
      operatorId: 'OP-UI-1',
      timestamp: '2026-05-25T20:20:00Z',
      reason: 'unit-test',
      dryRun: true,
    });
    await sendOperatorManualAimCommand('http://127.0.0.1:8088', {
      kind: 'ManualAimCommand',
      panDeltaDeg: 2,
      tiltDeltaDeg: 0,
      rateLimitDegPerSec: 12,
      deadmanActive: true,
      dryRun: true,
    });
    await sendOperatorFireIntent('http://127.0.0.1:8088', {
      kind: 'FireIntent',
      targetId: 'DRY-RUN-F16-01',
      stage: 3,
      round: 1,
      operatorConfirm: true,
      dryRun: true,
      requestedAt: '2026-05-25T20:20:01Z',
    });

    expect(globalThis.fetch).toHaveBeenNthCalledWith(1, 'http://127.0.0.1:8088/mode', expect.objectContaining({ method: 'POST', headers: { 'Content-Type': 'application/json' } }));
    expect(globalThis.fetch).toHaveBeenNthCalledWith(2, 'http://127.0.0.1:8088/manual-aim', expect.objectContaining({ method: 'POST', headers: { 'Content-Type': 'application/json' } }));
    expect(globalThis.fetch).toHaveBeenNthCalledWith(3, 'http://127.0.0.1:8088/fire-intent', expect.objectContaining({ method: 'POST', headers: { 'Content-Type': 'application/json' } }));
  });

  it('fetches telemetry export, replay, and reset endpoints without live output', async () => {
    mockFetch({
      schemaVersion: 1,
      physicalOutputEnabled: false,
      replayOnly: true,
      telemetry: { path: 'telemetry_data/operator-api-dry-run.jsonl', exists: true, recordCount: 2 },
      entries: [{ recordType: 'event', payload: { physicalOutput: false } }],
      state: { dryRun: true },
    });

    const exported = await fetchOperatorTelemetryExport('http://127.0.0.1:8088');
    const replay = await fetchOperatorReplay('http://127.0.0.1:8088');
    const reset = await resetOperatorTelemetry('http://127.0.0.1:8088');

    expect(exported.physicalOutputEnabled).toBe(false);
    expect(replay.physicalOutputEnabled).toBe(false);
    expect(reset.physicalOutputEnabled).toBe(false);
    expect(globalThis.fetch).toHaveBeenNthCalledWith(1, 'http://127.0.0.1:8088/telemetry/export', expect.objectContaining({ method: 'GET' }));
    expect(globalThis.fetch).toHaveBeenNthCalledWith(2, 'http://127.0.0.1:8088/replay', expect.objectContaining({ method: 'GET' }));
    expect(globalThis.fetch).toHaveBeenNthCalledWith(3, 'http://127.0.0.1:8088/telemetry/reset', expect.objectContaining({ method: 'POST', headers: { 'Content-Type': 'application/json' } }));
  });

  it('surfaces backend failures instead of silently claiming acceptance', async () => {
    mockFetch({ error: 'unavailable' }, false);

    await expect(fetchOperatorSnapshot('http://127.0.0.1:8088')).rejects.toThrow('Operator API 503');
  });

  it('surfaces non-JSON API responses as contract failures', async () => {
    globalThis.fetch = vi.fn(async () => ({
      ok: true,
      status: 200,
      statusText: 'OK',
      json: async () => {
        throw new SyntaxError('Unexpected token');
      },
    })) as unknown as typeof fetch;

    await expect(fetchOperatorReadiness('http://127.0.0.1:8088')).rejects.toThrow('JSON yanıtı okunamadı');
  });
});
