import { describe, expect, it } from 'vitest';
import { clampPan, clampTilt, mechanicsConfig, signedDegrees } from './mechanicsConfig';

describe('mechanicsConfig defaults', () => {
  it('keeps mock pan/tilt commands inside configured mechanical limits', () => {
    expect(clampPan(mechanicsConfig.panMaxDeg + 100)).toBe(mechanicsConfig.panMaxDeg);
    expect(clampPan(mechanicsConfig.panMinDeg - 100)).toBe(mechanicsConfig.panMinDeg);
    expect(clampTilt(mechanicsConfig.tiltMaxDeg + 100)).toBe(mechanicsConfig.tiltMaxDeg);
    expect(clampTilt(mechanicsConfig.tiltMinDeg - 100)).toBe(mechanicsConfig.tiltMinDeg);
  });

  it('formats signed degree readouts for operator controls', () => {
    expect(signedDegrees(mechanicsConfig.fineStepDeg)).toBe('+0.5°');
    expect(signedDegrees(-mechanicsConfig.fineStepDeg)).toBe('-0.5°');
  });
});
