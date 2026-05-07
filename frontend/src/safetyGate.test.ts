import { describe, expect, it } from 'vitest';
import { evaluateSafety } from './safetyGate';
import type { Mode, SafetyState, Stage, Track } from './types';

const base: Omit<SafetyState, 'blockReason'> = {
  estop: false,
  motionZoneOk: true,
  fireZoneOk: true,
  targetGateOk: true,
  modeOk: true,
  connectionOk: true,
};

const enemyTrack: Track = {
  id: 'S3-X1',
  x: 50,
  y: 50,
  w: 10,
  h: 10,
  lane: 1,
  type: 'F16',
  friendFoe: 'Düşman',
  confidence: 0.92,
  range: 12,
  velocity: 2,
  direction: 'Yaklaşıyor',
  rangeGate: 'Uygun',
  candidate: true,
};

const friendTrack: Track = { ...enemyTrack, id: 'S3-F2', friendFoe: 'Dost', candidate: false };
const invalidRangeTrack: Track = { ...enemyTrack, id: 'S3-X3', range: 4, rangeGate: 'Geçersiz' };

function check(overrides: Partial<Omit<SafetyState, 'blockReason'>>, stage: Stage = 3, mode: Mode = 'autonomous', selectedTrack = enemyTrack) {
  return evaluateSafety({
    stage,
    mode,
    base: { ...base, ...overrides },
    selectedTrack,
    command: 'autonomous_engage',
  }).blockReason;
}

describe('evaluateSafety', () => {
  it('blocks all commands on estop', () => {
    expect(check({ estop: true })).toBe('BLOCKED_ESTOP');
  });

  it('blocks disconnected hardware', () => {
    expect(check({ connectionOk: false })).toBe('BLOCKED_CONNECTION');
  });

  it('blocks movement zone for movement intents', () => {
    const result = evaluateSafety({ stage: 2, mode: 'autonomous', base: { ...base, motionZoneOk: false }, selectedTrack: enemyTrack, command: 'autonomous_move' });
    expect(result.blockReason).toBe('BLOCKED_MOTION_ZONE');
  });

  it('blocks fire zone for autonomous engagement', () => {
    expect(check({ fireZoneOk: false })).toBe('BLOCKED_FIRE_ZONE');
  });

  it('blocks mode mismatch', () => {
    expect(check({}, 2, 'safe')).toBe('BLOCKED_MODE');
  });

  it('blocks stage 3 friend target', () => {
    expect(check({}, 3, 'autonomous', friendTrack)).toBe('BLOCKED_TARGET_GATE');
  });

  it('blocks stage 3 invalid range', () => {
    expect(check({}, 3, 'autonomous', invalidRangeTrack)).toBe('BLOCKED_TARGET_GATE');
  });

  it('allows stage 3 valid enemy in range', () => {
    expect(check({})).toBe('ALLOWED');
  });
});
