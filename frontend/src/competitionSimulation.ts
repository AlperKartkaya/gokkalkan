import { courseRangeFromPoint, pointAtProgress } from './competitionCourse';
import { rangeGateFor } from './safetyGate';
import type { Stage, TargetType, Track } from './types';

const env = import.meta.env;

function numberFromEnv(key: string, fallback: number, min: number, max: number): number {
  const raw = env[key];
  const parsed = typeof raw === 'string' && raw.trim() !== '' ? Number(raw) : fallback;
  const finite = Number.isFinite(parsed) ? parsed : fallback;
  return Math.min(max, Math.max(min, finite));
}

export type SimulatorMode = 'strict' | 'practice';

export const COMPETITION_STAGE_ROUNDS: Record<Stage, number> = {
  1: 1,
  2: 4,
  3: 8,
};

export const HOSTILE_TYPES_BY_ROUND: TargetType[] = [
  'F16',
  'Helikopter',
  'Mini/Micro İHA',
  'Balistik Füze',
  'F16',
  'Helikopter',
  'Mini/Micro İHA',
  'Balistik Füze',
];

export const STAGE2_TRAINING_SCENARIOS: Array<readonly [TargetType, TargetType, TargetType]> = [
  ['Balistik Füze', 'Mini/Micro İHA', 'Balistik Füze'],
  ['Mini/Micro İHA', 'Balistik Füze', 'Mini/Micro İHA'],
  ['Balistik Füze', 'Mini/Micro İHA', 'Mini/Micro İHA'],
  ['Mini/Micro İHA', 'Balistik Füze', 'Balistik Füze'],
  ['Balistik Füze', 'Mini/Micro İHA', 'Balistik Füze'],
  ['Mini/Micro İHA', 'Balistik Füze', 'Mini/Micro İHA'],
  ['Balistik Füze', 'Mini/Micro İHA', 'Mini/Micro İHA'],
  ['Mini/Micro İHA', 'Balistik Füze', 'Balistik Füze'],
];

export const competitionSimulationConfig = {
  assumptionNotice:
    'Rota koordinatları PLG26-A-001-002-00-R1 çiziminden alınır; 0,4 m/s hız komite kaynaklı geçici prior olup şartname değeri değildir ve saha kestirimiyle güncellenir.',
  stage1: {
    timeLimitSeconds: 300,
    targetOrder: ['Balistik Füze', 'Helikopter', 'F16', 'Mini/Micro İHA'] as TargetType[],
    orderPolicy: 'hakem-random-observed-at-runtime',
    wrongTargetPenalty: -5,
    maxBaseScore: 80,
    bonusFormula: '20 × kalan saniye / 300',
  },
  stage2: {
    rounds: 4,
    practiceRounds: numberFromEnv('VITE_GOKKALKAN_STAGE2_PRACTICE_ROUNDS', 8, 5, 24),
    lanes: 3,
    roundDurationSeconds: numberFromEnv('VITE_GOKKALKAN_STAGE2_ROUND_SECONDS', 18, 6, 120),
    targetSpeedMps: numberFromEnv('VITE_GOKKALKAN_STAGE2_TARGET_SPEED_MPS', 0.4, 0.1, 20),
    engagementProgressMin: numberFromEnv('VITE_GOKKALKAN_STAGE2_ENGAGEMENT_PROGRESS_MIN', 0.2, 0.05, 0.9),
    pointsByDestroyedCount: { 0: -5, 1: 5, 2: 15, 3: 30 } as Record<0 | 1 | 2 | 3, number>,
  },
  stage3: {
    rounds: 8,
    lanes: 3,
    roundDurationSeconds: numberFromEnv('VITE_GOKKALKAN_STAGE3_ROUND_SECONDS', 20, 6, 120),
    targetSpeedMps: numberFromEnv('VITE_GOKKALKAN_STAGE3_TARGET_SPEED_MPS', 0.4, 0.1, 20),
    engagementProgressMin: numberFromEnv('VITE_GOKKALKAN_STAGE3_ENGAGEMENT_PROGRESS_MIN', 0.32, 0.05, 0.9),
    maxRoundPenalty: -10,
    failIfConsecutiveHostileMisses: 4,
  },
  uavPreferredAutoEngagementMaxRangeMeters: numberFromEnv('VITE_GOKKALKAN_UAV_AUTO_ENGAGE_MAX_RANGE_M', 5, 0, 15),
  targetVisualScale: {
    F16: numberFromEnv('VITE_GOKKALKAN_F16_VISUAL_SCALE', 1.15, 0.4, 2.5),
    Helikopter: numberFromEnv('VITE_GOKKALKAN_HELICOPTER_VISUAL_SCALE', 1, 0.4, 2.5),
    'Balistik Füze': numberFromEnv('VITE_GOKKALKAN_MISSILE_VISUAL_SCALE', 1.06, 0.4, 2.5),
    'Mini/Micro İHA': numberFromEnv('VITE_GOKKALKAN_UAV_VISUAL_SCALE', 0.82, 0.3, 2),
  } satisfies Record<TargetType, number>,
};

