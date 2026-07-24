import type {
  CommandResult,
  FireIntent,
  ManualAimCommand,
  ModeRequest,
  OperatorSafetyState,
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
  liveArmEnabled: boolean;
  tracks: OperatorTrackState[];
  sensorFrames?: OperatorSensorFrame[];
  sensorHealth?: OperatorSensorHealth;
  safety: OperatorSafetyState;
  commandResults: CommandResult[];
  events: OperatorTelemetryEvent[];
  physicalOutputEnabled: boolean;
  telemetry?: OperatorTelemetryMetadata;
  maintenanceBudgetSec?: number;
  maintenanceUsedSec?: number;
  maintenanceRemainingBudgetSec?: number;
  missionElapsedSec?: number;
  missionRemainingSeconds?: number;
  missionTimeLimitSec?: number;
  missionTimerRunning?: boolean;
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
  ok: boolean;
  estop: boolean;
  safety: import('./operatorContracts').OperatorSafetyState;
}

export interface HardwareHealthResponse {
  adapter: string;
  busConnected: boolean;
  picoReachable: boolean;
  dryRun: boolean;
  physicalOutputEnabled: boolean;
  commandCount?: number;
  // CanMcuAdapter'dan gelen ek alanlar
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

/** GET /hardware/health — CAN bağlantısı ve Pico MCU durumu. */
export async function fetchHardwareHealth(baseUrl: string): Promise<HardwareHealthResponse> {
  return requestJson<HardwareHealthResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/hardware/health`);
}

/** POST /tracks/update — Perception bridge veya sensör adapter'ından canlı track besleme. */
export async function sendTracksUpdate(baseUrl: string, payload: TracksUpdatePayload): Promise<TracksUpdateResponse> {
  return requestJson<TracksUpdateResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/tracks/update`, payload);
}

/** POST /maintenance — Şartname v1.3: bakım modu başlat (bütçe kontrolü backend tarafında). */
export async function sendMaintenanceRequest(baseUrl: string): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>(`${normalizeOperatorApiBaseUrl(baseUrl)}/maintenance`, {});
}

/** POST /maintenance/end — Bakım süresini sonlandır; safe moda dön. */
export async function sendMaintenanceEnd(baseUrl: string): Promise<Record<string, unknown>> {
  return requestJson<Record<string, unknown>>(`${normalizeOperatorApiBaseUrl(baseUrl)}/maintenance/end`, {});
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
