export type Stage = 1 | 2 | 3;

export type Mode =
  | 'safe'
  | 'manual'
  | 'autonomous'
  | 'engagement'
  | 'blocked'
  | 'maintenance';

export type TargetType = 'F16' | 'Helikopter' | 'Balistik Füze' | 'Mini/Micro İHA';
export type FriendFoe = 'Dost' | 'Düşman' | 'Bilinmeyen';
export type RangeGate = 'Uygun' | 'Erken' | 'Geçersiz';

export type BlockReason =
  | 'ALLOWED'
  | 'BLOCKED_ESTOP'
  | 'BLOCKED_MOTION_ZONE'
  | 'BLOCKED_FIRE_ZONE'
  | 'BLOCKED_TARGET_GATE'
  | 'BLOCKED_MODE'
  | 'BLOCKED_CONNECTION'
  | 'BLOCKED_ZONE_CONFIG';

export type CommandIntent = 'move' | 'fire' | 'autonomous_move' | 'autonomous_engage';

export type EventType = 'command' | 'target' | 'safety' | 'fire' | 'mode' | 'telemetry';

export interface Track {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  lane: 1 | 2 | 3;
  type: TargetType;
  friendFoe: FriendFoe;
  confidence: number;
  range: number;
  velocity: number;
  direction: string;
  rangeGate: RangeGate;
  candidate: boolean;
}

export interface SafetyState {
  estop: boolean;
  motionZoneOk: boolean;
  fireZoneOk: boolean;
  targetGateOk: boolean;
  modeOk: boolean;
  connectionOk: boolean;
  blockReason: BlockReason;
}

export interface TelemetryEvent {
  id: number;
  timestamp: string;
  stage: Stage;
  mode: Mode;
  type: EventType;
  decision: string;
  reason: string;
}
