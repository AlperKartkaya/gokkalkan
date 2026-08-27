import type { BlockReason, FriendFoe, Mode, Stage, TargetType } from './types';

export type OperatorConnectionState = 'offline' | 'dry-run' | 'hil' | 'live';
export type OperatorCommandKind = 'ModeRequest' | 'StageRequest' | 'ManualAimCommand' | 'FireIntent';
export type OperatorBlockReason = BlockReason | 'BLOCKED_ARMING' | 'BLOCKED_BACKEND' | 'BLOCKED_SENSOR' | 'BLOCKED_INVALID_COMMAND';
export type OperatorSensorSource = 'radar' | 'lidar' | 'camera' | 'fusion' | 'dry-run';

export const MANUAL_AIM_STEP_DEG = 2;
export const MANUAL_AIM_RATE_LIMIT_DEG_PER_SEC = 12;
export const MAX_MANUAL_AIM_DELTA_DEG = 11.25;
export const MAX_MANUAL_AIM_RATE_LIMIT_DEG_PER_SEC = 30;

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

export interface StageRequest {
  kind: 'StageRequest';
  stage: Stage;
  round: number;
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
  targetType: TargetType | 'Bilinmeyen' | 'Balon';
  friendFoe: FriendFoe;
  rangeM: number;
  bearingDeg: number;
  confidence: number;
  typeConfidence?: number | null;
  friendFoeConfidence?: number | null;
  confidenceSemantics?: 'JOINT_PRESENTATION_CLASS' | 'HSV_TRACK_STABILITY' | 'LEGACY_COMBINED' | string;
  source: 'perception' | 'radar-lidar' | 'fused' | 'dry-run';
  updatedAt: string;
  bboxPx?: [number, number, number, number] | null;
  frameSizePx?: [number, number] | null;
  objectRole?: 'target' | 'balloon';
  fireCandidate?: boolean;
  courseState?: OperatorCourseTrackState | null;
}

export interface OperatorCourseTrackState {
  trackId: string;
  routeId: 'POLIGON_ROUTE_1' | 'POLIGON_ROUTE_2' | 'POLIGON_ROUTE_3' | null;
  routeNumber: 1 | 2 | 3 | null;
  passIndex: number;
  lifecycle: 'ACTIVE_IN_POLIGON' | 'PREDICTED_IN_POLIGON' | 'OUTSIDE_POLIGON';
  sM: number;
  speedMps: number;
  speedSource: 'PRIOR' | 'MEASURED' | 'UNAVAILABLE';
  projectedCourseM: { x: number; y: number } | null;
  projectionResidualM: number | null;
  tangentCourseDeg: number | null;
  insidePoligon: boolean;
  predictionValid: boolean;
}

export interface OperatorCoursePrediction extends OperatorCourseTrackState {
  lifecycle: 'PREDICTED_IN_POLIGON';
  predictedRangeM: number;
  predictedBearingDeg: number;
  use: 'CAMERA_REACQUISITION_ONLY';
  fireAuthoritative: false;
}

export interface OperatorSensorFrame {
  frameId: string;
  stage: Stage;
  round: number;
  trackId: string;
  sensor: OperatorSensorSource;
  timestamp: string;
  rangeM: number;
  bearingDeg: number;
  elevationDeg: number;
  radialVelocityMps: number;
  rcsDbsm: number | null;
  snrDb: number | null;
  pointCount: number;
  quality: number;
  targetType: TargetType | 'Bilinmeyen';
  friendFoe: FriendFoe;
  classificationConfidence: number;
  rangeGate: string;
  recommendation: string;
  sourceDataset: string;
  replayOnly: boolean;
  rawSampleRef: string;
}

export interface OperatorSensorHealth {
  schemaVersion: number;
  status: 'offline' | 'replay' | 'live' | 'empty';
  adapterConnected: boolean;
  perceptionConnected: boolean;
  replayOnly: boolean;
  sourceDataset: string;
  latestFrameAt: string;
  frameCount: number;
  physicalOutputEnabled: boolean;
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
  physicalOutput?: boolean;
  hardwareResultCode?: string;
  blockReason?: string;
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
  BLOCKED_INVALID_COMMAND: 'Komut alanları güvenli sınırlar içinde değil.',
  BLOCKED_ZONE_CONFIG: 'Yasak bölge yapılandırması geçersiz; komut güvenli biçimde reddedildi.',
};

export function stageRoundLimit(stage: Stage): number {
  if (stage === 1) return 4;
  if (stage === 2) return 4;
  return 8;
}

export function stageExpectedMode(stage: Stage): Mode {
  return stage === 1 ? 'manual' : 'autonomous';
}

export function stageMissionCopy(stage: Stage): string {
  if (stage === 1) return 'Aşama 1 · Manuel Mod zorunlu · 5/10/15 m durağan hedef sırası';
  if (stage === 2) return 'Aşama 2 · Otonom takip/imha · 4 resmi tur · sınıflandırma zorunlu değil';
  return 'Aşama 3 · Otonom dost/düşman ayrımı · 8 tur · hedef tipine göre menzil kapısı';
}

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

export function canSendManualAim(params: { stage: Stage; mode: Mode; deadmanActive: boolean; dryRun: boolean; liveArmEnabled: boolean; backendConnected: boolean }): boolean {
  return params.stage === 1 && params.mode === 'manual' && params.deadmanActive && params.backendConnected && (params.dryRun || params.liveArmEnabled);
}

export function isManualAimPayloadSafe(command: ManualAimCommand): boolean {
  return (
    Number.isFinite(command.panDeltaDeg)
    && Number.isFinite(command.tiltDeltaDeg)
    && Number.isFinite(command.rateLimitDegPerSec)
    && Math.abs(command.panDeltaDeg) <= MAX_MANUAL_AIM_DELTA_DEG
    && Math.abs(command.tiltDeltaDeg) <= MAX_MANUAL_AIM_DELTA_DEG
    && command.rateLimitDegPerSec > 0
    && command.rateLimitDegPerSec <= MAX_MANUAL_AIM_RATE_LIMIT_DEG_PER_SEC
  );
}

export function makeManualAimCommand(params: {
  panDeltaDeg: number;
  tiltDeltaDeg: number;
  deadmanActive: boolean;
  dryRun: boolean;
  rateLimitDegPerSec?: number;
}): ManualAimCommand {
  return {
    kind: 'ManualAimCommand',
    panDeltaDeg: params.panDeltaDeg,
    tiltDeltaDeg: params.tiltDeltaDeg,
    rateLimitDegPerSec: params.rateLimitDegPerSec ?? MANUAL_AIM_RATE_LIMIT_DEG_PER_SEC,
    deadmanActive: params.deadmanActive,
    dryRun: params.dryRun,
  };
}

export function makeStageRequest(params: { stage: Stage; round: number; dryRun: boolean; operatorId?: string; reason?: string; now?: Date }): StageRequest {
  if (!Number.isInteger(params.stage) || !Number.isInteger(params.round)) {
    throw new Error('StageRequest stage and round must be exact integers.');
  }
  if (params.round < 1 || params.round > stageRoundLimit(params.stage)) {
    throw new Error(`StageRequest round ${params.round} is outside Aşama ${params.stage} bounds.`);
  }

  return {
    kind: 'StageRequest',
    stage: params.stage,
    round: params.round,
    operatorId: params.operatorId ?? 'OP-UI-1',
    timestamp: (params.now ?? new Date()).toISOString(),
    reason: params.reason ?? 'operator-stage-control',
    dryRun: params.dryRun,
  };
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
    physicalOutput: false,
  };
}
