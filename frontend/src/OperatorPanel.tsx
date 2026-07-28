import { type CSSProperties, type PointerEvent, type WheelEvent, useEffect, useMemo, useRef, useState } from 'react';
import gokkalkanIconUrl from '../assets/gokkalkan_icon.png';
import { COMPETITION_COURSE, displayXForRangeBand, toDisplayCourseMeters } from './competitionCourse';
import {
  canSendFireIntent,
  makeCommandResult,
  makeFireIntent,
  makeStageRequest,
  operatorBlockCopy,
  stageExpectedMode,
  stageRoundLimit,
  type CommandResult,
  type OperatorPanelConfig,
  type OperatorSensorFrame,
  type OperatorTrackState,
} from './operatorContracts';
import {
  fetchOperatorReplay,
  fetchOperatorReadiness,
  fetchOperatorTelemetryExport,
  resetOperatorTelemetry,
  sendOperatorFireIntent,
  sendOperatorStageRequest,
  type HardwareResult,
  type OperatorReplayBundle,
  type OperatorReadinessItem,
  type OperatorTelemetryExport,
  type OperatorTelemetryLogRecord,
} from './operatorApiClient';
import type { Mode, Stage, TargetType } from './types';
import { MissionHeader } from './components/MissionHeader';
import { CommandConsole } from './components/CommandConsole';
import { ReadinessDashboard } from './components/ReadinessDashboard';
import { EventStream } from './components/EventStream';
import { SafetyAuthorityPanel } from './components/SafetyAuthorityPanel';
import { HardwareHealthBadge } from './components/HardwareHealthBadge';
import { TrackList } from './components/TrackList';
import { sendOperatorEStop, sendMaintenanceEnd, sendMaintenanceRequest, sendMissionResume, sendMissionStop, sendOperatorManualAimCommand } from './operatorApiClient';
import { useOperatorBackendState } from './hooks/useOperatorBackendState';


const DEFAULT_OPERATOR_STAGE: Stage = 1;
const TYPE_SYMBOL_CONFIDENCE_THRESHOLD = 0.4;

const targetLabel: Record<TargetType, string> = {
  F16: 'Savaş Uçağı / F16',
  Helikopter: 'Helikopter',
  'Balistik Füze': 'Balistik Füze',
  'Mini/Micro İHA': 'Mini/Micro İHA',
};

function makeBootCommandResult() {
  return makeCommandResult({
    commandId: 'BOOT-DRY-RUN',
    kind: 'ModeRequest',
    accepted: true,
    dryRun: true,
    safetyBlockReason: 'ALLOWED',
    createdAt: new Date('2026-05-25T20:00:00Z'),
  });
}

function affiliationClass(friendFoe: OperatorTrackState['friendFoe']) {
  if (friendFoe === 'Düşman') return 'enemy';
  if (friendFoe === 'Dost') return 'friend';
  return 'unknown';
}

function isFrameUnidentified(frame: Pick<OperatorSensorFrame, 'friendFoe' | 'classificationConfidence'>) {
  return frame.friendFoe === 'Bilinmeyen' || frame.classificationConfidence < 0.6;
}

function hasReliableTrackType(track: Pick<OperatorTrackState, 'confidence'>) {
  return track.confidence >= TYPE_SYMBOL_CONFIDENCE_THRESHOLD;
}

function hasReliableFrameType(frame: Pick<OperatorSensorFrame, 'classificationConfidence'>) {
  return frame.classificationConfidence >= TYPE_SYMBOL_CONFIDENCE_THRESHOLD;
}

function hostilityConfidence(frame: OperatorSensorFrame) {
  return isFrameUnidentified(frame) ? Math.max(0.52, 1 - frame.classificationConfidence) : frame.quality;
}

function stageHasHostilityDetection(stage: Stage) {
  return stage === 3;
}

function operatorXForRange(range: number) {
  return displayXForRangeBand(range);
}

function clampPercent(value: number, min = 7, max = 93) {
  return Math.min(max, Math.max(min, value));
}

