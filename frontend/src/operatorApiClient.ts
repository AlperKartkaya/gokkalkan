import type {
  CommandResult,
  FireIntent,
  ManualAimCommand,
  ModeRequest,
  OperatorSafetyState,
  OperatorCoursePrediction,
  OperatorSensorFrame,
  OperatorSensorHealth,
  OperatorTrackState,
  StageRequest,
} from './operatorContracts';
import type { Mode, Stage } from './types';

export interface OperatorTelemetryMetadata {
  path: string;
  exists: boolean;
  recordCount: number;
}

export interface VideoDemoSession {
  active: boolean;
  runId?: string;
  capability?: string;
  title?: string;
  startedAt?: string;
  physicalActionRequired?: string;
  physicalCapabilityVerified?: false;
  manualAnnotationIsDetection?: false;
  physicalOutput: false;
  error?: string;
}

export interface OperatorTelemetryLogRecord {
  recordId?: number;
  timestamp?: string;
  recordType: string;
  payload?: Record<string, unknown>;
  raw?: string;
}

export interface OperatorTelemetryEvent {
  id: number;
  timestamp: string;
  stage: Stage;
  mode: Mode;
  type: string;
  decision: string;
  reason: string;
  payload: Record<string, unknown>;
}

export interface OperatorApiSnapshot {
  app: string;
  version: number;
  snapshotVersion?: number;
  mode: Mode;
  stage: Stage;
  round: number;
  dryRun: boolean;
  runtimeMode?: 'SIM' | 'HIL' | 'LIVE';
  liveArmEnabled: boolean;
  tracks: OperatorTrackState[];
  sensorFrames?: OperatorSensorFrame[];
  sensorHealth?: OperatorSensorHealth;
  safety: OperatorSafetyState;
  commandResults: CommandResult[];
  events: OperatorTelemetryEvent[];
  physicalOutputEnabled: boolean;
  telemetry?: OperatorTelemetryMetadata;
  courseGeometry?: {
    datasetId: string;
    sourceRevision: number;
    sourceSha256: string;
    scope: 'POLIGON_INTERIOR_ONLY';
    outsideReturnIncluded: false;
    routeCount: 3;
    targetSpeedPriorMps: number;
    targetSpeedPriorAuthority: 'committee-provisional-not-spec';
    boundsCourseM: {
      westX: number;
      eastX: number;
      southY: number;
      northY: number;
    };
  };
  coursePredictions?: OperatorCoursePrediction[];
  turretPosition?: {
    panDeg: number;
    tiltDeg: number;
    valid?: boolean;
  };
  turretCalibration?: {
    calibrationId: string;
    status: string;
    calibratedAt: string | null;
    active: boolean;
    pan: { gain: number; offsetDeg: number; rmseDeg: number | null; sampleCount: number };
    tilt: { gain: number; offsetDeg: number; rmseDeg: number | null; sampleCount: number };
  };
  ballisticCompensation?: {
    calibrationId: string;
    status: string;
    active: boolean;
    rangeM: number | null;
    elevationCorrectionDeg: number | null;
    mode: 'HOLDOVER_RETICLE';
    automaticFireAdjustment: false;
    reason: string;
  };
  lidarReading?: {
    status: 'LIVE_ACCEPTED' | 'REJECTED';
    distanceM: number | null;
    trackId: string | null;
    timestamp: string;
    reason: string;
    source: 'tfa50-l-1d';
  } | null;
  maintenanceBudgetSec?: number;
  maintenanceUsedSec?: number;
  maintenanceRemainingBudgetSec?: number;
  missionElapsedSec?: number;
  missionRemainingSeconds?: number;
  missionTimeLimitSec?: number;
  missionTimerRunning?: boolean;
  missionTimeExpired?: boolean;
  missionCore?: {
    schemaVersion: number;
    runId: string;
    version: number;
    lastEventSequence: number;
    lifecycle: string;
    perceptionHealthy: boolean;
    faults: string[];
    updatedAtUtc: string;
    updatedAtMonotonicNs: number;
  };
  autonomousController?: {
    state: string;
    reason: string;
    attempts: Record<string, number>;
  };
  missionFlow?: {
    schemaVersion: number;
    status: 'IDLE' | 'ACTIVE' | 'PAUSED' | 'MAINTENANCE' | 'ESTOP_LATCHED' | 'ROUND_COMPLETE';
    stage: Stage;
    round: number;
    selectedTargetId: string | null;
    targetOrder: string[];
    completedTargetIds: string[];
    completedTargetCount: number;
    eligibleTargetCount: number;
    progressPercent: number;
    roundComplete: boolean;
    nextRound: number;
    previousStatus: string | null;
    lastTransitionReason: string;
    transitionSequence: number;
  };
}

