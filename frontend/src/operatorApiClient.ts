import type { CommandResult, FireIntent, ManualAimCommand, ModeRequest, OperatorSafetyState, OperatorTrackState } from './operatorContracts';
import type { Mode, Stage } from './types';

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

export async function sendOperatorModeRequest(baseUrl: string, request: ModeRequest): Promise<OperatorApiCommandResponse> {
  return requestJson<OperatorApiCommandResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/mode`, request);
}

export async function sendOperatorManualAimCommand(baseUrl: string, request: ManualAimCommand): Promise<OperatorApiCommandResponse> {
  return requestJson<OperatorApiCommandResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/manual-aim`, request);
}

export async function sendOperatorFireIntent(baseUrl: string, request: FireIntent): Promise<OperatorApiCommandResponse> {
  return requestJson<OperatorApiCommandResponse>(`${normalizeOperatorApiBaseUrl(baseUrl)}/fire-intent`, request);
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

  return response.json() as Promise<T>;
}
