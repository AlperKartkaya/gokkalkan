import type { BlockReason, FriendFoe, Mode, Stage, TargetType } from './types';

export type OperatorConnectionState = 'offline' | 'dry-run' | 'live';
export type OperatorCommandKind = 'ModeRequest' | 'ManualAimCommand' | 'FireIntent';
export type OperatorBlockReason = BlockReason | 'BLOCKED_ARMING' | 'BLOCKED_BACKEND' | 'BLOCKED_SENSOR';

export interface OperatorPanelConfig {
  apiBaseUrl: string;
  connectionState: OperatorConnectionState;
  dryRun: boolean;
  liveArmEnabled: boolean;
}

export interface ModeRequest {
  kind: 'ModeRequest';
  requestedMode: Mode;
  operatorId: string;
  timestamp: string;
  reason: string;
  dryRun: boolean;
}

export interface ManualAimCommand {
  kind: 'ManualAimCommand';
  panDeltaDeg: number;
  tiltDeltaDeg: number;
  rateLimitDegPerSec: number;
  deadmanActive: boolean;
  dryRun: boolean;
}

export interface FireIntent {
  kind: 'FireIntent';
  targetId: string;
  stage: Stage;
  round: number;
  operatorConfirm: boolean;
  dryRun: boolean;
  requestedAt: string;
}

export interface OperatorTrackState {
  trackId: string;
  stage: Stage;
  round: number;
  targetType: TargetType;
  friendFoe: FriendFoe;
  rangeM: number;
  bearingDeg: number;
  confidence: number;
  source: 'perception' | 'radar-lidar' | 'fused' | 'dry-run';
  updatedAt: string;
}

export interface OperatorSafetyState {
  estop: boolean;
  motionZoneOk: boolean;
  fireZoneOk: boolean;
  targetGateOk: boolean;
  modeOk: boolean;
  backendConnected: boolean;
  perceptionConnected: boolean;
  sensorAdapterConnected: boolean;
  dryRun: boolean;
  liveArmEnabled: boolean;
  blockReason: OperatorBlockReason;
  explanation: string;
}

export interface CommandResult {
  commandId: string;
  kind: OperatorCommandKind;
  accepted: boolean;
  completed: boolean;
  dryRun: boolean;
  safetyBlockReason: OperatorBlockReason;
  message: string;
  createdAt: string;
}

export const operatorBlockCopy: Record<OperatorBlockReason, string> = {
  ALLOWED: 'Komut niyeti güvenli dry-run kanalında kabul edilebilir.',
  BLOCKED_ESTOP: 'Acil Durdur aktif; hareket ve atış niyeti kilitli.',
  BLOCKED_MOTION_ZONE: 'Harekete yasak alan ihlali var.',
  BLOCKED_FIRE_ZONE: 'Atışa yasak alan ihlali var.',
  BLOCKED_TARGET_GATE: 'Hedef, dost/düşman veya menzil kapısı uygun değil.',
  BLOCKED_MODE: 'Aktif mod bu komut için uygun değil.',
  BLOCKED_CONNECTION: 'Bağlantı sağlığı komut için yeterli değil.',
  BLOCKED_ARMING: 'Canlı arming kapalı; fiziksel çıkış yetkisi yok.',
  BLOCKED_BACKEND: 'Backend bağlantısı yok; gerçek komut gönderilemez.',
  BLOCKED_SENSOR: 'Perception veya sensör adapter sağlığı doğrulanmadı.',
};

export function evaluateOperatorSafety(input: Omit<OperatorSafetyState, 'blockReason' | 'explanation'>): OperatorSafetyState {
  let blockReason: OperatorBlockReason = 'ALLOWED';

  if (input.estop) blockReason = 'BLOCKED_ESTOP';
  else if (!input.backendConnected) blockReason = 'BLOCKED_BACKEND';
  else if (!input.dryRun && !input.liveArmEnabled) blockReason = 'BLOCKED_ARMING';
  else if (!input.motionZoneOk) blockReason = 'BLOCKED_MOTION_ZONE';
  else if (!input.fireZoneOk) blockReason = 'BLOCKED_FIRE_ZONE';
  else if (!input.modeOk) blockReason = 'BLOCKED_MODE';
  else if (!input.targetGateOk) blockReason = 'BLOCKED_TARGET_GATE';
  else if (!input.dryRun && (!input.perceptionConnected || !input.sensorAdapterConnected)) blockReason = 'BLOCKED_SENSOR';

  return {
    ...input,
    blockReason,
    explanation: operatorBlockCopy[blockReason],
  };
}

export function canSendFireIntent(safety: OperatorSafetyState, selectedTargetId: string | undefined): boolean {
  return Boolean(selectedTargetId) && safety.blockReason === 'ALLOWED' && (safety.dryRun || safety.liveArmEnabled);
}

export function makeFireIntent(params: { targetId: string; stage: Stage; round: number; dryRun: boolean; now?: Date }): FireIntent {
  return {
    kind: 'FireIntent',
    targetId: params.targetId,
    stage: params.stage,
    round: params.round,
    operatorConfirm: true,
    dryRun: params.dryRun,
    requestedAt: (params.now ?? new Date()).toISOString(),
  };
}

export function makeCommandResult(params: {
  commandId: string;
  kind: OperatorCommandKind;
  accepted: boolean;
  dryRun: boolean;
  safetyBlockReason: OperatorBlockReason;
  createdAt?: Date;
}): CommandResult {
  const acceptedText = params.accepted
    ? params.dryRun
      ? 'Dry-run komut niyeti kaydedildi; fiziksel çıkış üretilmedi.'
      : 'Komut backend tarafından kabul edildi.'
    : operatorBlockCopy[params.safetyBlockReason];

  return {
    commandId: params.commandId,
    kind: params.kind,
    accepted: params.accepted,
    completed: params.accepted && params.dryRun,
    dryRun: params.dryRun,
    safetyBlockReason: params.safetyBlockReason,
    message: acceptedText,
    createdAt: (params.createdAt ?? new Date()).toISOString(),
  };
}
