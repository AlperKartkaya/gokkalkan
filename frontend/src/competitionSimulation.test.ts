import { describe, expect, it } from 'vitest';
import { COMPETITION_STAGE_ROUNDS, competitionSimulationConfig, generateCompetitionTracks, stage1ScoreForRange, stage2RoundScore, stage3TargetScore } from './competitionSimulation';
import { rangeRuleFor } from './missionConfig';

describe('competition mechanics simulator', () => {
  it('keeps official stage round counts and configurable assumption notice', () => {
    expect(COMPETITION_STAGE_ROUNDS).toEqual({ 1: 1, 2: 4, 3: 8 });
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
