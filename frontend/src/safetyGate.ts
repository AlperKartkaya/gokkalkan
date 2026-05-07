import type { BlockReason, Mode, SafetyState, Stage, Track } from './types';

export function rangeGateFor(type: Track['type'], range: number): Track['rangeGate'] {
  if (type === 'F16') {
    if (range > 15) return 'Erken';
    return range >= 10 && range <= 15 ? 'Uygun' : 'Geçersiz';
  }
  if (type === 'Mini/Micro İHA') return range <= 15 ? 'Uygun' : 'Erken';
  if (range > 15) return 'Erken';
  return range >= 5 && range <= 15 ? 'Uygun' : 'Geçersiz';
}

export function evaluateSafety(params: {
  stage: Stage;
  mode: Mode;
  base: Omit<SafetyState, 'blockReason'>;
  selectedTrack?: Track;
  command: 'move' | 'fire' | 'autonomous';
}): SafetyState {
  const { stage, mode, base, selectedTrack, command } = params;
  let blockReason: BlockReason = 'ALLOWED';

  if (base.estop) blockReason = 'BLOCKED_ESTOP';
  else if (!base.connectionOk) blockReason = 'BLOCKED_CONNECTION';
  else if (command === 'move' && !base.motionZoneOk) blockReason = 'BLOCKED_MOTION_ZONE';
  else if (command === 'fire' && !base.fireZoneOk) blockReason = 'BLOCKED_FIRE_ZONE';
  else if (!base.modeOk || (stage === 1 && mode !== 'manual' && command === 'fire')) blockReason = 'BLOCKED_MODE';
  else if (command === 'fire' && stage === 3) {
    if (!selectedTrack || selectedTrack.friendFoe !== 'Düşman' || selectedTrack.rangeGate !== 'Uygun' || !base.targetGateOk) {
      blockReason = 'BLOCKED_TARGET_GATE';
    }
  }

  return { ...base, blockReason };
}

export const blockCopy: Record<BlockReason, string> = {
  ALLOWED: 'İzin var',
  BLOCKED_ESTOP: 'Acil Durdur aktif',
  BLOCKED_MOTION_ZONE: 'Harekete yasak alan',
  BLOCKED_FIRE_ZONE: 'Atışa yasak alan',
  BLOCKED_TARGET_GATE: 'Dost/menzil kapısı',
  BLOCKED_MODE: 'Mod uyumsuz',
  BLOCKED_CONNECTION: 'Bağlantı yok',
};
