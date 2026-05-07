import type { BlockReason, CommandIntent, Mode, SafetyState, Stage, Track } from './types';

export function rangeGateFor(type: Track['type'], range: number): Track['rangeGate'] {
  if (type === 'F16') {
    if (range > 15) return 'Erken';
    return range >= 10 && range <= 15 ? 'Uygun' : 'Geçersiz';
  }
  if (type === 'Mini/Micro İHA') return range <= 15 ? 'Uygun' : 'Erken';
  if (range > 15) return 'Erken';
  return range >= 5 && range <= 15 ? 'Uygun' : 'Geçersiz';
}

export function evaluateSystemHealth(base: Omit<SafetyState, 'blockReason'>): SafetyState {
  if (base.estop) return { ...base, blockReason: 'BLOCKED_ESTOP' };
  if (!base.connectionOk) return { ...base, blockReason: 'BLOCKED_CONNECTION' };
  return { ...base, blockReason: 'ALLOWED' };
}

function isMoveIntent(command: CommandIntent) {
  return command === 'move' || command === 'autonomous_move';
}

function isEngageIntent(command: CommandIntent) {
  return command === 'fire' || command === 'autonomous_engage';
}

function isModeAllowed(stage: Stage, mode: Mode, command: CommandIntent) {
  if (mode === 'safe' || mode === 'maintenance' || mode === 'blocked') return false;
  if (stage === 1) return mode === 'manual' && command === 'fire';
  if (command === 'autonomous_engage') return mode === 'autonomous' || mode === 'engagement';
  if (command === 'fire') return mode === 'manual' || mode === 'engagement';
  return mode === 'manual' || mode === 'autonomous' || mode === 'engagement';
}

export function evaluateSafety(params: {
  stage: Stage;
  mode: Mode;
  base: Omit<SafetyState, 'blockReason'>;
  selectedTrack?: Track;
  command: CommandIntent;
}): SafetyState {
  const { stage, mode, base, selectedTrack, command } = params;
  let blockReason: BlockReason = 'ALLOWED';

  const health = evaluateSystemHealth(base);
  if (health.blockReason !== 'ALLOWED') blockReason = health.blockReason;
  else if (isMoveIntent(command) && !base.motionZoneOk) blockReason = 'BLOCKED_MOTION_ZONE';
  else if (isEngageIntent(command) && !base.fireZoneOk) blockReason = 'BLOCKED_FIRE_ZONE';
  else if (!base.modeOk || !isModeAllowed(stage, mode, command)) blockReason = 'BLOCKED_MODE';
  else if (isEngageIntent(command) && stage === 3) {
    if (!selectedTrack || selectedTrack.friendFoe !== 'Düşman' || selectedTrack.rangeGate !== 'Uygun' || !base.targetGateOk) {
      blockReason = 'BLOCKED_TARGET_GATE';
    }
  } else if (isEngageIntent(command) && !base.targetGateOk) {
    blockReason = 'BLOCKED_TARGET_GATE';
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
