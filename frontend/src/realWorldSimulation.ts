import { COMPETITION_COURSE, bearingFromSystem, courseRangeFromPoint, pointAtProgress } from './competitionCourse';
import { rangeGateFor } from './safetyGate';
import type { FriendFoe, Stage, TargetType, Track } from './types';

const env = import.meta.env;

function numberFromEnv(key: string, fallback: number, min: number, max: number): number {
  const raw = env[key];
  const parsed = typeof raw === 'string' && raw.trim() !== '' ? Number(raw) : fallback;
  const finite = Number.isFinite(parsed) ? parsed : fallback;
  return Math.min(max, Math.max(min, finite));
}

function booleanFromEnv(key: string, fallback: boolean): boolean {
  const raw = env[key];
  if (typeof raw !== 'string') return fallback;
  if (['1', 'true', 'yes', 'on'].includes(raw.toLowerCase())) return true;
  if (['0', 'false', 'no', 'off'].includes(raw.toLowerCase())) return false;
  return fallback;
}

export const realWorldSimulationConfig = {
  enabledByDefault: booleanFromEnv('VITE_GOKKALKAN_REALWORLD_SIM_DEFAULT', false),
  sensorNoisePx: numberFromEnv('VITE_GOKKALKAN_SIM_SENSOR_NOISE_PX', 1.8, 0, 12),
  latencyMs: numberFromEnv('VITE_GOKKALKAN_SIM_LATENCY_MS', 84, 0, 1_000),
  packetLossPercent: numberFromEnv('VITE_GOKKALKAN_SIM_PACKET_LOSS_PERCENT', 0.7, 0, 25),
  windMps: numberFromEnv('VITE_GOKKALKAN_SIM_WIND_MPS', 2.4, 0, 20),
  batteryStartV: numberFromEnv('VITE_GOKKALKAN_SIM_BATTERY_START_V', 15.8, 10, 24),
  tourSeconds: numberFromEnv('VITE_GOKKALKAN_SIM_TOUR_SECONDS', 22, 8, 120),
  cameraFovDeg: numberFromEnv('VITE_GOKKALKAN_SIM_CAMERA_FOV_DEG', 62, 20, 140),
  lidarRangeStdM: numberFromEnv('VITE_GOKKALKAN_SIM_LIDAR_RANGE_STD_M', 0.08, 0, 1),
  radarRangeStdM: numberFromEnv('VITE_GOKKALKAN_SIM_RADAR_RANGE_STD_M', 0.18, 0, 2),
  radarSnrDb: numberFromEnv('VITE_GOKKALKAN_SIM_RADAR_SNR_DB', 24, 5, 45),
};

export interface RealWorldTelemetry {
  source: string;
  frameId: number;
  fps: number;
  latencyMs: number;
  packetLossPercent: number;
  sensorNoisePx: number;
  windMps: number;
  batteryV: number;
  panLoadPercent: number;
  illuminationLux: number;
  lidarReturns: number;
  radarTracks: number;
  fusionLocks: number;
}

export interface CameraDetection {
  trackId: string;
  label: TargetType;
  friendFoe: FriendFoe;
  confidence: number;
  bbox: { x: number; y: number; w: number; h: number };
  colorHint: 'red-enemy' | 'blue-friend' | 'neutral';
}

export interface LidarReturn {
  trackId: string;
  lane: 1 | 2 | 3;
  rangeM: number;
  azimuthDeg: number;
  elevationDeg: number;
  pointCount: number;
  reflectivity: number;
  quality: 'iyi' | 'zayıf';
}

export interface RadarReturn {
  trackId: string;
  lane: 1 | 2 | 3;
  rangeM: number;
  bearingDeg: number;
  radialVelocityMps: number;
  snrDb: number;
  rcsDbsm: number;
}

export interface SensorFusionFrame {
  stage: Stage;
  frameId: number;
  cameraDetections: CameraDetection[];
  lidarReturns: LidarReturn[];
  radarReturns: RadarReturn[];
  fusedTargetId?: string;
  nearestRangeM?: number;
  assumptionNotice: string;
  sourceLineRefs: string[];
}

function wave(elapsed: number, speed: number, offset: number) {
  return Math.sin(elapsed * speed + offset);
}