export function stage1ScoreForRange(range: number): number {
  if (range <= 7.5) return 5;
  if (range <= 12.5) return 10;
  return 20;
}

export function stage2RoundScore(destroyedCount: number): number {
  const bounded = Math.min(3, Math.max(0, destroyedCount)) as 0 | 1 | 2 | 3;
  return competitionSimulationConfig.stage2.pointsByDestroyedCount[bounded];
}

export function stage3TargetScore(type: TargetType): number {
  if (type === 'F16') return 30;
  if (type === 'Mini/Micro İHA') return 10;
  return 20;
}

export function roundDurationFor(stage: Stage): number {
  if (stage === 2) return competitionSimulationConfig.stage2.roundDurationSeconds;
  if (stage === 3) return competitionSimulationConfig.stage3.roundDurationSeconds;
  return competitionSimulationConfig.stage1.timeLimitSeconds;
}

function scaledSize(type: TargetType): { w: number; h: number } {
  const scale = competitionSimulationConfig.targetVisualScale[type];
  const base = {
    F16: { w: 11.8, h: 7.6 },
    Helikopter: { w: 8.7, h: 8.7 },
    'Balistik Füze': { w: 7.2, h: 11.5 },
    'Mini/Micro İHA': { w: 7.5, h: 7.5 },
  } satisfies Record<TargetType, { w: number; h: number }>;
  return { w: base[type].w * scale, h: base[type].h * scale };
}

