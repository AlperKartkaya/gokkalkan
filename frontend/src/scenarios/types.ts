import type { BlockReason, FriendFoe, Mode, Stage, TargetType } from '../types';

export type ScenarioEventKind =
  | 'setup'
  | 'target_launch'
  | 'track'
  | 'manual_move'
  | 'autonomous_move'
  | 'arm'
  | 'fire'
  | 'hit'
  | 'miss'
  | 'maintenance_request'
  | 'maintenance_pause'
  | 'maintenance_resume'
  | 'round_end'
  | 'stage_complete'
  | 'safety';

export type ScenarioActor = 'hakem' | 'operatör' | 'Gökkalkan' | 'hedef' | 'güvenlik';

export interface ScenarioWaypoint {
  second: number;
  x: number;
  y: number;
  range: number;
  velocity?: number;
  confidence?: number;
}

export interface ScenarioTarget {
  id: string;
  type: TargetType;
  friendFoe: FriendFoe;
  lane: 1 | 2 | 3;
  round?: number;
  spawnSecond: number;
  despawnSecond: number;
  width: number;
  height: number;
  route: ScenarioWaypoint[];
  candidateFrom?: number;
  candidateUntil?: number;
  notes: string;
}

export interface ScenarioEvent {
  second: number;
  kind: ScenarioEventKind;
  actor: ScenarioActor;
  title: string;
  detail: string;
  targetId?: string;
  mode?: Mode;
  autoRunning?: boolean;
  round?: number;
  result?: 'hit' | 'miss' | 'blocked';
  points?: number;
  panAngle?: number;
  tiltAngle?: number;
  blockReason?: BlockReason;
  maintenanceDurationSeconds?: number;
}

export interface StageScenario {
  id: string;
  stage: Stage;
  title: string;
  durationSeconds: number;
  defaultMode: Mode;
  autoRunning: boolean;
  sourceRefs: string[];
  assumptions: string[];
  routeAdjustableNote: string;
  targets: ScenarioTarget[];
  events: ScenarioEvent[];
}