function clampNumber(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function formatDuration(totalSeconds: number) {
  const boundedSeconds = Math.max(0, Math.ceil(totalSeconds));
  const minutes = Math.floor(boundedSeconds / 60);
  const seconds = boundedSeconds % 60;
  return `${minutes}:${seconds.toString().padStart(2, '0')}`;
}

type SensorViewState = {
  pitch: number;
  yaw: number;
  panX: number;
  panZ: number;
  distance: number;
};

type SensorDragState = {
  pointerId: number;
  startX: number;
  startY: number;
  basePitch: number;
  baseYaw: number;
  basePanX: number;
  basePanZ: number;
  mode: 'orbit' | 'pan';
};

const defaultSensorView: SensorViewState = {
  pitch: 48,
  yaw: 92,
  panX: 0.8,
  panZ: 0,
  distance: 18,
};

function visualSizeForTarget(type: TargetType) {
  const base = {
    F16: { w: 9.4, h: 6.2 },
    Helikopter: { w: 7.6, h: 7.6 },
    'Balistik Füze': { w: 6.4, h: 9.2 },
    'Mini/Micro İHA': { w: 6.8, h: 6.8 },
  } satisfies Record<TargetType, { w: number; h: number }>;
  return base[type];
}

function visualTrackFor(track: OperatorTrackState, index: number, stage: Stage) {
  const radians = (track.bearingDeg * Math.PI) / 180;
  const size = hasReliableTrackType(track) ? visualSizeForTarget(track.targetType) : { w: 6.2, h: 6.2 };
  const mappedPoint = track.courseState?.insidePoligon && track.courseState.projectedCourseM
    ? toDisplayCourseMeters(track.courseState.projectedCourseM)
    : undefined;
  const x = mappedPoint?.x ?? (stage === 1
    ? clampPercent(operatorXForRange(track.rangeM) + (index % 2 === 0 ? -2.4 : 2.4), 12, 82)
    : clampPercent(operatorXForRange(track.rangeM) + Math.sin(radians) * 7, 13, 72));
  const y = mappedPoint?.y ?? (stage === 1
    ? clampPercent(35 + index * 8, 24, 74)
    : clampPercent(30 + index * 13.5 + Math.sin(radians) * 4, 26, 78));
  const rangeGate = targetRangeGateOk(track) ? 'Uygun' : track.rangeM > 15 ? 'Erken' : 'Geçersiz';
  const courseGate = track.courseState == null || track.courseState.predictionValid;
  const candidate = courseGate && track.friendFoe === 'Düşman' && (stage === 1 || stage === 2 || targetRangeGateOk(track));
  const lane = track.courseState?.routeNumber
    ?? (((index % 3) + 1) as 1 | 2 | 3);
  return { ...track, x, y, w: size.w, h: size.h, rangeGate, candidate, lane };
}

function visualRangeLabel(track?: ReturnType<typeof visualTrackFor>) {
  if (!track) return 'Hedef yok';
  if (track.friendFoe === 'Dost') return 'Dost unsur';
  if (track.rangeGate === 'Uygun') return 'MENZİL UYGUN';
  if (track.rangeGate === 'Erken') return 'ÇOK ERKEN';
  return 'MENZİL DIŞI';
}

const DOME_SOURCE_NOSE_SCREEN_DEG = 135;
const DOME_DEFAULT_ROTATION_DEG = 45;
const OPERATOR_SYSTEM_POSITION = COMPETITION_COURSE.systemPosition;

function domeRotationForVisualTrack(track?: ReturnType<typeof visualTrackFor>) {
  if (!track) return DOME_DEFAULT_ROTATION_DEG;
  const targetAngle = (Math.atan2(track.y - OPERATOR_SYSTEM_POSITION.y, track.x - OPERATOR_SYSTEM_POSITION.x) * 180) / Math.PI;
  return targetAngle - DOME_SOURCE_NOSE_SCREEN_DEG;
}

function targetRangeGateOk(track: OperatorTrackState | undefined) {
  if (!track) return false;
  const range = targetEngagementRange(track.targetType);
  return track.rangeM >= range.min && track.rangeM <= range.max;
}

function targetEngagementRange(type: TargetType) {
  if (type === 'F16') return { min: 10, max: 15 };
  if (type === 'Helikopter' || type === 'Balistik Füze') return { min: 5, max: 15 };
  return { min: 0, max: 15 };
}

function permittedRangeForStageTarget(stage: Stage, type: TargetType) {
  if (stage === 2) return { min: 0, max: 15 };
  return targetEngagementRange(type);
}

function sensorFrame3DPoint(frame: OperatorSensorFrame, index: number) {
  const bearingRadians = (frame.bearingDeg * Math.PI) / 180;
  const normalizedRange = clampNumber(frame.rangeM / 15, 0.12, 1);
  return {
    x: clampPercent(60 - normalizedRange * 38 + Math.sin(bearingRadians) * 10, 14, 62),
    y: clampPercent(54 - Math.cos(bearingRadians) * 26 + index * 5, 18, 82),
    z: 18 + clampNumber(frame.quality, 0.35, 0.98) * 38 + index * 2,
  };
}

type Vec3 = [number, number, number];
type SensorBatch = { positions: number[]; colors: number[] };
type SensorOverlayPoint = {
  frameId: string;
  trackId: string;
  left: number;
  top: number;
  visible: boolean;
};

type SensorGlResources = {
  program: WebGLProgram;
  positionBuffer: WebGLBuffer;
  colorBuffer: WebGLBuffer;
  positionLocation: number;
  colorLocation: number;
  matrixLocation: WebGLUniformLocation;
};

const SENSOR_DOME_POSITION: Vec3 = [7.7, 0, 0];
const SENSOR_DEFAULT_DISTANCE = defaultSensorView.distance;

const sensorPalette = {
  grid: [0.18, 0.52, 0.95] as Vec3,
  ring: [0.22, 0.82, 1] as Vec3,
  dome: [0.18, 0.56, 1] as Vec3,
  domeDark: [0.03, 0.12, 0.46] as Vec3,
  enemy: [1, 0.34, 0.43] as Vec3,
  friend: [0.2, 0.93, 0.54] as Vec3,
  unknown: [0.96, 0.98, 1] as Vec3,
  selected: [1, 0.84, 0.32] as Vec3,
};

function vecSubtract(a: Vec3, b: Vec3): Vec3 {
  return [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
}

function vecCross(a: Vec3, b: Vec3): Vec3 {
  return [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
}

function vecDot(a: Vec3, b: Vec3) {
  return a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
}

function vecNormalize(value: Vec3): Vec3 {
  const length = Math.hypot(value[0], value[1], value[2]) || 1;
  return [value[0] / length, value[1] / length, value[2] / length];
}

function multiplyMat4(a: number[], b: number[]) {
  const output = new Array<number>(16).fill(0);
  for (let column = 0; column < 4; column += 1) {
    for (let row = 0; row < 4; row += 1) {
      output[column * 4 + row] =
        a[0 * 4 + row] * b[column * 4 + 0] +
        a[1 * 4 + row] * b[column * 4 + 1] +
        a[2 * 4 + row] * b[column * 4 + 2] +
        a[3 * 4 + row] * b[column * 4 + 3];
    }
  }
  return output;
}

function perspectiveMatrix(fieldOfViewRadians: number, aspect: number, near: number, far: number) {
  const f = 1 / Math.tan(fieldOfViewRadians / 2);
  const rangeInverse = 1 / (near - far);
  return [
    f / aspect, 0, 0, 0,
    0, f, 0, 0,
    0, 0, (near + far) * rangeInverse, -1,
    0, 0, near * far * rangeInverse * 2, 0,
  ];
}

function lookAtMatrix(eye: Vec3, center: Vec3, up: Vec3) {
  const zAxis = vecNormalize(vecSubtract(eye, center));
  const xAxis = vecNormalize(vecCross(up, zAxis));
  const yAxis = vecCross(zAxis, xAxis);
  return [
    xAxis[0], yAxis[0], zAxis[0], 0,
    xAxis[1], yAxis[1], zAxis[1], 0,
    xAxis[2], yAxis[2], zAxis[2], 0,
    -vecDot(xAxis, eye), -vecDot(yAxis, eye), -vecDot(zAxis, eye), 1,
  ];
}

function sensorViewMatrix(view: SensorViewState, aspect: number) {
  const yaw = (view.yaw * Math.PI) / 180;
  const pitch = (view.pitch * Math.PI) / 180;
  const center: Vec3 = [view.panX, 0.2, view.panZ];
  const groundDistance = Math.cos(pitch) * view.distance;
  const eye: Vec3 = [
    center[0] + Math.sin(yaw) * groundDistance,
    center[1] + Math.sin(pitch) * view.distance,
    center[2] + Math.cos(yaw) * groundDistance,
  ];
  return multiplyMat4(
    perspectiveMatrix((46 * Math.PI) / 180, Math.max(aspect, 0.5), 0.1, 80),
    lookAtMatrix(eye, center, [0, 1, 0]),
  );
}

function transformPoint(matrix: number[], point: Vec3) {
  const x = matrix[0] * point[0] + matrix[4] * point[1] + matrix[8] * point[2] + matrix[12];
  const y = matrix[1] * point[0] + matrix[5] * point[1] + matrix[9] * point[2] + matrix[13];
  const z = matrix[2] * point[0] + matrix[6] * point[1] + matrix[10] * point[2] + matrix[14];
  const w = matrix[3] * point[0] + matrix[7] * point[1] + matrix[11] * point[2] + matrix[15];
  return { x, y, z, w };
}

function projectSensorPoint(matrix: number[], point: Vec3) {
  const projected = transformPoint(matrix, point);
  if (Math.abs(projected.w) < 0.0001) return { left: 50, top: 50, visible: false };
  const ndcX = projected.x / projected.w;
  const ndcY = projected.y / projected.w;
  const ndcZ = projected.z / projected.w;
  return {
    left: clampNumber((ndcX * 0.5 + 0.5) * 100, 3, 97),
    top: clampNumber((-ndcY * 0.5 + 0.5) * 100, 6, 94),
    visible: ndcZ >= -1 && ndcZ <= 1 && ndcX > -1.15 && ndcX < 1.15 && ndcY > -1.15 && ndcY < 1.15,
  };
}

function sensorFrameWorldPoint(frame: OperatorSensorFrame, index: number, total: number): Vec3 {
  const bearingRadians = (frame.bearingDeg * Math.PI) / 180;
  const normalizedRange = clampNumber(frame.rangeM / 15, 0.08, 1);
  const lateral = Math.sin(bearingRadians);
  const rowBias = index - (total - 1) / 2;
  return [
    clampNumber(SENSOR_DOME_POSITION[0] - normalizedRange * 10.7 + lateral * 2.35, -7.9, 5.2),
    0.72 + clampNumber(frame.elevationDeg ?? 0.4, -4, 12) * 0.06 + index * 0.12,
    clampNumber(lateral * 5 + rowBias * 0.78, -5.8, 5.8),
  ];
}

function sensorFrameColor(frame: OperatorSensorFrame): Vec3 {
  if (frame.friendFoe === 'Düşman') return sensorPalette.enemy;
  if (frame.friendFoe === 'Dost') return sensorPalette.friend;
  return sensorPalette.unknown;
}

function pushVertex(batch: SensorBatch, point: Vec3, color: Vec3) {
  batch.positions.push(point[0], point[1], point[2]);
  batch.colors.push(color[0], color[1], color[2]);
}

function pushTriangle(batch: SensorBatch, a: Vec3, b: Vec3, c: Vec3, color: Vec3) {
  pushVertex(batch, a, color);
  pushVertex(batch, b, color);
  pushVertex(batch, c, color);
}

function pushLine(batch: SensorBatch, a: Vec3, b: Vec3, color: Vec3) {
  pushVertex(batch, a, color);
  pushVertex(batch, b, color);
}

function orientedPoint(origin: Vec3, local: Vec3, yaw: number): Vec3 {
  const cos = Math.cos(yaw);
  const sin = Math.sin(yaw);
  return [
    origin[0] + local[0] * cos + local[2] * sin,
    origin[1] + local[1],
    origin[2] - local[0] * sin + local[2] * cos,
  ];
}

function pushOrientedBox(batch: SensorBatch, origin: Vec3, localCenter: Vec3, size: Vec3, yaw: number, color: Vec3) {
  const halfX = size[0] / 2;
  const halfY = size[1] / 2;
  const halfZ = size[2] / 2;
  const center = orientedPoint(origin, localCenter, yaw);
  const corners = [
    orientedPoint(center, [-halfX, -halfY, -halfZ], yaw),
    orientedPoint(center, [halfX, -halfY, -halfZ], yaw),
    orientedPoint(center, [halfX, halfY, -halfZ], yaw),
    orientedPoint(center, [-halfX, halfY, -halfZ], yaw),
    orientedPoint(center, [-halfX, -halfY, halfZ], yaw),
    orientedPoint(center, [halfX, -halfY, halfZ], yaw),
    orientedPoint(center, [halfX, halfY, halfZ], yaw),
    orientedPoint(center, [-halfX, halfY, halfZ], yaw),
  ];
  [
    [0, 1, 2], [0, 2, 3],
    [4, 6, 5], [4, 7, 6],
    [0, 4, 5], [0, 5, 1],
    [3, 2, 6], [3, 6, 7],
    [1, 5, 6], [1, 6, 2],
    [0, 3, 7], [0, 7, 4],
  ].forEach(([a, b, c]) => pushTriangle(batch, corners[a], corners[b], corners[c], color));
}

function pushPyramidNose(batch: SensorBatch, origin: Vec3, localBase: Vec3, length: number, radius: number, yaw: number, color: Vec3) {
  const tip = orientedPoint(origin, [localBase[0] + length, localBase[1], localBase[2]], yaw);
  const base = [
    orientedPoint(origin, [localBase[0], localBase[1] - radius, localBase[2] - radius], yaw),
    orientedPoint(origin, [localBase[0], localBase[1] + radius, localBase[2] - radius], yaw),
    orientedPoint(origin, [localBase[0], localBase[1] + radius, localBase[2] + radius], yaw),
    orientedPoint(origin, [localBase[0], localBase[1] - radius, localBase[2] + radius], yaw),
  ];
  pushTriangle(batch, tip, base[0], base[1], color);
  pushTriangle(batch, tip, base[1], base[2], color);
  pushTriangle(batch, tip, base[2], base[3], color);
  pushTriangle(batch, tip, base[3], base[0], color);
}

function pushCylinder(batch: SensorBatch, center: Vec3, radius: number, height: number, segments: number, color: Vec3) {
  const bottomY = center[1] - height / 2;
  const topY = center[1] + height / 2;
  for (let index = 0; index < segments; index += 1) {
    const angle = (index / segments) * Math.PI * 2;
    const nextAngle = ((index + 1) / segments) * Math.PI * 2;
    const p0: Vec3 = [center[0] + Math.cos(angle) * radius, bottomY, center[2] + Math.sin(angle) * radius];
    const p1: Vec3 = [center[0] + Math.cos(nextAngle) * radius, bottomY, center[2] + Math.sin(nextAngle) * radius];
    const p2: Vec3 = [center[0] + Math.cos(nextAngle) * radius, topY, center[2] + Math.sin(nextAngle) * radius];
    const p3: Vec3 = [center[0] + Math.cos(angle) * radius, topY, center[2] + Math.sin(angle) * radius];
    pushTriangle(batch, p0, p1, p2, color);
    pushTriangle(batch, p0, p2, p3, color);
    pushTriangle(batch, [center[0], topY, center[2]], p3, p2, color);
  }
}

function pushSphere(batch: SensorBatch, center: Vec3, radius: number, color: Vec3) {
  const rings = 7;
  const segments = 14;
  for (let ring = 0; ring < rings; ring += 1) {
    const phi0 = (-Math.PI / 2) + (ring / rings) * Math.PI;
    const phi1 = (-Math.PI / 2) + ((ring + 1) / rings) * Math.PI;
    for (let segment = 0; segment < segments; segment += 1) {
      const theta0 = (segment / segments) * Math.PI * 2;
      const theta1 = ((segment + 1) / segments) * Math.PI * 2;
      const point = (phi: number, theta: number): Vec3 => [
        center[0] + Math.cos(phi) * Math.cos(theta) * radius,
        center[1] + Math.sin(phi) * radius,
        center[2] + Math.cos(phi) * Math.sin(theta) * radius,
      ];
      const a = point(phi0, theta0);
      const b = point(phi0, theta1);
      const c = point(phi1, theta1);
      const d = point(phi1, theta0);
      pushTriangle(batch, a, b, c, color);
      pushTriangle(batch, a, c, d, color);
    }
  }
}

function pushSensorAircraft(triangles: SensorBatch, lines: SensorBatch, frame: OperatorSensorFrame, point: Vec3) {
  const color = sensorFrameColor(frame);
  const yaw = ((frame.bearingDeg - 2) * Math.PI) / 180;
  const scale = 1;
  if (!hasReliableFrameType(frame)) {
    pushSphere(triangles, point, 0.36, color);
  } else if (frame.targetType === 'Helikopter') {
    pushOrientedBox(triangles, point, [0, 0, 0], [0.88 * scale, 0.28 * scale, 0.42 * scale], yaw, color);
    pushOrientedBox(triangles, point, [-0.72 * scale, 0, 0], [0.86 * scale, 0.08 * scale, 0.12 * scale], yaw, color);
    pushOrientedBox(triangles, point, [0, 0.32 * scale, 0], [1.18 * scale, 0.035 * scale, 0.08 * scale], yaw, color);
    pushOrientedBox(triangles, point, [0, 0.33 * scale, 0], [0.08 * scale, 0.035 * scale, 1.18 * scale], yaw, color);
  } else if (frame.targetType === 'Balistik Füze') {
    pushOrientedBox(triangles, point, [0, 0, 0], [1.15 * scale, 0.2 * scale, 0.2 * scale], yaw, color);
    pushPyramidNose(triangles, point, [0.58 * scale, 0, 0], 0.38 * scale, 0.13 * scale, yaw, color);
    pushOrientedBox(triangles, point, [-0.44 * scale, -0.02 * scale, 0.2 * scale], [0.25 * scale, 0.05 * scale, 0.36 * scale], yaw, color);
    pushOrientedBox(triangles, point, [-0.44 * scale, -0.02 * scale, -0.2 * scale], [0.25 * scale, 0.05 * scale, 0.36 * scale], yaw, color);
  } else if (frame.targetType === 'Mini/Micro İHA') {
    pushOrientedBox(triangles, point, [0, 0, 0], [0.34 * scale, 0.18 * scale, 0.34 * scale], yaw, color);
    pushOrientedBox(triangles, point, [0, 0, 0], [1.05 * scale, 0.045 * scale, 0.09 * scale], yaw, color);
    pushOrientedBox(triangles, point, [0, 0, 0], [0.09 * scale, 0.045 * scale, 1.05 * scale], yaw, color);
    [[0.48, 0.48], [0.48, -0.48], [-0.48, 0.48], [-0.48, -0.48]].forEach(([x, z]) => {
      pushOrientedBox(triangles, point, [x * scale, 0.04 * scale, z * scale], [0.23 * scale, 0.04 * scale, 0.23 * scale], yaw, color);
    });
  } else {
    pushOrientedBox(triangles, point, [0.05 * scale, 0, 0], [1.38 * scale, 0.16 * scale, 0.22 * scale], yaw, color);
    pushPyramidNose(triangles, point, [0.72 * scale, 0, 0], 0.48 * scale, 0.12 * scale, yaw, color);
    pushOrientedBox(triangles, point, [-0.04 * scale, -0.01 * scale, 0], [0.62 * scale, 0.04 * scale, 1.54 * scale], yaw, color);
    pushOrientedBox(triangles, point, [-0.58 * scale, 0, 0], [0.38 * scale, 0.045 * scale, 0.64 * scale], yaw, color);
    pushOrientedBox(triangles, point, [-0.62 * scale, 0.28 * scale, 0], [0.22 * scale, 0.54 * scale, 0.08 * scale], yaw, color);
    pushOrientedBox(triangles, point, [-0.18 * scale, -0.1 * scale, 0], [0.34 * scale, 0.07 * scale, 0.18 * scale], yaw, color);
  }
  pushLine(lines, [point[0], 0.06, point[2]], [point[0], point[1], point[2]], color);
}

function pushSensorWorld(triangles: SensorBatch, lines: SensorBatch, frames: OperatorSensorFrame[], selectedTrackId: string) {
  for (let x = -8; x <= 8; x += 2) {
    pushLine(lines, [x, 0, -6.2], [x, 0, 6.2], sensorPalette.grid);
  }
  for (let z = -6; z <= 6; z += 2) {
    pushLine(lines, [-8.2, 0, z], [8.4, 0, z], sensorPalette.grid);
  }
  [5, 10, 15].forEach((range) => {
    const radius = (range / 15) * 9.6;
    const segments = 44;
    for (let index = 0; index < segments; index += 1) {
      const angle = -Math.PI / 2 + (index / segments) * Math.PI;
      const nextAngle = -Math.PI / 2 + ((index + 1) / segments) * Math.PI;
      pushLine(
        lines,
        [SENSOR_DOME_POSITION[0] - Math.cos(angle) * radius, 0.025, SENSOR_DOME_POSITION[2] + Math.sin(angle) * radius * 0.64],
        [SENSOR_DOME_POSITION[0] - Math.cos(nextAngle) * radius, 0.025, SENSOR_DOME_POSITION[2] + Math.sin(nextAngle) * radius * 0.64],
        sensorPalette.ring,
      );
    }
  });

  const selectedFrame = frames.find((frame) => frame.trackId === selectedTrackId) ?? frames[0];
  const selectedPoint = selectedFrame ? sensorFrameWorldPoint(selectedFrame, Math.max(0, frames.indexOf(selectedFrame)), frames.length) : undefined;
  const turretYaw = selectedPoint
    ? Math.atan2(-(selectedPoint[2] - SENSOR_DOME_POSITION[2]), selectedPoint[0] - SENSOR_DOME_POSITION[0])
    : Math.PI;

  pushCylinder(triangles, [SENSOR_DOME_POSITION[0], 0.28, SENSOR_DOME_POSITION[2]], 0.42, 0.56, 24, sensorPalette.domeDark);
  pushCylinder(triangles, [SENSOR_DOME_POSITION[0], 0.68, SENSOR_DOME_POSITION[2]], 0.72, 0.24, 28, sensorPalette.dome);
  pushOrientedBox(triangles, [SENSOR_DOME_POSITION[0], 0.78, SENSOR_DOME_POSITION[2]], [0.42, 0, 0], [0.92, 0.12, 0.12], turretYaw, sensorPalette.dome);

  if (selectedPoint) {
    pushLine(lines, [SENSOR_DOME_POSITION[0], 0.9, SENSOR_DOME_POSITION[2]], selectedPoint, sensorPalette.selected);
  }

  frames.forEach((frame, index) => {
    pushSensorAircraft(triangles, lines, frame, sensorFrameWorldPoint(frame, index, frames.length));
  });
}

function createSensorShader(gl: WebGLRenderingContext, type: number, source: string) {
  const shader = gl.createShader(type);
  if (!shader) throw new Error('WebGL shader oluşturulamadı.');
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    const message = gl.getShaderInfoLog(shader) ?? 'Bilinmeyen shader hatası';
    gl.deleteShader(shader);
    throw new Error(message);
  }
  return shader;
}

function createSensorResources(gl: WebGLRenderingContext): SensorGlResources {
  const vertexShader = createSensorShader(gl, gl.VERTEX_SHADER, `
    attribute vec3 a_position;
    attribute vec3 a_color;
    uniform mat4 u_matrix;
    varying vec3 v_color;
    void main() {
      gl_Position = u_matrix * vec4(a_position, 1.0);
      v_color = a_color;
    }
  `);
  const fragmentShader = createSensorShader(gl, gl.FRAGMENT_SHADER, `
    precision mediump float;
    varying vec3 v_color;
    void main() {
      gl_FragColor = vec4(v_color, 1.0);
    }
  `);
  const program = gl.createProgram();
  if (!program) throw new Error('WebGL programı oluşturulamadı.');
  gl.attachShader(program, vertexShader);
  gl.attachShader(program, fragmentShader);
  gl.linkProgram(program);
  gl.deleteShader(vertexShader);
  gl.deleteShader(fragmentShader);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    const message = gl.getProgramInfoLog(program) ?? 'Bilinmeyen WebGL link hatası';
    gl.deleteProgram(program);
    throw new Error(message);
  }
  const positionBuffer = gl.createBuffer();
  const colorBuffer = gl.createBuffer();
  const matrixLocation = gl.getUniformLocation(program, 'u_matrix');
  if (!positionBuffer || !colorBuffer || !matrixLocation) throw new Error('WebGL buffer lokasyonu alınamadı.');
  return {
    program,
    positionBuffer,
    colorBuffer,
    positionLocation: gl.getAttribLocation(program, 'a_position'),
    colorLocation: gl.getAttribLocation(program, 'a_color'),
    matrixLocation,
  };
}

function resizeSensorCanvas(canvas: HTMLCanvasElement) {
  const pixelRatio = Math.min(window.devicePixelRatio || 1, 2);
  const width = Math.max(1, Math.round(canvas.clientWidth * pixelRatio));
  const height = Math.max(1, Math.round(canvas.clientHeight * pixelRatio));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
}

function drawSensorBatch(gl: WebGLRenderingContext, resources: SensorGlResources, batch: SensorBatch, mode: number, matrix: number[]) {
  if (batch.positions.length === 0) return;
  gl.useProgram(resources.program);
  gl.uniformMatrix4fv(resources.matrixLocation, false, new Float32Array(matrix));

  gl.bindBuffer(gl.ARRAY_BUFFER, resources.positionBuffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(batch.positions), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(resources.positionLocation);
  gl.vertexAttribPointer(resources.positionLocation, 3, gl.FLOAT, false, 0, 0);

  gl.bindBuffer(gl.ARRAY_BUFFER, resources.colorBuffer);
  gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(batch.colors), gl.STATIC_DRAW);
  gl.enableVertexAttribArray(resources.colorLocation);
  gl.vertexAttribPointer(resources.colorLocation, 3, gl.FLOAT, false, 0, 0);

  gl.drawArrays(mode, 0, batch.positions.length / 3);
}

function renderSensorWebGlScene(gl: WebGLRenderingContext, resources: SensorGlResources, frames: OperatorSensorFrame[], selectedTrackId: string, view: SensorViewState) {
  const canvas = gl.canvas as HTMLCanvasElement;
  resizeSensorCanvas(canvas);
  const matrix = sensorViewMatrix(view, canvas.width / canvas.height);
  const triangles: SensorBatch = { positions: [], colors: [] };
  const lines: SensorBatch = { positions: [], colors: [] };
  pushSensorWorld(triangles, lines, frames, selectedTrackId);

  gl.viewport(0, 0, canvas.width, canvas.height);
  gl.clearColor(0.012, 0.022, 0.035, 1);
  gl.clearDepth(1);
  gl.enable(gl.DEPTH_TEST);
  gl.depthFunc(gl.LEQUAL);
  gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
  drawSensorBatch(gl, resources, triangles, gl.TRIANGLES, matrix);
  drawSensorBatch(gl, resources, lines, gl.LINES, matrix);

  return {
    matrix,
    overlayPoints: frames.map((frame, index) => {
      const projected = projectSensorPoint(matrix, sensorFrameWorldPoint(frame, index, frames.length));
      const fallback = sensorFrame3DPoint(frame, index);
      return {
        frameId: frame.frameId,
        trackId: frame.trackId,
        left: projected.visible ? projected.left : fallback.x,
        top: projected.visible ? projected.top : fallback.y,
        visible: projected.visible,
      };
    }),
  };
}

function overlayPointsEqual(a: SensorOverlayPoint[], b: SensorOverlayPoint[]) {
  return a.length === b.length && a.every((point, index) => {
    const other = b[index];
    return other
      && other.frameId === point.frameId
      && other.trackId === point.trackId
      && Math.abs(other.left - point.left) < 0.2
      && Math.abs(other.top - point.top) < 0.2
      && other.visible === point.visible;
  });
}


function shortRecordPayload(record: OperatorTelemetryLogRecord) {
  const value = record.payload ? JSON.stringify(record.payload) : record.raw ?? 'payload yok';
  return value.length > 120 ? `${value.slice(0, 120)}…` : value;
}

function OperatorTargetSilhouette({ type, className = '' }: { type: TargetType; className?: string }) {
  return (
    <svg className={`target-silhouette ${className}`} viewBox="0 0 64 64" aria-hidden="true">
      {type === 'Balistik Füze' && (
        <g>
          <path d="M32 5 C26 13 24 19 24 31 L24 47 L40 47 L40 31 C40 19 38 13 32 5 Z" />
          <path d="M24 42 L12 55 L24 52 Z M40 42 L52 55 L40 52 Z" />
          <path d="M29 47 L25 61 L32 56 L39 61 L35 47 Z" />
          <circle cx="32" cy="25" r="4" />
        </g>
      )}
      {type === 'Helikopter' && (
        <g>
          <path d="M16 33 C20 24 42 24 49 33 C44 43 23 44 16 33 Z" />
          <path d="M44 32 L59 25 L61 29 L49 38 Z" />
          <path d="M24 41 L20 51 L28 51 L31 43 Z M39 41 L43 51 L51 51 L47 41 Z" />
          <path d="M13 20 H51 M29 14 H35 V26 H29 Z" />
          <path d="M8 18 L21 22 M56 18 L43 22" />
        </g>
      )}
      {type === 'F16' && (
        <g>
          <path d="M4 32 L16 28 L36 28 L57 32 L36 36 L16 36 Z" />
          <path d="M32 28 L47 12 L55 15 L42 31 Z M32 36 L47 52 L55 49 L42 33 Z" />
          <path d="M17 28 L8 17 L27 27 Z M17 36 L8 47 L27 37 Z" />
          <path d="M38 29 L47 25 L44 32 L47 39 L38 35 Z" />
          <path d="M23 29 L30 23 L37 29 Z" />
          <circle cx="48" cy="32" r="2" />
        </g>
      )}
      {type === 'Mini/Micro İHA' && (
        <g>
          <circle cx="32" cy="32" r="8" />
          <path d="M24 24 L12 12 M40 24 L52 12 M24 40 L12 52 M40 40 L52 52" />
          <circle cx="11" cy="11" r="7" />
          <circle cx="53" cy="11" r="7" />
          <circle cx="11" cy="53" r="7" />
          <circle cx="53" cy="53" r="7" />
          <path d="M26 32 H38 M32 26 V38" />
        </g>
      )}
    </svg>
  );
}

function OperatorTrackScene({
  stage,
  tracks,
  selectedTrackId,
  shotTrackIds,
  onSelect,
  compact = false,
}: {
  stage: Stage;
  tracks: OperatorTrackState[];
  selectedTrackId: string;
  shotTrackIds: Set<string>;
  onSelect: (trackId: string) => void;
  compact?: boolean;
}) {
  const hostilityDetection = stageHasHostilityDetection(stage);
  const visualTracks = tracks.map((track, index) => visualTrackFor(track, index, stage));
  const selectedVisualTrack = visualTracks.find((track) => track.trackId === selectedTrackId) ?? visualTracks[0];
  const permittedRange = selectedVisualTrack ? permittedRangeForStageTarget(stage, selectedVisualTrack.targetType) : { min: 5, max: 15 };
  const showPermittedRangeWindow = Boolean(selectedVisualTrack && stage === 3);
  const ruleWindow = selectedVisualTrack && stage === 3
    ? {
        start: Math.min(operatorXForRange(permittedRange.max), operatorXForRange(permittedRange.min)),
        width: Math.abs(operatorXForRange(permittedRange.min) - operatorXForRange(permittedRange.max)),
      }
    : selectedVisualTrack
      ? { start: operatorXForRange(selectedVisualTrack.rangeM) - 6, width: 12 }
      : { start: operatorXForRange(15), width: Math.abs(operatorXForRange(5) - operatorXForRange(15)) };
  const domeAngle = domeRotationForVisualTrack(selectedVisualTrack);
  const domeStyle = {
    left: `${OPERATOR_SYSTEM_POSITION.x}%`,
    top: `${OPERATOR_SYSTEM_POSITION.y}%`,
    '--dome-rotation': `${domeAngle}deg`,
  } as CSSProperties;

  return (
    <section
      className={`parkour-hero operator-track-scene ${compact ? 'is-compact' : ''} stage-${stage} relative overflow-hidden rounded-xl border border-[#25d8ff]/18 bg-[#0b1117] shadow-[inset_0_0_54px_rgba(0,0,0,.56)]`}
      data-testid="operator-track-scene"
      aria-label="Operatör iz görüntüsü"
    >
      <svg className="parkour-overlay" viewBox="0 0 100 100" aria-label={`Aşama ${stage} iz şeması`}>
        <defs>
          <pattern id={`operator-grid-${stage}`} width="5" height="5" patternUnits="userSpaceOnUse">
            <path d="M 5 0 L 0 0 0 5" fill="none" stroke="rgba(174,225,255,.10)" strokeWidth=".25" />
          </pattern>
          <marker id={`operator-arrow-${stage}`} markerWidth="5" markerHeight="5" refX="4.2" refY="2.5" orient="auto">
            <path d="M0,0 L5,2.5 L0,5 Z" fill="#ffbb42" opacity=".78" />
          </marker>
        </defs>
        <rect className="schematic-grid" x="3" y="6" width="94" height="88" rx="4" fill={`url(#operator-grid-${stage})`} />

        {stage === 1 ? (
          <g className="stage1-practice-field">
            {[15, 10, 5].map((range) => (
              <g key={range} className={`stage1-zone zone-${range} ${selectedVisualTrack && Math.abs(selectedVisualTrack.rangeM - range) < 2.6 ? 'active' : ''}`} data-testid={`operator-range-${range}m`}>
                <rect x={range === 15 ? 9 : range === 10 ? 36 : 63} y="15" width="25" height="66" rx="4" />
                <text x={range === 15 ? 21.5 : range === 10 ? 48.5 : 75.5} y="22">{range} m</text>
              </g>
            ))}
            <text className="stage1-title" x="9" y="10">MANUEL ATIŞ</text>
          </g>
        ) : (
          <g className="moving-course-field">
            {showPermittedRangeWindow && selectedVisualTrack && (
              <>
                <rect className="valid-window active" x={ruleWindow.start} y="15" width={ruleWindow.width} height="77" data-testid="operator-permitted-range-window" />
                <text className="window-label active" x={Math.min(84, Math.max(16, ruleWindow.start + ruleWindow.width / 2))} y="18.2" textAnchor="middle">
                  {visualRangeLabel(selectedVisualTrack)}
                </text>
              </>
            )}
            {[15, 10, 5].map((range) => (
              <g
                key={range}
                className={`range-line ${selectedVisualTrack && range >= permittedRange.min && range <= permittedRange.max ? 'active' : ''}`}
                data-testid={`operator-range-${range}m`}
              >
                <line x1={operatorXForRange(range)} y1="10" x2={operatorXForRange(range)} y2="93" />
                <text x={operatorXForRange(range) + 0.7} y="12">{range} m</text>
              </g>
            ))}
            <text className="point-label" x="7" y="8">POLİGON GİRİŞİ</text>
            <text className="escape-label" x="69" y="96">POLİGON ÇIKIŞI</text>
            {COMPETITION_COURSE.lanes.map((lane) => (
              <g key={lane.lane} className={`lane-path lane-${lane.lane}`}>
                <polyline points={lane.points.map((point) => `${point.x},${point.y}`).join(' ')} markerEnd={`url(#operator-arrow-${stage})`} />
                <text x="8" y={lane.points[0].y - 2}>ROTA {lane.lane}</text>
              </g>
            ))}
          </g>
        )}

        <g className="system-anchor">
          <circle cx={OPERATOR_SYSTEM_POSITION.x} cy={OPERATOR_SYSTEM_POSITION.y} r="1.15" />
          <text x={OPERATOR_SYSTEM_POSITION.x} y={OPERATOR_SYSTEM_POSITION.y + 8} textAnchor="middle">GÖKKALKAN</text>
        </g>
        {selectedVisualTrack && (
          <g className="target-link" data-testid="operator-aim-line">
            <line x1={selectedVisualTrack.x} y1={selectedVisualTrack.y} x2={OPERATOR_SYSTEM_POSITION.x} y2={OPERATOR_SYSTEM_POSITION.y} />
          </g>
        )}
      </svg>

      <div className="parkour-object-layer">
        <div
          className="steel-dome pointer-events-none absolute z-[5] grid h-[62px] w-[62px] -translate-x-1/2 -translate-y-1/2 place-items-center [filter:drop-shadow(0_0_18px_rgba(51,230,140,.24))_drop-shadow(0_10px_20px_rgba(0,0,0,.48))]"
          style={domeStyle}
          data-testid="operator-steel-dome"
          data-rotation={domeAngle.toFixed(1)}
          aria-hidden="true"
        >
          <img className="h-[54px] w-[54px] rounded-full object-contain opacity-90 will-change-transform [transform:rotate(var(--dome-rotation))]" src={gokkalkanIconUrl} alt="" />
        </div>

        {visualTracks.map((track) => {
          const selected = selectedVisualTrack?.trackId === track.trackId;
          const typeReliable = hasReliableTrackType(track);
          const unknown = !typeReliable;
          const shot = shotTrackIds.has(track.trackId);
          const displayAffiliation = hostilityDetection ? track.friendFoe : 'Bilinmeyen';
          const statusText = unknown ? 'tür doğruluğu bekleniyor' : hostilityDetection ? `${targetLabel[track.targetType]} ${track.friendFoe}` : targetLabel[track.targetType];
          return (
            <button
              key={track.trackId}
              className={`aircraft absolute z-[6] grid min-h-[62px] min-w-[58px] -translate-x-1/2 -translate-y-1/2 content-center place-items-center rounded-full border-0 bg-transparent p-0.5 text-center shadow-none transition-[color,filter,transform] duration-150 will-change-[left,top] ${affiliationClass(displayAffiliation)} ${unknown ? 'unknown-object' : ''} ${stage !== 1 ? 'moving' : 'stationary'} ${selected ? 'selected' : ''} ${track.candidate && !shot ? 'candidate' : ''} ${shot ? 'is-shot' : ''}`}
              style={{ left: `${track.x}%`, top: `${track.y}%`, width: `${track.w}%`, height: `${track.h}%` }}
              data-testid={`operator-track-${track.trackId}`}
              data-track-id={track.trackId}
              data-affiliation={displayAffiliation}
              data-identification={unknown ? 'unknown' : 'identified'}
              data-shape={typeReliable ? 'symbol' : 'sphere'}
              data-shot={shot ? 'true' : 'false'}
              aria-label={`${track.trackId} ${statusText} ${track.rangeM.toFixed(1)} metre`}
              onClick={() => onSelect(track.trackId)}
            >
              <span className="motion-trail" />
              <span className="target-visual">{unknown ? <span className="target-unknown-sphere" aria-hidden="true" /> : <OperatorTargetSilhouette type={track.targetType} />}</span>
              {shot && (
                <span className="shot-eliminated-icon" data-testid={`operator-track-shot-icon-${track.trackId}`} aria-hidden="true">
                  <svg viewBox="0 0 64 64">
                    <circle cx="32" cy="32" r="23" />
                    <path d="M20 20 L44 44 M44 20 L20 44" />
                  </svg>
                </span>
              )}
            </button>
          );
        })}
      </div>

      {hostilityDetection && (
        <div className="map-legend absolute bottom-3 left-3.5 z-[8] flex flex-wrap gap-1.5 rounded-lg border border-white/10 bg-[rgba(2,4,7,.76)] px-2 py-1.5 backdrop-blur">
          <span className="flex items-center gap-1.5 text-[11px] font-extrabold text-[#cde1ec]"><i className="enemy-dot" />Düşman</span>
          <span className="flex items-center gap-1.5 text-[11px] font-extrabold text-[#cde1ec]"><i className="friend-dot" />Dost</span>
          <span className="flex items-center gap-1.5 text-[11px] font-extrabold text-[#cde1ec]"><i className="unknown-dot" />Bilinmeyen</span>
          <span className="flex items-center gap-1.5 text-[11px] font-extrabold text-[#cde1ec]"><i className="window-dot" />Menzil</span>
        </div>
      )}
    </section>
  );
}

function RawCameraDiagnosticPage({ streamUrl, onBack }: { streamUrl: string; onBack: () => void }) {
  const [failed, setFailed] = useState(false);
  return (
    <main className="raw-camera-page min-h-screen bg-[#05070a] p-4 text-[#ecf7ff]" data-testid="raw-camera-page">
      <header className="flex items-center justify-between gap-3 rounded-xl border border-[#25d8ff]/18 bg-[rgba(7,10,14,.94)] p-4 max-[760px]:flex-col max-[760px]:items-stretch">
        <div><p className="m-0 text-xs font-black uppercase tracking-[.22em] text-[#48a8ff]">Fiziksel sensör akışı</p><h1 className="m-0 mt-1 text-3xl font-black tracking-[.05em] text-white">HAM KAMERA</h1></div>
        <button type="button" className="min-h-12 rounded-full border border-[#ffbb42]/35 bg-[#ffbb42]/10 px-4 text-xs font-black tracking-[.12em] text-[#ffe4ad] max-[760px]:w-full" data-testid="raw-camera-back-button" onClick={onBack}>OPERATÖR PANELİNE DÖN</button>
      </header>
      <section className="mt-4 rounded-xl border border-[#48a8ff]/25 bg-black/40 p-3">
        <img src={streamUrl} className={`${failed ? 'hidden' : 'block'} aspect-video w-full rounded-lg bg-black object-contain`} alt="Kamera sensöründen gelen canlı MJPEG akışı" data-testid="raw-camera-live-stream" onError={() => setFailed(true)} />
        {failed && <div className="grid aspect-video place-items-center rounded-lg border border-[#ff4757]/30 bg-[#ff4757]/8 p-8 text-center" data-testid="raw-camera-offline"><div><b>FİZİKSEL KAMERA AKIŞI YOK</b><p className="mt-2 text-sm text-[#ffbdc4]">Sentetik görüntü üretilmedi. Perception bridge ve MJPEG servisini doğrulayın.</p></div></div>}
        <p className="mb-0 mt-3 break-all text-xs text-[#91a6b7]">Kaynak: {streamUrl}</p>
      </section>
    </main>
  );
}

function Stage1CameraSupport({ streamUrl, lidarRangeM, lidarLive, correctionDeg, calibrationActive }: { streamUrl: string; lidarRangeM?: number; lidarLive: boolean; correctionDeg?: number | null; calibrationActive: boolean }) {
  const [failed, setFailed] = useState(false);
  const holdoverTop = correctionDeg == null ? 50 : clampNumber(50 + correctionDeg * 4, 50, 78);
  return (
    <section className="relative min-h-[520px] overflow-hidden rounded-xl bg-black" data-testid="stage1-camera-support">
      {!failed ? <img src={streamUrl} alt="Aşama 1 canlı nişan kamerası" className="absolute inset-0 h-full w-full object-contain" onError={() => setFailed(true)} data-testid="stage1-camera-stream" /> : <div className="absolute inset-0 grid place-items-center text-center text-[#ffbdc4]" data-testid="stage1-camera-offline"><div><b>KAMERA AKIŞI BEKLENİYOR</b><p className="text-sm">Sentetik hedef gösterilmez.</p></div></div>}
      <div className="pointer-events-none absolute inset-0" aria-label="Nişangâh katmanı"><span className="absolute left-1/2 top-1/2 h-12 w-12 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-[#25d8ff] shadow-[0_0_14px_#25d8ff]" /><span className="absolute left-1/2 top-1/2 h-px w-20 -translate-x-1/2 bg-[#25d8ff]" /><span className="absolute left-1/2 top-1/2 h-20 w-px -translate-y-1/2 bg-[#25d8ff]" />{correctionDeg != null && <span className="absolute left-1/2 h-6 w-6 -translate-x-1/2 rounded-full border-2 border-[#ffbb42]" style={{ top: `${holdoverTop}%` }} data-testid="stage1-impact-reticle" />}</div>
      <div className="absolute left-3 top-3 rounded-lg border border-[#25d8ff]/30 bg-black/75 px-3 py-2 font-mono" data-testid="stage1-lidar-range"><span className="block text-[10px] text-[#91a6b7]">1D LİDAR · BORESIGHT · {lidarLive ? 'CANLI' : 'REPLAY/BEKLEME'}</span><b className="text-xl text-white">{lidarRangeM == null ? '---' : `${lidarRangeM.toFixed(2)} m`}</b></div>
      <div className="absolute bottom-3 left-3 right-3 flex justify-between gap-3 rounded-lg bg-black/75 px-3 py-2 text-xs"><span>Merkez: kamera/taret ekseni</span><span data-testid="stage1-ballistic-state">{correctionDeg != null ? `Sarı: tahmini darbe noktası · +${correctionDeg.toFixed(2)}°` : calibrationActive ? 'Menzil atış tablosu dışında' : 'Balistik kalibrasyon aktif değil'}</span></div>
    </section>
  );
}

function SensorFusion3DView({
  stage,
  frames,
  selectedTrackId,
  shotTrackIds,
  onSelect,
  connectedSensorFramesEmpty,
}: {
  stage: Stage;
  frames: OperatorSensorFrame[];
  selectedTrackId: string;
  shotTrackIds: Set<string>;
  onSelect: (trackId: string) => void;
  connectedSensorFramesEmpty: boolean;
}) {
  const viewRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const glResourcesRef = useRef<SensorGlResources | undefined>(undefined);
  const [view, setView] = useState<SensorViewState>(defaultSensorView);
  const [dragState, setDragState] = useState<SensorDragState>();
  const [renderTick, setRenderTick] = useState(0);
  const [webglAvailable, setWebglAvailable] = useState(true);
  const [overlayPoints, setOverlayPoints] = useState<SensorOverlayPoint[]>([]);

  const zoomLevel = SENSOR_DEFAULT_DISTANCE / view.distance;
  const displayFrames = useMemo(
    () => (stageHasHostilityDetection(stage) ? frames : frames.map((frame) => ({ ...frame, friendFoe: 'Bilinmeyen' as const }))),
    [frames, stage],
  );

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    if (typeof ResizeObserver === 'undefined') {
      const handleResize = () => setRenderTick((value) => value + 1);
      window.addEventListener('resize', handleResize);
      return () => window.removeEventListener('resize', handleResize);
    }
    const observer = new ResizeObserver(() => setRenderTick((value) => value + 1));
    observer.observe(canvas);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const gl = canvas.getContext('webgl', {
      alpha: false,
      antialias: true,
      depth: true,
      powerPreference: 'high-performance',
    });
    if (!gl) {
      setWebglAvailable(false);
      return;
    }
    setWebglAvailable(true);
    try {
      const resources = glResourcesRef.current ?? createSensorResources(gl);
      glResourcesRef.current = resources;
      const result = renderSensorWebGlScene(gl, resources, displayFrames, selectedTrackId, view);
      setOverlayPoints((current) => (overlayPointsEqual(current, result.overlayPoints) ? current : result.overlayPoints));
    } catch (error) {
      console.warn('Sensör füzyon WebGL çizimi devre dışı kaldı:', error);
      setWebglAvailable(false);
    }
  }, [displayFrames, selectedTrackId, view, renderTick]);

  useEffect(() => () => {
    const canvas = canvasRef.current;
    const gl = canvas?.getContext('webgl');
    const resources = glResourcesRef.current;
    if (!gl || !resources) return;
    gl.deleteProgram(resources.program);
    gl.deleteBuffer(resources.positionBuffer);
    gl.deleteBuffer(resources.colorBuffer);
    glResourcesRef.current = undefined;
  }, []);

  const beginPointerDrag = (event: PointerEvent, captureTarget: HTMLDivElement | null) => {
    if (!captureTarget) return;
    captureTarget.setPointerCapture(event.pointerId);
    setDragState({
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      basePitch: view.pitch,
      baseYaw: view.yaw,
      basePanX: view.panX,
      basePanZ: view.panZ,
      mode: event.shiftKey ? 'pan' : 'orbit',
    });
  };

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    beginPointerDrag(event, event.currentTarget);
  };

  const handleTargetPointerDown = (event: PointerEvent<HTMLButtonElement>, trackId: string) => {
    event.stopPropagation();
    onSelect(trackId);
    beginPointerDrag(event, viewRef.current);
  };

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!dragState || dragState.pointerId !== event.pointerId) return;
    const deltaX = event.clientX - dragState.startX;
    const deltaY = event.clientY - dragState.startY;
    setView((current) => ({
      ...current,
      pitch: dragState.mode === 'orbit' ? clampNumber(dragState.basePitch + deltaY * 0.16, 22, 72) : current.pitch,
      yaw: dragState.mode === 'orbit' ? dragState.baseYaw - deltaX * 0.36 : current.yaw,
      panX: dragState.mode === 'pan' ? clampNumber(dragState.basePanX - deltaX * 0.018 * current.distance, -6, 6) : current.panX,
      panZ: dragState.mode === 'pan' ? clampNumber(dragState.basePanZ + deltaY * 0.018 * current.distance, -4.5, 4.5) : current.panZ,
    }));
  };

  const endPointerDrag = (event: PointerEvent<HTMLDivElement>) => {
    if (dragState?.pointerId !== event.pointerId) return;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
    setDragState(undefined);
  };

  const handleWheel = (event: WheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    setView((current) => ({
      ...current,
      distance: clampNumber(current.distance * (event.deltaY < 0 ? 0.96 : 1.04), 10.5, 32),
    }));
  };

  return (
    <div
      className={`sensor-3d-view webgl-3d-view ${dragState ? 'is-dragging' : ''}`}
      data-testid="operator-sensor-3d-view"
      data-renderer={webglAvailable ? 'webgl' : 'unavailable'}
      data-rotate-x={view.pitch.toFixed(1)}
      data-rotate-z={view.yaw.toFixed(1)}
      data-yaw={view.yaw.toFixed(1)}
      data-pitch={view.pitch.toFixed(1)}
      data-zoom={zoomLevel.toFixed(2)}
      data-pan-x={view.panX.toFixed(1)}
      data-pan-z={view.panZ.toFixed(1)}
      ref={viewRef}
      aria-label="Etkileşimli sensör füzyon hedef izi görünümü"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={endPointerDrag}
      onPointerCancel={endPointerDrag}
      onWheelCapture={handleWheel}
    >
      <canvas ref={canvasRef} className="sensor-3d-canvas" data-testid="operator-sensor-3d-canvas" aria-hidden="true" />
      <div className="sensor-3d-hud">
        <span>Hedef İzleri</span>
        <b>Füzyon Görünümü</b>
      </div>
      <button
        className="sensor-3d-reset"
        type="button"
        data-testid="operator-sensor-3d-reset"
        onPointerDown={(event) => event.stopPropagation()}
        onClick={() => setView(defaultSensorView)}
      >
        3D RESET
      </button>
      {displayFrames.map((frame, index) => {
        const fallbackPoint = sensorFrame3DPoint(frame, index);
        const point = overlayPoints[index] ?? {
          frameId: frame.frameId,
          trackId: frame.trackId,
          left: fallbackPoint.x,
          top: fallbackPoint.y,
          visible: true,
        };
        const selected = selectedTrackId === frame.trackId;
        const typeReliable = hasReliableFrameType(frame);
        const unknown = !typeReliable;
        const shot = shotTrackIds.has(frame.trackId);
        return (
          <button
            key={frame.frameId}
            className={`sensor-3d-target pointer-events-auto ${affiliationClass(frame.friendFoe)} ${unknown ? 'unknown-object' : ''} ${selected ? 'selected' : ''} ${shot ? 'is-shot' : ''} ${point.visible ? '' : 'is-off-axis'}`}
            data-testid={`operator-sensor-3d-target-${frame.trackId}`}
            data-track-id={frame.trackId}
            data-affiliation={frame.friendFoe}
            data-identification={unknown ? 'unknown' : 'identified'}
            data-shape={typeReliable ? 'symbol' : 'sphere'}
            data-shot={shot ? 'true' : 'false'}
            data-type-confidence={frame.classificationConfidence.toFixed(2)}
            data-color-confidence={hostilityConfidence(frame).toFixed(2)}
            style={{ left: `${point.left}%`, top: `${point.top}%` }}
            aria-label={`${frame.trackId} ${unknown ? 'kimlik bekliyor' : targetLabel[frame.targetType]} ${frame.rangeM.toFixed(1)} metre`}
            onPointerDown={(e) => handleTargetPointerDown(e, frame.trackId)}
            onClick={() => onSelect(frame.trackId)}
          />
        );
      })}
      {!webglAvailable && (
        <span className="sensor-3d-empty sensor-3d-webgl-warning">WebGL açılamadı; sensör akışı yazılım katmanında tutuluyor.</span>
      )}
      {(connectedSensorFramesEmpty || displayFrames.length === 0) && (
        <span className="sensor-3d-empty" data-testid="operator-sensor-3d-empty">SensorFrame yok</span>
      )}
    </div>
  );
}

