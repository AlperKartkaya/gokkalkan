import { rangeGateFor } from './safetyGate';
import type { Stage, TargetType, Track } from './types';

const types: TargetType[] = ['F16', 'Helikopter', 'Balistik Füze', 'Mini/Micro İHA'];

export const targetOrder: TargetType[] = ['Balistik Füze', 'Helikopter', 'F16', 'Mini/Micro İHA'];

function oscillate(t: number, speed: number, offset: number) {
  return (Math.sin(t * speed + offset) + 1) / 2;
}

export function generateTracks(stage: Stage, elapsed: number): Track[] {
  if (stage === 1) {
    return targetOrder.map((type, index) => {
      const ranges = [5, 10, 15, 15];
      const x = [18, 44, 70, 60][index];
      const y = [60, 42, 55, 25][index] + Math.sin(elapsed * 0.6 + index) * 1.2;
      const range = ranges[index];
      return {
        id: `M-${index + 1}`,
        x,
        y,
        w: index === 2 ? 12 : 9,
        h: index === 3 ? 7 : 10,
        lane: ((index % 3) + 1) as 1 | 2 | 3,
        type,
        friendFoe: 'Bilinmeyen',
        confidence: 0.88 - index * 0.04,
        range,
        velocity: 0,
        direction: 'Sabit',
        rangeGate: rangeGateFor(type, range),
        candidate: index === 0,
      };
    });
  }

  if (stage === 2) {
    return [1, 2, 3].map((lane) => {
      const progress = (elapsed * (0.025 + lane * 0.004) + lane * 0.18) % 1;
      const x = 8 + progress * 78;
      const y = 22 + lane * 18 + Math.sin(elapsed * 0.9 + lane) * 1.8;
      const type = lane === 2 ? 'Balistik Füze' : 'Mini/Micro İHA';
      const range = 18 - progress * 15;
      return {
        id: `S2-L${lane}`,
        x,
        y,
        w: lane === 2 ? 10 : 8,
        h: lane === 2 ? 12 : 7,
        lane: lane as 1 | 2 | 3,
        type,
        friendFoe: 'Bilinmeyen',
        confidence: 0.72 + oscillate(elapsed, 0.7, lane) * 0.22,
        range,
        velocity: 1.8 + lane * 0.5,
        direction: 'A→B',
        rangeGate: rangeGateFor(type, range),
        candidate: lane === 2 || progress > 0.45,
      };
    });
  }

  return [0, 1, 2].map((index) => {
    const progress = (elapsed * (0.018 + index * 0.003) + index * 0.21) % 1;
    const enemyIndex = Math.floor(elapsed / 10) % 3;
    const type = types[(Math.floor(elapsed / 7) + index) % types.length];
    const range = 19 - progress * 17;
    const friendFoe = index === enemyIndex ? 'Düşman' : 'Dost';
    const x = 12 + progress * 74;
    const y = [30, 52, 72][index] + Math.sin(elapsed * 0.55 + index) * 2;
    return {
      id: `S3-${friendFoe === 'Düşman' ? 'X' : 'F'}${index + 1}`,
      x,
      y,
      w: type === 'F16' ? 13 : 9,
      h: type === 'Mini/Micro İHA' ? 7 : 10,
      lane: (index + 1) as 1 | 2 | 3,
      type,
      friendFoe,
      confidence: 0.76 + oscillate(elapsed, 0.6, index) * 0.2,
      range,
      velocity: 1.2 + index * 0.35,
      direction: friendFoe === 'Düşman' ? 'Yaklaşıyor' : 'Geçiş',
      rangeGate: rangeGateFor(type, range),
      candidate: friendFoe === 'Düşman' && rangeGateFor(type, range) === 'Uygun',
    };
  });
}
