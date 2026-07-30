import { describe, expect, it } from 'vitest';
import { STAGE_SCENARIOS, generateScenarioTracks, scenarioFrameFor } from './index';

describe('hands-off competition scenarios', () => {
  it('defines all three stages with source refs, events, and adjustable target routes', () => {
    ([1, 2, 3] as const).forEach((stage) => {
      const scenario = STAGE_SCENARIOS[stage];
      expect(scenario.stage).toBe(stage);
      expect(scenario.sourceRefs.join(' ')).toContain('docs/sartname_v4.txt');
      expect(scenario.events.length).toBeGreaterThan(8);
      expect(scenario.targets.every((target) => target.route.length >= 2)).toBe(true);
      expect(scenario.routeAdjustableNote).toContain('route');
    });
  });

  it('auto-selects the Şartname mode for each stage frame', () => {
    expect(scenarioFrameFor(STAGE_SCENARIOS[1], 0).mode).toBe('manual');
    expect(scenarioFrameFor(STAGE_SCENARIOS[2], 0).mode).toBe('autonomous');
    expect(scenarioFrameFor(STAGE_SCENARIOS[3], 0).mode).toBe('autonomous');
  });

  it('interpolates Aşama 2 routes from A to B so target positions are adjustable by file data', () => {
    const early = generateScenarioTracks(STAGE_SCENARIOS[2], 1).find((track) => track.id === 'S2-R1-L2');
    const later = generateScenarioTracks(STAGE_SCENARIOS[2], 10).find((track) => track.id === 'S2-R1-L2');
    expect(early).toBeTruthy();
    expect(later).toBeTruthy();
    expect(later!.x).toBeGreaterThan(early!.x);
    expect(later!.range).toBeLessThan(early!.range);
    expect(later!.direction).toContain('A→B');
  });

  it('models maintenance and hit/miss outcomes in replay frames', () => {
    const stage1Maintenance = scenarioFrameFor(STAGE_SCENARIOS[1], 65);
    expect(stage1Maintenance.mode).toBe('maintenance');
    expect(stage1Maintenance.paused).toBe(true);

    const stage2Miss = scenarioFrameFor(STAGE_SCENARIOS[2], 45);
    expect(stage2Miss.misses).toBe(1);
    expect(stage2Miss.score).toBe(45);

    const stage3FriendGate = scenarioFrameFor(STAGE_SCENARIOS[3], 55);
    expect(stage3FriendGate.blockReason).toBe('BLOCKED_TARGET_GATE');
    expect(stage3FriendGate.selectedTargetId).toBe('S3-R3-F1');
  });

  it('keeps Aşama 3 friends non-candidates while enemy candidate is available in range', () => {
    const tracks = generateScenarioTracks(STAGE_SCENARIOS[3], 8);
    expect(tracks.filter((track) => track.friendFoe === 'Dost').every((track) => !track.candidate)).toBe(true);
    expect(tracks.some((track) => track.friendFoe === 'Düşman' && track.candidate)).toBe(true);
  });
});
