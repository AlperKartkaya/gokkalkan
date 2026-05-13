import { rangeGateFor } from './safetyGate';
import type { Stage, TargetType, Track } from './types';

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

export function generateRealWorldTelemetry(stage: Stage, elapsed: number, enabled: boolean): RealWorldTelemetry {
  const activeFactor = enabled ? 1 : 0.35;
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
  };
}

export function generateRealWorldTracks(stage: Stage, elapsed: number): Track[] {
  if (stage === 1) {
    const targets: Array<{ id: string; type: TargetType; range: number; x: number; y: number; w: number; h: number; confidence: number }> = [
      { id: 'M-1', type: 'Balistik Füze', range: 5, x: 18, y: 58, w: 9, h: 10, confidence: 0.91 },
      { id: 'M-2', type: 'Helikopter', range: 10, x: 43, y: 42, w: 9, h: 10, confidence: 0.87 },
      { id: 'M-3', type: 'F16', range: 15, x: 70, y: 55, w: 12, h: 10, confidence: 0.84 },
      { id: 'M-4', type: 'Mini/Micro İHA', range: 15, x: 60, y: 25, w: 8, h: 7, confidence: 0.79 },
    ];
    return targets.map((target, index) => ({
      ...target,
      x: clamp(target.x + jitter(elapsed, index + 1, 0.28), 8, 92),
      y: clamp(target.y + jitter(elapsed, index + 5, 0.22), 12, 86),
      lane: ((index % 3) + 1) as 1 | 2 | 3,
      friendFoe: 'Bilinmeyen',
      velocity: 0,
      direction: 'Sabit · saha jitter',
      rangeGate: rangeGateFor(target.type, target.range),
      candidate: index === 0,
    }));
  }

  if (stage === 2) {
    return [1, 2, 3].map((lane) => {
      const progress = (elapsed * (0.035 + lane * 0.004) + lane * 0.13) % 1;
      const type = lane === 2 ? 'Balistik Füze' : 'Mini/Micro İHA';
      const range = clamp(18 - progress * 15 + jitter(elapsed, lane + 2, 0.07), 3, 18.5);
      return {
        id: `S2-L${lane}`,
        x: clamp(7 + progress * 80 + jitter(elapsed, lane, 0.34), 6, 92),
        y: clamp(20 + lane * 18 + jitter(elapsed, lane + 6, 0.4), 16, 84),
        w: lane === 2 ? 10 : 8,
        h: lane === 2 ? 12 : 7,
        lane: lane as 1 | 2 | 3,
        type,
        friendFoe: 'Bilinmeyen',
        confidence: clamp(0.74 + Math.max(0, wave(elapsed, 0.7, lane)) * 0.18 - realWorldSimulationConfig.packetLossPercent / 200, 0.55, 0.96),
        range,
        velocity: Number((1.7 + lane * 0.46 + Math.max(0, wave(elapsed, 0.4, lane)) * 0.35).toFixed(1)),
        direction: 'A→B · yaklaşan',
        rangeGate: rangeGateFor(type, range),
        candidate: lane === 2 || progress > 0.42,
      };
    });
  }

  const enemyIndex = Math.floor(elapsed / 9) % 3;
  const types = ['F16', 'Helikopter', 'Mini/Micro İHA'] as const;
  return [0, 1, 2].map((index) => {
    const friendFoe = index === enemyIndex ? 'Düşman' : 'Dost';
    const type = types[(index + Math.floor(elapsed / 12)) % types.length];
    const validBaseRange = type === 'F16' ? 12 : type === 'Mini/Micro İHA' ? 6.5 : 8.5;
    const friendRange = 9 + index * 2;
    const range = Number((friendFoe === 'Düşman' ? validBaseRange + jitter(elapsed, index + 3, 0.08) : friendRange + jitter(elapsed, index + 8, 0.1)).toFixed(1));
    const gate = rangeGateFor(type, range);
    return {
      id: `S3-${friendFoe === 'Düşman' ? 'X' : 'F'}${index + 1}`,
      x: clamp(18 + index * 30 + wave(elapsed, 0.25 + index * 0.04, index) * 8 + jitter(elapsed, index, 0.22), 8, 92),
      y: clamp([30, 52, 72][index] + jitter(elapsed, index + 4, 0.5), 16, 84),
      w: type === 'F16' ? 13 : 9,
      h: type === 'Mini/Micro İHA' ? 7 : 10,
      lane: (index + 1) as 1 | 2 | 3,
      type,
      friendFoe,
      confidence: clamp(0.78 + Math.max(0, wave(elapsed, 0.62, index)) * 0.17, 0.62, 0.97),
      range,
      velocity: Number((1.1 + index * 0.34 + realWorldSimulationConfig.windMps * 0.04).toFixed(1)),
      direction: friendFoe === 'Düşman' ? 'Yaklaşıyor · tehdit' : 'Geçiş · dost',
      rangeGate: gate,
      candidate: friendFoe === 'Düşman' && gate === 'Uygun',
    };
  });
}
