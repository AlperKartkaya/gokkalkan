import { rangeGateFor } from '../safetyGate';
import type { BlockReason, Mode, Stage, Track } from '../types';
import { stage1Scenario } from './stage1';
import { stage2Scenario } from './stage2';
import { stage3Scenario } from './stage3';
import type { ScenarioEvent, ScenarioTarget, ScenarioWaypoint, StageScenario } from './types';

export type { ScenarioEvent, ScenarioTarget, StageScenario } from './types';

export const STAGE_SCENARIOS: Record<Stage, StageScenario> = {
  1: stage1Scenario,
  2: stage2Scenario,
  3: stage3Scenario,
};

export interface ScenarioFrame {
  second: number;
  stage: Stage;
  mode: Mode;
  autoRunning: boolean;
  paused: boolean;
  selectedTargetId?: string;
  panAngle: number;
  tiltAngle: number;
  score: number;
  hits: number;
  misses: number;
  round: number;
  roundHits: number;
  currentTarget: number;
  enemyHitThisRound: boolean;
  blockReason: BlockReason;
  status: string;
  currentEvents: ScenarioEvent[];
  nextEvents: ScenarioEvent[];
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function interpolateRoute(route: ScenarioWaypoint[], second: number): ScenarioWaypoint {
  if (route.length === 0) return { second, x: 50, y: 50, range: 10 };
  if (second <= route[0].second) return route[0];
  for (let index = 0; index < route.length - 1; index += 1) {
    const from = route[index];
    const to = route[index + 1];
    if (second <= to.second) {
      const ratio = (second - from.second) / Math.max(1, to.second - from.second);
      return {
        second,
        x: from.x + (to.x - from.x) * ratio,
        y: from.y + (to.y - from.y) * ratio,
        range: from.range + (to.range - from.range) * ratio,
        velocity: (from.velocity ?? to.velocity ?? 0) + ((to.velocity ?? from.velocity ?? 0) - (from.velocity ?? to.velocity ?? 0)) * ratio,
        confidence: (from.confidence ?? to.confidence ?? 0.8) + ((to.confidence ?? from.confidence ?? 0.8) - (from.confidence ?? to.confidence ?? 0.8)) * ratio,
      };
    }
  }
  return route[route.length - 1];
}

function targetResolvedByHit(scenario: StageScenario, target: ScenarioTarget, second: number) {
  return scenario.events.some((event) => event.targetId === target.id && event.result === 'hit' && event.second < second);
}

function activeTargets(scenario: StageScenario, second: number) {
  return scenario.targets.filter((target) => target.spawnSecond <= second && target.despawnSecond >= second && !targetResolvedByHit(scenario, target, second));
}

export function generateScenarioTracks(scenario: StageScenario, second: number): Track[] {
  return activeTargets(scenario, second).map((target) => {
    const waypoint = interpolateRoute(target.route, second);
    const range = Number(waypoint.range.toFixed(1));
    const gate = rangeGateFor(target.type, range);
    const inCandidateWindow = (target.candidateFrom ?? target.spawnSecond) <= second && (target.candidateUntil ?? target.despawnSecond) >= second;
    const candidate = inCandidateWindow && (scenario.stage !== 3 || target.friendFoe === 'Düşman') && gate === 'Uygun';
    return {
      id: target.id,
      x: clamp(waypoint.x, 5, 94),
      y: clamp(waypoint.y, 8, 92),
      w: target.width,
      h: target.height,
      lane: target.lane,
      type: target.type,
      friendFoe: target.friendFoe,
      confidence: waypoint.confidence ?? 0.82,
      range,
      velocity: waypoint.velocity ?? 0,
      direction: scenario.stage === 1 ? target.notes : `A→B · ${target.notes}`,
      rangeGate: gate,
      candidate,
    };
  });
}

function latestEvent<T>(events: ScenarioEvent[], second: number, predicate: (event: ScenarioEvent) => event is ScenarioEvent & T): (ScenarioEvent & T) | undefined {
  return [...events].reverse().find((event): event is ScenarioEvent & T => event.second <= second && predicate(event));
}

function isMaintenanceActive(events: ScenarioEvent[], second: number) {
  return events.some((event) => event.kind === 'maintenance_pause' && event.maintenanceDurationSeconds && second >= event.second && second < event.second + event.maintenanceDurationSeconds);
}

export function scenarioFrameFor(scenario: StageScenario, rawSecond: number): ScenarioFrame {
  const second = clamp(Math.floor(rawSecond), 0, scenario.durationSeconds);
  const eventsToNow = scenario.events.filter((event) => event.second <= second);
  const currentEvents = scenario.events.filter((event) => event.second === second);
  const nextEvents = scenario.events.filter((event) => event.second > second).slice(0, 4);
  const modeEvent = latestEvent<{ mode: Mode }>(scenario.events, second, (event): event is ScenarioEvent & { mode: Mode } => Boolean(event.mode));
  const autoEvent = latestEvent<{ autoRunning: boolean }>(scenario.events, second, (event): event is ScenarioEvent & { autoRunning: boolean } => typeof event.autoRunning === 'boolean');
  const selectedEvent = latestEvent<{ targetId: string }>(scenario.events, second, (event): event is ScenarioEvent & { targetId: string } => Boolean(event.targetId));
  const panEvent = latestEvent<{ panAngle: number; tiltAngle: number }>(scenario.events, second, (event): event is ScenarioEvent & { panAngle: number; tiltAngle: number } => typeof event.panAngle === 'number' && typeof event.tiltAngle === 'number');
  const blockEvent = latestEvent<{ blockReason: BlockReason }>(scenario.events, second, (event): event is ScenarioEvent & { blockReason: BlockReason } => Boolean(event.blockReason));
  const roundEvent = latestEvent<{ round: number }>(scenario.events, second, (event): event is ScenarioEvent & { round: number } => typeof event.round === 'number');
  const scoredEvents = eventsToNow.filter((event) => typeof event.points === 'number');
  const hitEvents = eventsToNow.filter((event) => event.result === 'hit');
  const missEvents = eventsToNow.filter((event) => event.result === 'miss');
  const round = roundEvent?.round ?? 1;
  const roundHits = hitEvents.filter((event) => (event.round ?? round) === round).length;
  const latest = eventsToNow[eventsToNow.length - 1];
  const paused = isMaintenanceActive(scenario.events, second);
  const mode = paused ? 'maintenance' : modeEvent?.mode ?? scenario.defaultMode;
  const selectedTargetId = selectedEvent?.targetId ?? generateScenarioTracks(scenario, second).find((track) => track.candidate)?.id;
  const currentTarget = scenario.stage === 1 ? Math.min(4, hitEvents.length) : 0;
  const enemyHitThisRound = scenario.stage === 3 && hitEvents.some((event) => (event.round ?? round) === round);
  return {
    second,
    stage: scenario.stage,
    mode,
    autoRunning: paused ? false : autoEvent?.autoRunning ?? scenario.autoRunning,
    paused,
    selectedTargetId,
    panAngle: panEvent?.panAngle ?? 0,
    tiltAngle: panEvent?.tiltAngle ?? 0,
    score: scoredEvents.reduce((sum, event) => sum + (event.points ?? 0), 0),
    hits: hitEvents.length,
    misses: missEvents.length,
    round,
    roundHits,
    currentTarget,
    enemyHitThisRound,
    blockReason: blockEvent && second - blockEvent.second <= 2 ? blockEvent.blockReason : 'ALLOWED',
    status: latest ? `${latest.title} · ${latest.detail}` : scenario.title,
    currentEvents,
    nextEvents,
  };
}

export function eventDecision(event: ScenarioEvent) {
  if (event.result === 'hit') return event.kind === 'hit' ? 'SCENARIO_HIT' : 'SCENARIO_OK';
  if (event.result === 'miss') return 'SCENARIO_MISS';
  if (event.result === 'blocked') return event.blockReason ?? 'SCENARIO_BLOCK';
  return `SCENARIO_${event.kind.toUpperCase()}`;
}