function jitter(elapsed: number, seed: number, scale = 1) {
  return wave(elapsed, 0.73 + seed * 0.07, seed) * realWorldSimulationConfig.sensorNoisePx * scale;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function round1(value: number) {
  return Number(value.toFixed(1));
}

function validRangeForType(type: TargetType, elapsed: number, seed: number) {
  const midpoint = type === 'F16' ? 12.4 : type === 'Mini/Micro İHA' ? 6.3 : 8.6;
  const min = type === 'F16' ? 10 : type === 'Mini/Micro İHA' ? 0 : 5;
  return round1(clamp(midpoint + jitter(elapsed, seed, 0.06), min + 0.2, 14.7));
}

function movingProgress(elapsed: number, lane: 1 | 2 | 3, offset = 0) {
  return (elapsed / realWorldSimulationConfig.tourSeconds + lane * 0.11 + offset) % 1;
}

export function generateRealWorldTelemetry(stage: Stage, elapsed: number, enabled: boolean, trackCount = 3): RealWorldTelemetry {
  const activeFactor = enabled ? 1 : 0.35;
  const visibleTargets = stage === 1 ? 4 : trackCount;
  return {
    source: enabled ? 'real_camera_sim' : 'hardware_mock',
    frameId: Math.floor(elapsed * 30),
    fps: Math.round(27 + wave(elapsed, 0.4, stage) * 2),
    latencyMs: Math.round(realWorldSimulationConfig.latencyMs + activeFactor * wave(elapsed, 0.55, 2) * 16),
    packetLossPercent: Number((realWorldSimulationConfig.packetLossPercent + activeFactor * Math.max(0, wave(elapsed, 0.2, 1.8)) * 0.6).toFixed(1)),
    sensorNoisePx: Number((realWorldSimulationConfig.sensorNoisePx + activeFactor * Math.max(0, wave(elapsed, 0.8, 0.4)) * 0.7).toFixed(1)),
    windMps: Number((realWorldSimulationConfig.windMps + activeFactor * wave(elapsed, 0.18, 3) * 0.8).toFixed(1)),
    batteryV: Number(Math.max(12.2, realWorldSimulationConfig.batteryStartV - elapsed * 0.004).toFixed(2)),
    panLoadPercent: Math.round(34 + activeFactor * (stage * 6 + Math.max(0, wave(elapsed, 0.64, 0)) * 22)),
    illuminationLux: Math.round(510 + wave(elapsed, 0.15, 4) * 90),
    lidarReturns: visibleTargets,
    radarTracks: stage === 1 ? 0 : visibleTargets,
    fusionLocks: enabled ? Math.max(1, visibleTargets - (stage === 1 ? 2 : 0)) : 1,
  };
}

export function generateRealWorldTracks(stage: Stage, elapsed: number): Track[] {
  if (stage === 1) {
    const targets: Array<{ id: string; type: TargetType; range: number; x: number; y: number; w: number; h: number; confidence: number }> = [
      { id: 'M-1', type: 'Balistik Füze', range: 5, x: 76, y: 62, w: 9, h: 10, confidence: 0.91 },
      { id: 'M-2', type: 'Helikopter', range: 10, x: 48, y: 43, w: 9, h: 10, confidence: 0.87 },
      { id: 'M-3', type: 'F16', range: 15, x: 18, y: 57, w: 12, h: 10, confidence: 0.84 },
      { id: 'M-4', type: 'Mini/Micro İHA', range: 15, x: 61, y: 26, w: 8, h: 7, confidence: 0.79 },
    ];
    return targets.map((target, index) => ({
      ...target,
      x: clamp(target.x + jitter(elapsed, index + 1, 0.28), 8, 92),
      y: clamp(target.y + jitter(elapsed, index + 5, 0.22), 12, 86),
      lane: ((index % 3) + 1) as 1 | 2 | 3,
      friendFoe: 'Bilinmeyen',
      velocity: 0,
      direction: 'Sabit · 5/10/15 m saha jitter',
      rangeGate: rangeGateFor(target.type, target.range),
      candidate: index === 0,
    }));
  }

  if (stage === 2) {
    return ([1, 2, 3] as const).map((lane) => {
      const progress = movingProgress(elapsed, lane);
      const point = pointAtProgress(lane, progress);
      const type: TargetType = lane === 2 ? 'Balistik Füze' : 'Mini/Micro İHA';
      const range = round1(clamp(courseRangeFromPoint(point) + jitter(elapsed, lane + 2, 0.05), 3, 18.5));
      return {
        id: `S2-L${lane}`,
        x: clamp(point.x + jitter(elapsed, lane, 0.2), 6, 92),
        y: clamp(point.y + jitter(elapsed, lane + 6, 0.26), 16, 90),
        w: lane === 2 ? 10 : 8,
        h: lane === 2 ? 12 : 7,
        lane,
        type,
        friendFoe: 'Bilinmeyen',
        confidence: clamp(0.74 + Math.max(0, wave(elapsed, 0.7, lane)) * 0.18 - realWorldSimulationConfig.packetLossPercent / 200, 0.55, 0.96),
        range,
        velocity: round1(1.7 + lane * 0.46 + Math.max(0, wave(elapsed, 0.4, lane)) * 0.35),
        direction: `A→B · ${COMPETITION_COURSE.lanes[lane - 1].label} · parkurdan çıkmadan`,
        rangeGate: rangeGateFor(type, range),
        candidate: lane === 2 || progress > 0.42,
      };
    });
  }

  const enemyIndex = Math.floor(elapsed / 9) % 3;
  const types: TargetType[] = ['F16', 'Helikopter', 'Mini/Micro İHA'];
  return ([0, 1, 2] as const).map((index) => {
    const lane = (index + 1) as 1 | 2 | 3;
    const friendFoe: FriendFoe = index === enemyIndex ? 'Düşman' : 'Dost';
    const type = types[(index + Math.floor(elapsed / 12)) % types.length];
    const progress = movingProgress(elapsed, lane, 0.26 - index * 0.06);
    const point = pointAtProgress(lane, progress);
    const geometryRange = courseRangeFromPoint(point);
    const range = friendFoe === 'Düşman'
      ? validRangeForType(type, elapsed, index + 3)
      : round1(clamp(geometryRange + index * 0.4 + jitter(elapsed, index + 8, 0.05), 4.5, 16.8));
    const gate = rangeGateFor(type, range);
    return {
      id: `S3-${friendFoe === 'Düşman' ? 'X' : 'F'}${index + 1}`,
      x: clamp(point.x + jitter(elapsed, index, 0.18), 8, 92),
      y: clamp(point.y + jitter(elapsed, index + 4, 0.24), 16, 90),
      w: type === 'F16' ? 13 : 9,
      h: type === 'Mini/Micro İHA' ? 7 : 10,
      lane,
      type,
      friendFoe,
      confidence: clamp(0.78 + Math.max(0, wave(elapsed, 0.62, index)) * 0.17, 0.62, 0.97),
      range,
      velocity: round1(1.1 + index * 0.34 + realWorldSimulationConfig.windMps * 0.04),
      direction: friendFoe === 'Düşman' ? `Kırmızı ok · A→B · ${COMPETITION_COURSE.lanes[index].label}` : `Mavi ok · dost unsur · ${COMPETITION_COURSE.lanes[index].label}`,
      rangeGate: gate,
      candidate: friendFoe === 'Düşman' && gate === 'Uygun',
    };
  });
}

export function generateSensorFusionFrame(stage: Stage, elapsed: number, tracks: Track[]): SensorFusionFrame {
  const frameId = Math.floor(elapsed * 30);
  const cameraDetections = tracks.map((track): CameraDetection => ({
    trackId: track.id,
    label: track.type,
    friendFoe: track.friendFoe,
    confidence: Number(track.confidence.toFixed(2)),
    bbox: { x: round1(track.x), y: round1(track.y), w: round1(track.w), h: round1(track.h) },
    colorHint: track.friendFoe === 'Düşman' ? 'red-enemy' : track.friendFoe === 'Dost' ? 'blue-friend' : 'neutral',
  }));

  const lidarReturns = tracks.map((track, index): LidarReturn => ({
    trackId: track.id,
    lane: track.lane,
    rangeM: round1(track.range + wave(elapsed, 0.85, index) * realWorldSimulationConfig.lidarRangeStdM),
    azimuthDeg: bearingFromSystem({ x: track.x, y: track.y }),
    elevationDeg: round1(2.2 + track.lane * 1.4 + wave(elapsed, 0.3, index) * 0.6),
    pointCount: Math.max(8, Math.round(44 + track.confidence * 70 - track.range * 1.7)),
    reflectivity: Number(clamp(0.42 + track.confidence * 0.42 - track.range / 100, 0.2, 0.92).toFixed(2)),
    quality: track.confidence > 0.7 ? 'iyi' : 'zayıf',
  }));

  const radarReturns = tracks.map((track, index): RadarReturn => ({
    trackId: track.id,
    lane: track.lane,
    rangeM: round1(track.range + wave(elapsed, 0.55, index + 3) * realWorldSimulationConfig.radarRangeStdM),
    bearingDeg: bearingFromSystem({ x: track.x, y: track.y }),
    radialVelocityMps: round1(track.velocity + wave(elapsed, 0.25, index) * 0.12),
    snrDb: round1(realWorldSimulationConfig.radarSnrDb + track.confidence * 7 - realWorldSimulationConfig.packetLossPercent),
    rcsDbsm: round1(track.type === 'F16' ? 7.5 : track.type === 'Helikopter' ? 5.8 : track.type === 'Balistik Füze' ? 4.3 : 1.7),
  }));

  const fused = tracks.find((track) => track.candidate) ?? [...tracks].sort((a, b) => a.range - b.range)[0];
  const nearest = [...tracks].sort((a, b) => a.range - b.range)[0];

  return {
    stage,
    frameId,
    cameraDetections,
    lidarReturns,
    radarReturns: stage === 1 ? [] : radarReturns,
    fusedTargetId: fused?.id,
    nearestRangeM: nearest?.range,
    assumptionNotice: COMPETITION_COURSE.assumptionNotice,
    sourceLineRefs: [
      COMPETITION_COURSE.source.stage1,
      COMPETITION_COURSE.source.movingCourse,
      COMPETITION_COURSE.source.targetVisuals,
    ],
  };
}