export interface HardwareResult {
  adapter: string;
  commandId: string;
  kind: string;
  accepted: boolean;
  completed: boolean;
  physicalOutput: boolean;
  message: string;
  createdAt: string;
}

export type OperatorReadinessStatus = 'ready' | 'partial' | 'tbd' | 'blocked';

export interface OperatorReadinessItem {
  id: string;
  label: string;
  status: OperatorReadinessStatus;
  owner: string;
  evidence: string;
  nextStep: string;
  ktrInterface: string;
}

export interface OperatorReadinessReport {
  schemaVersion: number;
  generatedAt: string;
  summary: string;
  scoreBasis: string;
  readinessPercent: number;
  physicalOutputEnabled: boolean;
  mode: Mode;
  dryRun: boolean;
  items: OperatorReadinessItem[];
  nextCriticalActions: string[];
}

export interface OperatorSensorFrameBundle {
  schemaVersion: number;
  generatedAt: string;
  stage: Stage;
  round: number;
  sensorHealth: OperatorSensorHealth;
  frames: OperatorSensorFrame[];
  physicalOutputEnabled: boolean;
  replayOnly: true;
}

export interface OperatorTelemetryExport {
  schemaVersion: number;
  generatedAt: string;
  physicalOutputEnabled: boolean;
  unsafeReplayEvidence?: boolean;
  evidenceWarning?: string;
  telemetry: OperatorTelemetryMetadata;
  state: OperatorApiSnapshot;
  events: OperatorTelemetryEvent[];
  commandResults: CommandResult[];
  entries: OperatorTelemetryLogRecord[];
}

export interface OperatorReplayBundle {
  schemaVersion: number;
  generatedAt: string;
  sourceLogPath: string;
  physicalOutputEnabled: boolean;
  unsafeReplayEvidence?: boolean;
  evidenceWarning?: string;
  replayOnly: true;
  entries: OperatorTelemetryLogRecord[];
  events: Record<string, unknown>[];
  commandResults: CommandResult[];
  hardwareResults: HardwareResult[];
}

export interface OperatorTelemetryResetResponse {
  ok: boolean;
  physicalOutputEnabled: boolean;
  telemetry: OperatorTelemetryMetadata;
  state: OperatorApiSnapshot;
}

export interface OperatorApiCommandResponse {
  result: CommandResult;
  safety: OperatorSafetyState;
  hardwareResult?: HardwareResult | null;
  state: OperatorApiSnapshot;
}

export interface OperatorStateCommandResponse {
  accepted: boolean;
  state: OperatorApiSnapshot;
  physicalOutput: boolean;
  reason?: string;
}

export function normalizeOperatorApiBaseUrl(baseUrl: string): string {
  return baseUrl.trim().replace(/\/+$/, '');
}

export function operatorStateStreamUrl(baseUrl: string, afterVersion = 0): string {
  const after = Math.max(0, Math.trunc(afterVersion));
  return `${normalizeOperatorApiBaseUrl(baseUrl)}/state/stream?after=${after}`;
}

export async function fetchOperatorSnapshot(baseUrl: string): Promise<OperatorApiSnapshot> {
  return requestJson<OperatorApiSnapshot>(`${normalizeOperatorApiBaseUrl(baseUrl)}/state`);
}

export async function fetchOperatorReadiness(baseUrl: string): Promise<OperatorReadinessReport> {
  return requestJson<OperatorReadinessReport>(`${normalizeOperatorApiBaseUrl(baseUrl)}/readiness`);
}

export async function fetchVideoDemoSession(baseUrl: string): Promise<VideoDemoSession> {
  return requestJson<VideoDemoSession>(`${normalizeOperatorApiBaseUrl(baseUrl)}/video-demo/session`);
}

export async function fetchOperatorSensorFrames(baseUrl: string): Promise<OperatorSensorFrameBundle> {
  return requestJson<OperatorSensorFrameBundle>(`${normalizeOperatorApiBaseUrl(baseUrl)}/sensor-frames`);
}

export async function sendOperatorModeRequest(baseUrl: string, request: ModeRequest): Promise<OperatorApiCommandResponse> {
  return requestJson<OperatorApiCommandResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/mode`, request);
}

export async function sendOperatorStageRequest(baseUrl: string, request: StageRequest): Promise<OperatorApiCommandResponse> {
  return requestJson<OperatorApiCommandResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/stage`, request);
}

export async function sendOperatorManualAimCommand(baseUrl: string, request: ManualAimCommand): Promise<OperatorApiCommandResponse> {
  return requestJson<OperatorApiCommandResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/manual-aim`, request);
}

export async function sendOperatorFireIntent(baseUrl: string, request: FireIntent): Promise<OperatorApiCommandResponse> {
  return requestJson<OperatorApiCommandResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/fire-intent`, request);
}

