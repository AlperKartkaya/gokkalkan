import { describe, expect, it } from 'vitest';
import {
  canSendFireIntent,
  canSendManualAim,
  evaluateOperatorSafety,
  isManualAimPayloadSafe,
  makeCommandResult,
  makeFireIntent,
  makeManualAimCommand,
  makeStageRequest,
  stageExpectedMode,
  stageMissionCopy,
  stageRoundLimit,
} from './operatorContracts';
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

  it('creates manual aim commands only inside bounded dry-run guardrails', () => {
    const command = makeManualAimCommand({
      panDeltaDeg: 2,
      tiltDeltaDeg: 0,
      deadmanActive: true,
      dryRun: true,
    });

    expect(command).toMatchObject({ kind: 'ManualAimCommand', rateLimitDegPerSec: 12, deadmanActive: true });
    expect(isManualAimPayloadSafe(command)).toBe(true);
    expect(isManualAimPayloadSafe({ ...command, panDeltaDeg: 99 })).toBe(false);
    expect(canSendManualAim({ stage: 1, mode: 'manual', deadmanActive: true, dryRun: true, liveArmEnabled: false, backendConnected: true })).toBe(true);
    expect(canSendManualAim({ stage: 3, mode: 'manual', deadmanActive: true, dryRun: true, liveArmEnabled: false, backendConnected: true })).toBe(false);
    expect(canSendManualAim({ stage: 1, mode: 'safe', deadmanActive: true, dryRun: true, liveArmEnabled: false, backendConnected: true })).toBe(false);
    expect(canSendManualAim({ stage: 1, mode: 'manual', deadmanActive: false, dryRun: true, liveArmEnabled: false, backendConnected: true })).toBe(false);
  });

  it('creates stage requests with şartname-aligned round limits and mode expectations', () => {
    const stage3 = makeStageRequest({ stage: 3, round: 8, dryRun: true, now: new Date('2026-05-25T20:00:03Z') });
    const stage2 = makeStageRequest({ stage: 2, round: 4, dryRun: true, now: new Date('2026-05-25T20:00:04Z') });

    expect(stage3).toMatchObject({ kind: 'StageRequest', stage: 3, round: 8, dryRun: true });
    expect(stage2.round).toBe(4);
    expect(() => makeStageRequest({ stage: 3, round: 8.1, dryRun: true })).toThrow(/exact integers/);
    expect(() => makeStageRequest({ stage: 2, round: 5, dryRun: true })).toThrow(/outside Aşama 2 bounds/);
    expect(stageRoundLimit(1)).toBe(4);
    expect(stageRoundLimit(2)).toBe(4);
    expect(stageRoundLimit(3)).toBe(8);
    expect(stageExpectedMode(1)).toBe('manual');
    expect(stageExpectedMode(3)).toBe('autonomous');
    expect(stageMissionCopy(2)).toContain('sınıflandırma zorunlu değil');
  });
});