function movingTrack(params: {
  stage: 2 | 3;
  round: number;
  lane: 1 | 2 | 3;
  elapsedInRound: number;
  type: TargetType;
  friendFoe: Track['friendFoe'];
  hostileLane?: 1 | 2 | 3;
}): Track {
  const { stage, round, lane, elapsedInRound, type, friendFoe, hostileLane } = params;
  const duration = roundDurationFor(stage);
  const progress = Math.min(1, Math.max(0, elapsedInRound / duration));
  const lanePhase = lane === 1 ? 0 : lane === 2 ? 0.035 : 0.07;
  const point = pointAtProgress(lane, Math.min(1, progress + lanePhase));
  const trackRange = Number(courseRangeFromPoint(point).toFixed(1));
  const gate = rangeGateFor(type, trackRange);
  const size = scaledSize(type);
  const velocity = stage === 2 ? competitionSimulationConfig.stage2.targetSpeedMps : competitionSimulationConfig.stage3.targetSpeedMps;
  const uavCloseEnough = type !== 'Mini/Micro İHA' || trackRange <= competitionSimulationConfig.uavPreferredAutoEngagementMaxRangeMeters;
  const candidate = stage === 2
    ? gate === 'Uygun' && progress >= competitionSimulationConfig.stage2.engagementProgressMin && progress < 0.94 && uavCloseEnough
    : friendFoe === 'Düşman' && gate === 'Uygun' && progress >= competitionSimulationConfig.stage3.engagementProgressMin && progress < 0.96 && uavCloseEnough;
  const uavTrainingNote = type === 'Mini/Micro İHA'
    ? ` · İHA eğitim tercihi ≤${competitionSimulationConfig.uavPreferredAutoEngagementMaxRangeMeters} m`
    : '';

  return {
    id: stage === 2 ? `S2-R${round}-L${lane}` : `S3-R${round}-${friendFoe === 'Düşman' ? 'X' : `F${lane}`}`,
    x: Math.min(94, Math.max(5, point.x)),
    y: Math.min(92, Math.max(8, point.y)),
    w: size.w,
    h: size.h,
    lane,
    type,
    friendFoe,
    confidence: stage === 3 && friendFoe === 'Düşman' ? 0.96 : 0.9,
    range: trackRange,
    velocity,
    direction: stage === 2
      ? `Poligon giriş→çıkış · Rota ${lane} · ${velocity.toFixed(1)} m/s varsayım${uavTrainingNote}`
      : `${friendFoe === 'Düşman' ? 'Kırmızı/düşman' : 'Camgöbeği/dost'} · Rota ${lane} · ${hostileLane === lane ? 'ana hedef' : 'korunacak unsur'}${uavTrainingNote}`,
    rangeGate: gate,
    candidate,
  };
}

export function generateCompetitionTracks(stage: Stage, elapsedInRound: number, round: number): Track[] {
  if (stage === 1) {
    const targets: Array<{ id: string; type: TargetType; range: number; x: number; y: number; lane: 1 | 2 | 3 }> = [
      { id: 'S1-1', type: 'Balistik Füze', range: 5, x: 76, y: 56, lane: 3 },
      { id: 'S1-2', type: 'Helikopter', range: 10, x: 49, y: 42, lane: 2 },
      { id: 'S1-3', type: 'F16', range: 15, x: 22, y: 36, lane: 1 },
      { id: 'S1-4', type: 'Mini/Micro İHA', range: 15, x: 22, y: 63, lane: 1 },
    ];
    return targets.map((target, index) => {
      const size = scaledSize(target.type);
      return {
        ...target,
        w: size.w,
        h: size.h,
        friendFoe: 'Bilinmeyen',
        confidence: 1,
        velocity: 0,
        direction: `Durağan hedef · ${target.range} m`,
        rangeGate: rangeGateFor(target.type, target.range),
        candidate: index === 0,
      } satisfies Track;
    });
  }

  if (stage === 2) {
    const scenario = STAGE2_TRAINING_SCENARIOS[(round - 1) % STAGE2_TRAINING_SCENARIOS.length];
    return ([1, 2, 3] as const).map((lane) => movingTrack({
      stage: 2,
      round,
      lane,
      elapsedInRound,
      type: scenario[lane - 1],
      friendFoe: 'Bilinmeyen',
    }));
  }

  const hostileLane = (((round - 1) % 3) + 1) as 1 | 2 | 3;
  const hostileType = HOSTILE_TYPES_BY_ROUND[(round - 1) % HOSTILE_TYPES_BY_ROUND.length];
  const friendlyTypes: TargetType[] = round % 2 === 0 ? ['F16', 'Helikopter'] : ['Helikopter', 'F16'];
  let friendlyIndex = 0;
  return ([1, 2, 3] as const).map((lane) => {
    const isHostile = lane === hostileLane;
    const type = isHostile ? hostileType : friendlyTypes[friendlyIndex++ % friendlyTypes.length];
    return movingTrack({
      stage: 3,
      round,
      lane,
      elapsedInRound,
      type,
      friendFoe: isHostile ? 'Düşman' : 'Dost',
      hostileLane,
    });
  });
}
