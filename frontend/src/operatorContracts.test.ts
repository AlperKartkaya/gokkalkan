import { describe, expect, it } from 'vitest';
import { canSendFireIntent, evaluateOperatorSafety, makeCommandResult, makeFireIntent } from './operatorContracts';
import type { OperatorSafetyState } from './operatorContracts';

const baseSafetyInput: Omit<OperatorSafetyState, 'blockReason' | 'explanation'> = {
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
};

describe('operator panel safety contracts', () => {
  it('allows dry-run fire intent without perception hardware but never requires live arming', () => {
    const safety = evaluateOperatorSafety(baseSafetyInput);

    expect(safety.blockReason).toBe('ALLOWED');
    expect(canSendFireIntent(safety, 'DRY-RUN-T1')).toBe(true);
  });

  it('blocks live commands when live arming is not enabled', () => {
    const safety = evaluateOperatorSafety({ ...baseSafetyInput, dryRun: false });

    expect(safety.blockReason).toBe('BLOCKED_ARMING');
    expect(canSendFireIntent(safety, 'LIVE-T1')).toBe(false);
  });

  it('blocks when backend is unavailable even if the UI has a selected target', () => {
    const safety = evaluateOperatorSafety({ ...baseSafetyInput, backendConnected: false });

    expect(safety.blockReason).toBe('BLOCKED_BACKEND');
    expect(canSendFireIntent(safety, 'DRY-RUN-T1')).toBe(false);
  });

  it('creates explicit dry-run command results with no physical output claim', () => {
    const intent = makeFireIntent({ targetId: 'DRY-RUN-T1', stage: 3, round: 1, dryRun: true, now: new Date('2026-05-25T20:00:00Z') });
    const result = makeCommandResult({
      commandId: intent.requestedAt,
      kind: intent.kind,
      accepted: true,
      dryRun: intent.dryRun,
      safetyBlockReason: 'ALLOWED',
      createdAt: new Date('2026-05-25T20:00:01Z'),
    });

    expect(intent).toMatchObject({ kind: 'FireIntent', targetId: 'DRY-RUN-T1', dryRun: true });
    expect(result.completed).toBe(true);
    expect(result.message).toContain('fiziksel çıkış üretilmedi');
  });

  it('does not claim backend acceptance when an offline live command is blocked', () => {
    const result = makeCommandResult({
      commandId: 'MODE-offline',
      kind: 'ModeRequest',
      accepted: false,
      dryRun: false,
      safetyBlockReason: 'BLOCKED_BACKEND',
      createdAt: new Date('2026-05-25T20:00:02Z'),
    });

    expect(result.completed).toBe(false);
    expect(result.message).toBe('Backend bağlantısı yok; gerçek komut gönderilemez.');
  });
});