function AccuracyCircle({ label, value, tone, testId }: { label: string; value: number; tone: string; testId: string }) {
  const percent = Math.round(clampNumber(value, 0, 1) * 100);
  return (
    <span
      className={`accuracy-circle ${tone}`}
      style={{ '--accuracy': `${percent}%` } as CSSProperties}
      data-testid={testId}
      aria-label={`${label} doğruluk ${percent}%`}
    >
      <b>{percent}%</b>
      <small>{label}</small>
    </span>
  );
}

function ConfidencePanel({ stage, frames, selectedTrackId }: { stage: Stage; frames: OperatorSensorFrame[]; selectedTrackId: string }) {
  const uniqueFrames = frames.filter((frame, index, all) => all.findIndex((candidate) => candidate.trackId === frame.trackId) === index);
  const hostilityDetection = stageHasHostilityDetection(stage);

  return (
    <section className="operator-confidence-panel rounded-xl border border-[#25d8ff]/18 bg-[rgba(7,10,14,.94)] p-4" data-testid="operator-confidence-panel" aria-label="Sınıf ve dost düşman doğruluk yüzdeleri">
      <div
        className="operator-confidence-grid"
        style={{ '--confidence-count': Math.max(1, uniqueFrames.length) } as CSSProperties}
      >
        {uniqueFrames.map((frame) => {
          const unknown = !hasReliableFrameType(frame);
          const colorValue = hostilityConfidence(frame);
          const selected = frame.trackId === selectedTrackId;
          const displayType = unknown ? 'Bilinmeyen cisim' : targetLabel[frame.targetType];
          const displayAffiliation = hostilityDetection ? frame.friendFoe : 'Bilinmeyen';
          return (
            <article
              key={frame.trackId}
              className={`confidence-row rounded-lg border p-2.5 ${selected ? 'border-[#ffbb42]/35 bg-[#ffbb42]/10' : 'border-white/[.07] bg-white/[.04]'}`}
              data-testid={`operator-confidence-${frame.trackId}`}
              data-affiliation={displayAffiliation}
              data-identification={unknown ? 'unknown' : 'identified'}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <b className="block overflow-hidden text-ellipsis whitespace-nowrap text-sm text-white">{displayType}</b>
                  {hostilityDetection && <span className="block overflow-hidden text-ellipsis whitespace-nowrap text-xs font-black text-[#91a6b7]">{frame.friendFoe}</span>}
                </div>
                {hostilityDetection && <i className={`confidence-swatch ${affiliationClass(frame.friendFoe)}`} aria-hidden="true" />}
              </div>
              <div className={`accuracy-circle-grid mt-3 ${hostilityDetection ? '' : 'type-only'}`}>
                {hostilityDetection && (
                  <AccuracyCircle
                    label="Renk"
                    value={colorValue}
                    tone={affiliationClass(frame.friendFoe)}
                    testId={`operator-accuracy-${frame.trackId}-color`}
                  />
                )}
                <AccuracyCircle
                  label="Tür"
                  value={frame.classificationConfidence}
                  tone={unknown ? 'unknown' : 'type'}
                  testId={`operator-accuracy-${frame.trackId}-type`}
                />
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

export default function OperatorPanel(_props: { onBack: () => void; onOpenSimulator: () => void }) {
  const queryParams = useMemo(() => new URLSearchParams(window.location.search), []);
  const queryApiBaseUrl = queryParams.get('operatorApi')?.trim() ?? '';
  const isDesktopShell = queryParams.get('desktop') === '1';
  const envApiBaseUrl = (import.meta.env.VITE_GOKKALKAN_OPERATOR_API_BASE as string | undefined)?.trim() ?? '';
  const apiBaseUrl = queryApiBaseUrl || envApiBaseUrl;
  const cameraStreamUrl = queryParams.get('cameraStream')?.trim()
    || (import.meta.env.VITE_GOKKALKAN_CAMERA_STREAM_URL as string | undefined)?.trim()
    || 'http://127.0.0.1:8090/camera/live.mjpg';
  const liveArmEnabled = import.meta.env.VITE_GOKKALKAN_OPERATOR_LIVE_ARMED === '1';
  const [mode, setMode] = useState<Mode>(stageExpectedMode(DEFAULT_OPERATOR_STAGE));
  const [stage, setStage] = useState<Stage>(DEFAULT_OPERATOR_STAGE);
  const [round, setRound] = useState(1);
  const [selectedTrackId, setSelectedTrackId] = useState('');
  const [, setLastHardwareResult] = useState<HardwareResult>();
  const [maintenanceOpen, setMaintenanceOpen] = useState(false);
  const {
    snapshot: apiSnapshot,
    setSnapshot: setApiSnapshot,
    readiness: readinessReport,
    setReadiness: setReadinessReport,
    busy: backendBusy,
    error: backendError,
    readinessError: backendReadinessError,
  } = useOperatorBackendState(apiBaseUrl);
  const shotTrackIds = useMemo(
    () => new Set(apiSnapshot?.missionFlow?.completedTargetIds ?? []),
    [apiSnapshot?.missionFlow?.completedTargetIds],
  );
  const [commandBusy, setCommandBusy] = useState(false);
  const [commandApiError, setCommandApiError] = useState('');
  const [readinessRefreshError, setReadinessRefreshError] = useState('');
  const apiBusy = backendBusy || commandBusy;
  const apiError = backendError || commandApiError;
  const readinessError = backendReadinessError || readinessRefreshError;
  const setApiBusy = setCommandBusy;
  const setApiError = setCommandApiError;
  const setReadinessError = setReadinessRefreshError;
  const [telemetryExport, setTelemetryExport] = useState<OperatorTelemetryExport>();
  const [replayBundle, setReplayBundle] = useState<OperatorReplayBundle>();
  const [evidenceBusy, setEvidenceBusy] = useState(false);
  const [evidenceError, setEvidenceError] = useState('');
  const [evidenceNotice, setEvidenceNotice] = useState('');
  const [rawCameraOpen, setRawCameraOpen] = useState(false);
  const [commandResults, setCommandResults] = useState<CommandResult[]>([makeBootCommandResult()]);

  useEffect(() => {
    if (!apiSnapshot) return;
    setMode(apiSnapshot.mode);
    setStage(apiSnapshot.stage);
    setRound(apiSnapshot.round);
    if (apiSnapshot.commandResults.length > 0) setCommandResults(apiSnapshot.commandResults);
    setSelectedTrackId((current) => {
      const stillVisible = apiSnapshot.tracks.some((track) => track.trackId === current);
      const completed = apiSnapshot.missionFlow?.completedTargetIds.includes(current);
      if (stillVisible && !completed) return current;
      return apiSnapshot.missionFlow?.selectedTargetId
        ?? apiSnapshot.tracks[0]?.trackId
        ?? '';
    });
  }, [apiSnapshot]);

  const config: OperatorPanelConfig = useMemo(() => {
    const apiReady = Boolean(apiSnapshot && !apiError);
    const connectionState = apiReady ? (apiSnapshot?.dryRun ? 'dry-run' : 'live') : 'offline';
    return {
      apiBaseUrl: apiBaseUrl || 'backend-required',
      connectionState,
      dryRun: apiSnapshot?.dryRun ?? true,
      liveArmEnabled: apiSnapshot?.liveArmEnabled ?? (liveArmEnabled && apiReady),
    };
  }, [apiBaseUrl, apiError, apiSnapshot, liveArmEnabled]);

  const displayStage = apiSnapshot?.stage ?? stage;
  const displayRound = apiSnapshot?.round ?? round;
  const visibleTracks = apiSnapshot?.tracks ?? [];
  const authoritativeTargetId = apiSnapshot?.missionFlow?.selectedTargetId ?? '';
  const authoritativeTrack = visibleTracks.find(
    (track) => track.trackId === authoritativeTargetId,
  );
  const sensorFrames = apiSnapshot?.sensorFrames ?? [];
  const fusedSensorFrames = sensorFrames.filter((frame) => frame.sensor === 'fusion');
  const interpretedSensorFrames = fusedSensorFrames.length > 0 ? fusedSensorFrames : sensorFrames;
  const selectedLidarFrame = sensorFrames.find(
    (frame) => frame.sensor === 'lidar' && frame.trackId === authoritativeTargetId,
  ) ?? sensorFrames.find((frame) => frame.sensor === 'lidar');
  const liveLidarRangeM = apiSnapshot?.lidarReading?.distanceM
    ?? selectedLidarFrame?.rangeM
    ?? authoritativeTrack?.rangeM;
  const connectedSensorFramesEmpty = Boolean(apiSnapshot && sensorFrames.length === 0);
  const safety = apiSnapshot?.safety ?? {
    estop: false,
    motionZoneOk: false,
    fireZoneOk: false,
    targetGateOk: false,
    modeOk: false,
    backendConnected: false,
    perceptionConnected: false,
    sensorAdapterConnected: false,
    dryRun: true,
    liveArmEnabled: false,
    blockReason: 'BLOCKED_BACKEND' as const,
    explanation: 'Backend snapshot yok; panel fail-closed.',
  };
  const missionStatus = apiSnapshot?.missionFlow?.status ?? 'IDLE';
  const maintenanceSessionActive = missionStatus === 'MAINTENANCE';
  const operatorStopActive = missionStatus === 'PAUSED' || missionStatus === 'ESTOP_LATCHED';
  const safetyFireReady = canSendFireIntent(safety, authoritativeTrack?.trackId)
    && missionStatus === 'ACTIVE'
    && authoritativeTrack?.trackId === authoritativeTargetId;
  const isAutonomousFireStage = stageExpectedMode(displayStage) !== 'manual';
  const fireReady = safetyFireReady && Boolean(apiBaseUrl);
  const fireCaption = fireReady
    ? (isAutonomousFireStage ? 'Backend öncelikli hedef Hazır' : 'Manuel hedef sırası Hazır')
    : operatorBlockCopy[safety.blockReason];
  const maintenanceCountdownSeconds = apiSnapshot?.maintenanceRemainingBudgetSec ?? 0;
  const maintenanceReady = Boolean(
    apiBaseUrl
    && !apiBusy
    && missionStatus !== 'MAINTENANCE'
    && missionStatus !== 'ESTOP_LATCHED'
    && maintenanceCountdownSeconds >= 30,
  );
  const maintenanceStatusCopy = maintenanceSessionActive
    ? `Aktif · ${formatDuration(maintenanceCountdownSeconds)}`
    : `${formatDuration(maintenanceCountdownSeconds)} bütçe`;
  const telemetryMetadata = telemetryExport?.telemetry ?? apiSnapshot?.telemetry;
  const evidenceEntries = telemetryExport?.entries ?? replayBundle?.entries ?? [];
  const replayHardwareCount = replayBundle?.hardwareResults.length ?? 0;
  const replayCommandCount = replayBundle?.commandResults.length ?? 0;
  const replayEventCount = replayBundle?.events.length ?? 0;
  const unsafeReplayEvidence = Boolean(telemetryExport?.unsafeReplayEvidence || replayBundle?.unsafeReplayEvidence);
  const replayEvidenceWarning = telemetryExport?.evidenceWarning || replayBundle?.evidenceWarning;
  const readinessById = Object.fromEntries(
    (readinessReport?.items ?? []).map((item) => [item.id, item]),
  ) as Record<string, OperatorReadinessItem | undefined>;

  const pushResult = (result: CommandResult) => {
    setCommandResults((previous) => [
      result,
      ...previous.filter((item) => item.commandId !== result.commandId),
    ].slice(0, 8));
  };

  const loadTelemetryEvidence = async () => {
    if (!apiBaseUrl) {
      setEvidenceError('Backend API bağlantısı yok; export/replay için dry-run API başlatılmalı.');
      setEvidenceNotice('Yerel panel olay akışı görüntüleniyor.');
      return;
    }

    const [exported, replay, readiness] = await Promise.all([
      fetchOperatorTelemetryExport(apiBaseUrl),
      fetchOperatorReplay(apiBaseUrl),
      fetchOperatorReadiness(apiBaseUrl).catch((error: unknown) => {
        setReadinessError(error instanceof Error ? error.message : 'Readiness raporu alınamadı.');
        return undefined;
      }),
    ]);
    setTelemetryExport(exported);
    setReplayBundle(replay);
    if (readiness) {
      setReadinessReport(readiness);
      setReadinessError('');
    }
    setApiSnapshot(exported.state);
    if (exported.commandResults.length > 0) setCommandResults(exported.commandResults);
    setEvidenceError('');
    setEvidenceNotice('Kanıt paketi güncellendi; replay yalnız kayıt okur.');
  };

  const refreshTelemetryEvidence = () => {
    setEvidenceBusy(true);
    void loadTelemetryEvidence()
      .catch((error: unknown) => {
        setEvidenceError(error instanceof Error ? error.message : 'Telemetri kanıtı alınamadı.');
        setEvidenceNotice('');
      })
      .finally(() => setEvidenceBusy(false));
  };

  const resetTelemetryEvidence = () => {
    if (!apiBaseUrl) {
      setEvidenceError('Backend API bağlantısı yok; sıfırlama yalnız API üzerinden yapılır.');
      return;
    }

    setEvidenceBusy(true);
    void resetOperatorTelemetry(apiBaseUrl)
      .then(async (response) => {
        setApiSnapshot(response.state);
        setCommandResults(response.state.commandResults);
        setEvidenceNotice('Telemetri sıfırlandı; safe moda dönüldü ve fiziksel çıkış üretilmedi.');
        setEvidenceError('');
        const [exported, replay, readiness] = await Promise.all([
          fetchOperatorTelemetryExport(apiBaseUrl),
          fetchOperatorReplay(apiBaseUrl),
          fetchOperatorReadiness(apiBaseUrl).catch((error: unknown) => {
            setReadinessError(error instanceof Error ? error.message : 'Readiness raporu alınamadı.');
            return undefined;
          }),
        ]);
        setTelemetryExport(exported);
        setReplayBundle(replay);
        if (readiness) {
          setReadinessReport(readiness);
          setReadinessError('');
        }
      })
      .catch((error: unknown) => {
        setEvidenceError(error instanceof Error ? error.message : 'Telemetri sıfırlanamadı.');
        setEvidenceNotice('');
      })
      .finally(() => setEvidenceBusy(false));
  };

  const resetOperatorPanel = () => {
    setSelectedTrackId(authoritativeTargetId);
    setMaintenanceOpen(false);
    setEvidenceError('');
    setCommandApiError('');
    setRawCameraOpen(false);
    setEvidenceNotice('Görünüm backend snapshot durumuna yeniden eşitlendi; görev state değiştirilmedi.');
  };

  const recordStage = (nextStage: Stage, nextRound = 1) => {
    if (!apiBaseUrl) {
      setApiError('Backend API bağlantısı yok; StageRequest fail-closed.');
      return;
    }
    const boundedRound = Math.max(1, Math.min(stageRoundLimit(nextStage), nextRound));
    const request = makeStageRequest({
      stage: nextStage,
      round: boundedRound,
      dryRun: config.dryRun,
      reason: 'operator-stage-control',
    });
    setApiBusy(true);
    void sendOperatorStageRequest(apiBaseUrl, request)
      .then((response) => {
        pushResult(response.result);
        setApiSnapshot(response.state);
        setApiError('');
      })
      .catch((error: unknown) => {
        setApiError(error instanceof Error ? error.message : 'Backend StageRequest komutunu kabul etmedi.');
      })
      .finally(() => setApiBusy(false));
  };

  const sendManualAim = (panDeltaDeg: number, tiltDeltaDeg: number) => {
    if (!apiBaseUrl) {
      setApiError('Backend API bağlantısı yok; manuel yönelim fail-closed.');
      return;
    }
    setApiBusy(true);
    void sendOperatorManualAimCommand(apiBaseUrl, {
      kind: 'ManualAimCommand',
      panDeltaDeg,
      tiltDeltaDeg,
      rateLimitDegPerSec: 12,
      deadmanActive: true,
      dryRun: config.dryRun,
    })
      .then((response) => {
        pushResult(response.result);
        setApiSnapshot(response.state);
        setApiError('');
      })
      .catch((error: unknown) => {
        setApiError(error instanceof Error ? error.message : 'Manuel yönelim niyeti reddedildi.');
      })
      .finally(() => setApiBusy(false));
  };

  const sendFireIntent = () => {
    if (!apiBaseUrl || !authoritativeTrack || !fireReady) {
      setApiError('Backend-selected hedef veya Safety izni yok; FireIntent gönderilmedi.');
      return;
    }
    const intent = makeFireIntent({
      targetId: authoritativeTrack.trackId,
      stage: displayStage,
      round: displayRound,
      dryRun: config.dryRun,
    });
    setApiBusy(true);
    void sendOperatorFireIntent(apiBaseUrl, intent)
      .then((response) => {
        pushResult(response.result);
        setApiSnapshot(response.state);
        setLastHardwareResult(response.hardwareResult ?? undefined);
        setApiError('');
      })
      .catch((error: unknown) => {
        setLastHardwareResult(undefined);
        setApiError(error instanceof Error ? error.message : 'Backend FireIntent komutunu kabul etmedi.');
      })
      .finally(() => setApiBusy(false));
  };

  const triggerOperatorStop = () => {
    if (!apiBaseUrl) {
      setApiError('Backend API bağlantısı yok; kontrollü stop doğrulanamadı.');
      return;
    }
    setApiBusy(true);
    void sendMissionStop(apiBaseUrl)
      .then((response) => {
        setApiSnapshot(response.state);
        setApiError(response.accepted ? '' : 'Backend görev stop geçişini reddetti.');
      })
      .catch((error: unknown) => setApiError(error instanceof Error ? error.message : 'Görev durdurulamadı.'))
      .finally(() => setApiBusy(false));
  };

  const handleEStop = () => {
    if (!apiBaseUrl) {
      setApiError('Backend API bağlantısı yok. Fiziksel E-Stop birincil güvence olarak kullanılmalıdır.');
      return;
    }
    setApiBusy(true);
    void sendOperatorEStop(apiBaseUrl, { active: true })
      .then((response) => {
        setApiSnapshot(response.state);
        setApiError('');
      })
      .catch((error: unknown) => setApiError(error instanceof Error ? error.message : 'Yazılım E-Stop doğrulanamadı.'))
      .finally(() => setApiBusy(false));
  };

  const resumeOperatorStop = () => {
    if (!apiBaseUrl || missionStatus !== 'PAUSED') return;
    setApiBusy(true);
    void sendMissionResume(apiBaseUrl)
      .then((response) => {
        setApiSnapshot(response.state);
        setApiError(response.accepted ? '' : 'Backend devam geçişini reddetti.');
      })
      .catch((error: unknown) => setApiError(error instanceof Error ? error.message : 'Görev devam ettirilemedi.'))
      .finally(() => setApiBusy(false));
  };

  const finishMaintenanceSession = () => {
    if (!apiBaseUrl || !maintenanceSessionActive) return;
    setApiBusy(true);
    void sendMaintenanceEnd(apiBaseUrl)
      .then((response) => {
        setApiSnapshot(response.state);
        setMaintenanceOpen(false);
        setApiError(response.accepted ? '' : 'Backend bakım bitişini reddetti.');
      })
      .catch((error: unknown) => setApiError(error instanceof Error ? error.message : 'Bakım bitirilemedi.'))
      .finally(() => setApiBusy(false));
  };

  const openMaintenance = () => {
    if (!apiBaseUrl || !maintenanceReady) return;
    setApiBusy(true);
    void sendMaintenanceRequest(apiBaseUrl)
      .then((response) => {
        setApiSnapshot(response.state);
        setMaintenanceOpen(response.accepted);
        setApiError(response.accepted ? '' : 'Backend bakım geçişini reddetti.');
      })
      .catch((error: unknown) => setApiError(error instanceof Error ? error.message : 'Bakım başlatılamadı.'))
      .finally(() => setApiBusy(false));
  };

  useEffect(() => {
    const lockPage = maintenanceSessionActive || operatorStopActive;
    if (!lockPage) return;
    const previousBodyOverflow = document.body.style.overflow;
    const previousRootOverflow = document.documentElement.style.overflow;
    document.body.style.overflow = 'hidden';
    document.documentElement.style.overflow = 'hidden';
    return () => {
      document.body.style.overflow = previousBodyOverflow;
      document.documentElement.style.overflow = previousRootOverflow;
    };
  }, [maintenanceSessionActive, operatorStopActive]);

  if (rawCameraOpen) {
    return <RawCameraDiagnosticPage streamUrl={cameraStreamUrl} onBack={() => setRawCameraOpen(false)} />;
  }

  return (
    <main className="operator-shell min-h-screen bg-[#05070a] p-3 text-[#ecf7ff]" data-testid="operator-panel" data-desktop-shell={isDesktopShell ? 'true' : 'false'}>
      <MissionHeader
        apiBusy={apiBusy}
        config={config}
        stage={displayStage}
        mode={mode}
        round={displayRound}
        onRawCameraOpen={() => setRawCameraOpen(true)}
        onReset={resetOperatorPanel}
        missionRemainingSeconds={apiSnapshot?.missionRemainingSeconds}
      />
      {(apiError || readinessError) && (
        <div
          role="status"
          className="mb-3 rounded-xl border border-[#ff4757]/30 bg-[#ff4757]/10 p-3 text-sm font-bold text-[#ffbdc4]"
          data-testid="operator-backend-error"
        >
          {apiError || readinessError}
        </div>
      )}

      <section className="operator-primary-grid">
        <section className="operator-3d-panel rounded-xl border border-[#48a8ff]/18 bg-[rgba(7,10,14,.94)] p-0" data-testid="operator-sensor-fusion-panel" aria-label="Kamera ve 1D LiDAR yazılım füzyon katmanı">
          {displayStage === 1 ? (
            <Stage1CameraSupport
              streamUrl={cameraStreamUrl}
              lidarRangeM={liveLidarRangeM}
              lidarLive={apiSnapshot?.lidarReading?.status === 'LIVE_ACCEPTED'}
              correctionDeg={apiSnapshot?.ballisticCompensation?.elevationCorrectionDeg}
              calibrationActive={apiSnapshot?.ballisticCompensation?.active ?? false}
            />
          ) : (
            <SensorFusion3DView
              stage={displayStage}
              frames={interpretedSensorFrames}
              selectedTrackId={selectedTrackId}
              shotTrackIds={shotTrackIds}
              onSelect={setSelectedTrackId}
              connectedSensorFramesEmpty={connectedSensorFramesEmpty}
            />
          )}
        </section>

        <aside className="operator-side-rail">
          <CommandConsole
            displayStage={displayStage}
            displayRound={displayRound}
            apiBusy={apiBusy}
            fireReady={fireReady}
            fireCaption={fireCaption}
            operatorStopActive={operatorStopActive}
            maintenanceReady={maintenanceReady}
            maintenanceStatusCopy={maintenanceStatusCopy}
            onRecordStage={recordStage}
            onSendFireIntent={sendFireIntent}
            onTriggerOperatorStop={triggerOperatorStop}
            onOpenMaintenance={openMaintenance}
            onManualAim={sendManualAim}
            manualAimReady={Boolean(
              apiBaseUrl
              && displayStage === 1
              && mode === 'manual'
              && missionStatus === 'ACTIVE'
              && !safety.estop
            )}
            turretCalibration={apiSnapshot?.turretCalibration}
            stageRoundLimit={stageRoundLimit}
          >
            <TrackList
              tracks={visibleTracks}
              selectedTrackId={selectedTrackId}
              authoritativeTargetId={authoritativeTargetId}
              onSelect={setSelectedTrackId}
            />
            <OperatorTrackScene
              compact
              stage={displayStage}
              tracks={visibleTracks}
              selectedTrackId={selectedTrackId}
              shotTrackIds={shotTrackIds}
              onSelect={setSelectedTrackId}
            />
          </CommandConsole>
        </aside>
      </section>

      <ConfidencePanel stage={displayStage} frames={interpretedSensorFrames} selectedTrackId={selectedTrackId} />

      <section className="operator-utility-grid mt-3 grid gap-3 min-[1100px]:grid-cols-[minmax(0,.75fr)_minmax(0,.75fr)_minmax(0,1fr)]">
        <SafetyAuthorityPanel
            safety={safety}
            onEStop={handleEStop}
            eStopBusy={apiBusy}
          />

        <ReadinessDashboard
          maintenanceOpen={maintenanceOpen}
          setMaintenanceOpen={setMaintenanceOpen}
          readinessById={readinessById}
          config={config}
        />

        <EventStream commandResults={commandResults} />
      </section>

      <HardwareHealthBadge apiBaseUrl={apiBaseUrl ?? ''} snapshot={apiSnapshot} />

      <details className="mt-3 rounded-xl border border-[#48a8ff]/18 bg-[rgba(7,10,14,.94)] p-4" data-testid="operator-evidence-drawer">
        <summary className="cursor-pointer list-none text-xl font-black text-[#d7efff]">
          Kayıt / Replay
          <span className="ml-2 rounded-full border border-[#48a8ff]/25 bg-[#48a8ff]/10 px-2 py-1 align-middle text-xs text-[#bfe7ff]">Log</span>
        </summary>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button className="rounded-lg border border-[#48a8ff]/30 bg-[#48a8ff]/10 px-3 py-2 text-sm font-black text-[#cbe9ff] disabled:cursor-not-allowed disabled:opacity-45" disabled={!apiBaseUrl || evidenceBusy} onClick={refreshTelemetryEvidence}>
            {evidenceBusy ? 'Kanıt alınıyor' : 'Kanıtı Yenile'}
          </button>
          <button className="rounded-lg border border-[#ffbb42]/30 bg-[#ffbb42]/10 px-3 py-2 text-sm font-black text-[#ffe4ad] disabled:cursor-not-allowed disabled:opacity-45" disabled={!apiBaseUrl || evidenceBusy} onClick={resetTelemetryEvidence}>
            Telemetriyi Sıfırla
          </button>
        </div>
        {!apiBaseUrl && <p className="m-0 mt-3 rounded-lg border border-[#ffbb42]/25 bg-[#ffbb42]/10 p-3 text-sm font-bold text-[#ffe4ad]">Backend API yok: panel yerel dry-run modunda. Export/replay için `operatorApi` veya VITE_GOKKALKAN_OPERATOR_API_BASE gerekir.</p>}
        {evidenceError && <p className="m-0 mt-3 rounded-lg border border-[#ff4757]/25 bg-[#ff4757]/10 p-3 text-sm font-bold text-[#ffbdc4]">{evidenceError}</p>}
        {evidenceNotice && !evidenceError && <p className="m-0 mt-3 rounded-lg border border-[#33e68c]/25 bg-[#33e68c]/10 p-3 text-sm font-bold text-[#bfffe0]">{evidenceNotice}</p>}
        {unsafeReplayEvidence && <p className="m-0 mt-3 rounded-lg border border-[#ff4757]/30 bg-[#ff4757]/10 p-3 text-sm font-black text-[#ffbdc4]">{replayEvidenceWarning || 'Replay kanıtı güvenli değil: physicalOutput=true kaydı görüldü.'}</p>}
        <div className="mt-3 grid gap-2 text-sm min-[760px]:grid-cols-2">
          <EvidenceRow label="JSONL kayıt yolu" value={telemetryMetadata?.path ?? 'Henüz backend kanıtı alınmadı'} />
          <EvidenceRow label="Kayıt sayısı" value={String(telemetryMetadata?.recordCount ?? evidenceEntries.length)} />
          <EvidenceRow label="Replay özeti" value={`${replayEventCount} olay · ${replayCommandCount} komut · ${replayHardwareCount} dry-run hardware sonucu`} />
          <EvidenceRow label="Fiziksel çıkış" value={(telemetryExport?.physicalOutputEnabled ?? replayBundle?.physicalOutputEnabled ?? apiSnapshot?.physicalOutputEnabled) ? 'AÇIK' : 'KAPALI / YOK'} />
        </div>
        <div className="mt-3 grid max-h-64 gap-2 overflow-auto pr-1" aria-label="Replay kayıtları">
          {evidenceEntries.length === 0 && <p className="m-0 rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-sm text-[#91a6b7]">Henüz export/replay kaydı alınmadı.</p>}
          {evidenceEntries.slice(0, 8).map((record, index) => (
            <article key={`${record.recordId ?? index}-${record.timestamp ?? 'no-time'}`} className="rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-xs">
              <b className="text-[#d7efff]">{record.recordType}</b>
              <small className="ml-2 text-[#91a6b7]">{record.timestamp ?? 'timestamp yok'}</small>
              <p className="m-0 mt-1 break-words text-[#c8d8e2]">{shortRecordPayload(record)}</p>
            </article>
          ))}
        </div>
      </details>

      {maintenanceSessionActive && (
        <div className="operator-lock-overlay operator-lock-overlay-maintenance" data-testid="operator-maintenance-overlay" role="dialog" aria-modal="true" aria-label="Bakım oturumu">
          <section className="operator-lock-card">
            <span>BAKIM</span>
            <b data-testid="operator-maintenance-countdown">{formatDuration(maintenanceCountdownSeconds)}</b>
            <p data-testid="operator-maintenance-sessions-left">KALAN BÜTÇE: {formatDuration(maintenanceCountdownSeconds)}</p>
            <button type="button" data-testid="operator-maintenance-finish-button" onClick={finishMaintenanceSession}>
              Bakımı Bitir
            </button>
          </section>
        </div>
      )}

      {operatorStopActive && (
        <div className="operator-lock-overlay operator-lock-overlay-emergency" data-testid="operator-stop-overlay" role="dialog" aria-modal="true" aria-label="Acil durdurma">
          <section className="operator-lock-card">
            <span>{missionStatus === 'ESTOP_LATCHED' ? 'ACİL DURDUR' : 'GÖREV DURAKLATILDI'}</span>
            <b>KİLİTLİ</b>
            {missionStatus === 'PAUSED' ? (
              <button type="button" data-testid="operator-stop-resume-button" onClick={resumeOperatorStop}>
                DEVAM ET
              </button>
            ) : (
              <p>Fiziksel sinyal bırakılmalı ve kontrollü backend reset uygulanmalıdır.</p>
            )}
          </section>
        </div>
      )}
    </main>
  );
}

function EvidenceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/[.07] bg-white/[.04] p-3">
      <span className="block text-xs font-black uppercase tracking-[.12em] text-[#91a6b7]">{label}</span>
      <b className="mt-1 block break-words text-[#eaf7ff]">{value}</b>
    </div>
  );
}