export async function fetchOperatorTelemetryExport(baseUrl: string): Promise<OperatorTelemetryExport> {
  return requestJson<OperatorTelemetryExport>(`${normalizeOperatorApiBaseUrl(baseUrl)}/telemetry/export`);
}

export async function fetchOperatorReplay(baseUrl: string): Promise<OperatorReplayBundle> {
  return requestJson<OperatorReplayBundle>(`${normalizeOperatorApiBaseUrl(baseUrl)}/replay`);
}

export async function resetOperatorTelemetry(baseUrl: string): Promise<OperatorTelemetryResetResponse> {
  return requestJson<OperatorTelemetryResetResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/telemetry/reset`, {});
}

// ── Adım 3: Eksik endpoint'ler ──────────────────────────────────────────────

export interface OperatorEStopResponse {
  accepted: boolean;
  ok?: boolean;
  estop?: boolean;
  safety: import('./operatorContracts').OperatorSafetyState;
  state: OperatorApiSnapshot;
}

export interface HardwareHealthResponse {
  adapter: string;
  busConnected: boolean;
  picoReachable: boolean;
  dryRun: boolean;
  physicalOutputEnabled: boolean;
  commandCount?: number;
  transport?: 'usb_serial';
  serialPort?: string;
  serialConnected?: boolean;
  baudrate?: number;
  protocolVersion?: number;
  firmwareVersion?: string | null;
  encoderOk?: boolean;
  rejectedRxCount?: number;
  transportRejectedFrameCount?: number;
  lastStatusAgeSec?: number | null;
  mcuStatus?: Record<string, unknown>;
  lastHeartbeatAt?: string;
}

export interface TracksUpdatePayload {
  source: 'perception' | 'radar-lidar' | 'fused' | 'dry-run';
  tracks: Array<{
    trackId: string;
    targetType?: string;
    friendFoe?: string;
    rangeM: number;
    bearingDeg: number;
    confidence: number;
  }>;
}

export interface TracksUpdateResponse {
  ok: boolean;
  count: number;
  source: string;
  perceptionConnected: boolean;
  error?: string;
}

/** POST /estop — yazılım E-Stop tetikleyici (ikincil güvence; fiziksel buton birincildir). */
export async function sendOperatorEStop(baseUrl: string, payload: { active: boolean }): Promise<OperatorEStopResponse> {
  return requestJson<OperatorEStopResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/estop`, payload);
}

/** GET /hardware/health — USB CDC bağlantısı ve Pico MCU durumu. */
export async function fetchHardwareHealth(baseUrl: string): Promise<HardwareHealthResponse> {
  return requestJson<HardwareHealthResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/hardware/health`);
}

/** POST /tracks/update — Perception bridge veya sensör adapter'ından canlı track besleme. */
export async function sendTracksUpdate(baseUrl: string, payload: TracksUpdatePayload): Promise<TracksUpdateResponse> {
  return requestJson<TracksUpdateResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/tracks/update`, payload);
}

/** POST /maintenance — Şartname v1.4: bakım modu başlat (bütçe kontrolü backend tarafında). */
export async function sendMaintenanceRequest(baseUrl: string): Promise<OperatorStateCommandResponse> {
  return requestJson<OperatorStateCommandResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/maintenance`, {});
}

/** POST /maintenance/end — Bakımı bitir; önceki aktif görev ve timer backend tarafından sürdürülür. */
export async function sendMaintenanceEnd(baseUrl: string): Promise<OperatorStateCommandResponse> {
  return requestJson<OperatorStateCommandResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/maintenance/end`, {});
}

/** Controlled soft stop; does not replace or clear the physical E-Stop. */
export async function sendMissionStop(baseUrl: string): Promise<OperatorStateCommandResponse> {
  return requestJson<OperatorStateCommandResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/mission/stop`, {
    reason: 'operator-panel',
  });
}

/** Resume only a backend PAUSED state; E-Stop remains independently latched. */
export async function sendMissionResume(baseUrl: string): Promise<OperatorStateCommandResponse> {
  return requestJson<OperatorStateCommandResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/mission/resume`, {
    reason: 'operator-panel',
  });
}

async function requestJson<T>(url: string, body?: unknown): Promise<T> {
  const response = await fetch(url, {
    method: body ? 'POST' : 'GET',
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (!response.ok) {
    throw new Error(`Operator API ${response.status}: ${response.statusText}`);
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new Error(`Operator API ${response.status}: JSON yanıtı okunamadı`);
  }
}
