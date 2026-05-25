import type { CommandResult, FireIntent, ManualAimCommand, ModeRequest, OperatorSafetyState, OperatorTrackState } from './operatorContracts';
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
  mode: Mode;
  stage: Stage;
  round: number;
  dryRun: boolean;
  liveArmEnabled: boolean;
  tracks: OperatorTrackState[];
  safety: OperatorSafetyState;
  commandResults: CommandResult[];
  events: OperatorTelemetryEvent[];
  physicalOutputEnabled: boolean;
  telemetry?: OperatorTelemetryMetadata;
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

export interface OperatorTelemetryExport {
  schemaVersion: number;
  generatedAt: string;
  physicalOutputEnabled: boolean;
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

export async function fetchOperatorSnapshot(baseUrl: string): Promise<OperatorApiSnapshot> {
  return requestJson<OperatorApiSnapshot>(`${normalizeOperatorApiBaseUrl(baseUrl)}/state`);
}

export async function fetchOperatorReadiness(baseUrl: string): Promise<OperatorReadinessReport> {
  return requestJson<OperatorReadinessReport>(`${normalizeOperatorApiBaseUrl(baseUrl)}/readiness`);
}

export async function sendOperatorModeRequest(baseUrl: string, request: ModeRequest): Promise<OperatorApiCommandResponse> {
  return requestJson<OperatorApiCommandResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/mode`, request);
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
