import { describe, expect, it } from 'vitest';
import { COMPETITION_STAGE_ROUNDS, STAGE2_TRAINING_SCENARIOS, competitionSimulationConfig, generateCompetitionTracks, stage1ScoreForRange, stage2RoundScore, stage3TargetScore } from './competitionSimulation';
import { rangeRuleFor } from './missionConfig';

describe('competition mechanics simulator', () => {
  it('keeps official stage round counts and configurable assumption notice', () => {
    expect(COMPETITION_STAGE_ROUNDS).toEqual({ 1: 1, 2: 4, 3: 8 });
    expect(competitionSimulationConfig.stage2.practiceRounds).toBeGreaterThan(COMPETITION_STAGE_ROUNDS[2]);
    expect(competitionSimulationConfig.stage2.targetSpeedMps).toBeGreaterThan(0);
    expect(competitionSimulationConfig.assumptionNotice).toContain('şartnamede sayısal verilmediği');
  });

  it('scores Stage 1 and Stage 2 using final-phase rules', () => {
    expect(stage1ScoreForRange(5)).toBe(5);
    expect(stage1ScoreForRange(10)).toBe(10);
    expect(stage1ScoreForRange(15)).toBe(20);
    expect(stage2RoundScore(0)).toBe(-5);
    expect(stage2RoundScore(1)).toBe(5);
    expect(stage2RoundScore(2)).toBe(15);
    expect(stage2RoundScore(3)).toBe(30);
  });

  it('generates Stage 2 rounds as three A-to-B lane targets without classification requirement', () => {
    const tracks = generateCompetitionTracks(2, 6, 2);
    expect(tracks).toHaveLength(3);
    expect(tracks.map((track) => track.lane)).toEqual([1, 2, 3]);
    expect(tracks.every((track) => track.friendFoe === 'Bilinmeyen')).toBe(true);
    expect(tracks.every((track) => track.direction.includes('A→B'))).toBe(true);
  });

  it('continues Stage 2 practice scenarios past official round 4 with varied target types', () => {
    expect(STAGE2_TRAINING_SCENARIOS).toHaveLength(8);
    const roundFiveTracks = generateCompetitionTracks(2, 1, 5);
    expect(roundFiveTracks.map((track) => track.id)).toEqual(['S2-R5-L1', 'S2-R5-L2', 'S2-R5-L3']);
    expect(new Set(roundFiveTracks.map((track) => track.type))).toEqual(new Set(['F16', 'Balistik Füze', 'Helikopter']));
  });

  it('updates Stage 2 and Stage 3 target positions on sub-second time deltas', () => {
    for (const stage of [2, 3] as const) {
      const before = generateCompetitionTracks(stage, 1, 1);
      const after = generateCompetitionTracks(stage, 1.25, 1);
      expect(after.map((track, index) => Math.hypot(track.x - before[index].x, track.y - before[index].y))
        .some((delta) => delta > 0.1)).toBe(true);
    }
  });

  it('delays autonomous engagement instead of shooting targets as soon as they enter', () => {
    const enteringTracks = generateCompetitionTracks(2, 0.5, 1);
    expect(enteringTracks).toHaveLength(3);
    expect(enteringTracks.some((track) => track.candidate)).toBe(false);

    const engagementTracks = generateCompetitionTracks(
      2,
      competitionSimulationConfig.stage2.roundDurationSeconds * 0.62,
      1,
    );
    expect(engagementTracks.some((track) => track.candidate)).toBe(true);
  });

  it('gates Stage 2 F16 engagement to the official 10-15 m window', () => {
    const duration = competitionSimulationConfig.stage2.roundDurationSeconds;
    const samples = Array.from({ length: 80 }, (_, index) => generateCompetitionTracks(2, (duration * index) / 79, 1)
      .find((track) => track.type === 'F16'));
    const candidateSamples = samples.filter((track): track is NonNullable<typeof track> => Boolean(track?.candidate));

    expect(candidateSamples.length).toBeGreaterThan(0);
    expect(candidateSamples.every((track) => track.range >= 10 && track.range <= 15)).toBe(true);
    expect(samples.some((track) => Boolean(track?.candidate && track.range < 10))).toBe(false);
  });

  it('generates Stage 3 rounds with exactly one hostile and two friendly targets plus valid scoring', () => {
    const tracks = generateCompetitionTracks(3, 3, 1);
    expect(tracks.filter((track) => track.friendFoe === 'Düşman')).toHaveLength(1);
    expect(tracks.filter((track) => track.friendFoe === 'Dost')).toHaveLength(2);
    expect(stage3TargetScore('F16')).toBe(30);
    expect(stage3TargetScore('Helikopter')).toBe(20);
    expect(stage3TargetScore('Balistik Füze')).toBe(20);
    expect(stage3TargetScore('Mini/Micro İHA')).toBe(10);
  });

  it('keeps Mini/Micro İHA official scoring range while preferring close autonomous training engagement', () => {
    expect(rangeRuleFor('Mini/Micro İHA')).toMatchObject({ min: 0, max: 15 });

    const earlyHostileUav = generateCompetitionTracks(3, competitionSimulationConfig.stage3.roundDurationSeconds * 0.45, 3)
      .find((track) => track.friendFoe === 'Düşman');
    expect(earlyHostileUav?.type).toBe('Mini/Micro İHA');
    expect(earlyHostileUav?.rangeGate).toBe('Uygun');
    expect(earlyHostileUav?.range).toBeGreaterThan(competitionSimulationConfig.uavPreferredAutoEngagementMaxRangeMeters);
    expect(earlyHostileUav?.candidate).toBe(false);

    const closeHostileUav = generateCompetitionTracks(3, competitionSimulationConfig.stage3.roundDurationSeconds * 0.88, 3)
      .find((track) => track.friendFoe === 'Düşman');
    expect(closeHostileUav?.type).toBe('Mini/Micro İHA');
    expect(closeHostileUav?.range).toBeLessThanOrEqual(competitionSimulationConfig.uavPreferredAutoEngagementMaxRangeMeters);
    expect(closeHostileUav?.candidate).toBe(true);
  });
});
