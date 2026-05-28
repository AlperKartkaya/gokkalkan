import { type CSSProperties, type PointerEvent, type WheelEvent, useEffect, useMemo, useRef, useState } from 'react';
import gokkalkanIconUrl from '../assets/gokkalkan_icon.png';
import { COMPETITION_COURSE } from './competitionCourse';
import {
  canSendFireIntent,
  evaluateOperatorSafety,
  makeCommandResult,
  makeFireIntent,
  makeStageRequest,
  operatorBlockCopy,
  stageExpectedMode,
  stageRoundLimit,
  type CommandResult,
  type FireIntent,
  type OperatorPanelConfig,
  type OperatorSensorFrame,
  type OperatorSensorHealth,
  type OperatorTrackState,
} from './operatorContracts';
import {
  fetchOperatorReplay,
  fetchOperatorReadiness,
  fetchOperatorSnapshot,
  fetchOperatorTelemetryExport,
  resetOperatorTelemetry,
  sendOperatorFireIntent,
  sendOperatorModeRequest,
  sendOperatorStageRequest,
  type HardwareResult,
  type OperatorApiSnapshot,
  type OperatorReplayBundle,
  type OperatorReadinessItem,
  type OperatorReadinessReport,
  type OperatorReadinessStatus,
  type OperatorTelemetryExport,
  type OperatorTelemetryLogRecord,
} from './operatorApiClient';
import type { Mode, Stage, TargetType } from './types';

const targetLabel: Record<TargetType, string> = {
  F16: 'Savaş Uçağı / F16',
  Helikopter: 'Helikopter',
  'Balistik Füze': 'Balistik Füze',
  'Mini/Micro İHA': 'Mini/Micro İHA',
};

const dryRunTracksByStage: Record<Stage, OperatorTrackState[]> = {
  1: [
    { trackId: 'S1-ORDER-FUZE-01', stage: 1, round: 1, targetType: 'Balistik Füze', friendFoe: 'Düşman', rangeM: 15, bearingDeg: -24, confidence: 0.86, source: 'dry-run', updatedAt: '2026-05-25T20:00:00.000Z' },
    { trackId: 'S1-ORDER-HEL-02', stage: 1, round: 1, targetType: 'Helikopter', friendFoe: 'Düşman', rangeM: 10, bearingDeg: -7, confidence: 0.84, source: 'dry-run', updatedAt: '2026-05-25T20:00:00.000Z' },
    { trackId: 'S1-ORDER-F16-03', stage: 1, round: 1, targetType: 'F16', friendFoe: 'Düşman', rangeM: 5, bearingDeg: 10, confidence: 0.82, source: 'dry-run', updatedAt: '2026-05-25T20:00:00.000Z' },
    { trackId: 'S1-ORDER-UAV-04', stage: 1, round: 1, targetType: 'Mini/Micro İHA', friendFoe: 'Düşman', rangeM: 5, bearingDeg: 27, confidence: 0.8, source: 'dry-run', updatedAt: '2026-05-25T20:00:00.000Z' },
  ],
  2: [
    { trackId: 'S2-R1-L1-BALISTIK', stage: 2, round: 1, targetType: 'Balistik Füze', friendFoe: 'Düşman', rangeM: 14.2, bearingDeg: -28, confidence: 0.78, source: 'fused', updatedAt: '2026-05-25T20:00:00.000Z' },
    { trackId: 'S2-R1-L2-UAV', stage: 2, round: 1, targetType: 'Mini/Micro İHA', friendFoe: 'Düşman', rangeM: 11.6, bearingDeg: 2, confidence: 0.74, source: 'radar-lidar', updatedAt: '2026-05-25T20:00:00.000Z' },
    { trackId: 'S2-R1-L3-UAV', stage: 2, round: 1, targetType: 'Mini/Micro İHA', friendFoe: 'Düşman', rangeM: 8.9, bearingDeg: 31, confidence: 0.72, source: 'radar-lidar', updatedAt: '2026-05-25T20:00:00.000Z' },
  ],
  3: [
    { trackId: 'DRY-RUN-F16-01', stage: 3, round: 1, targetType: 'F16', friendFoe: 'Düşman', rangeM: 12.4, bearingDeg: -18, confidence: 0.96, source: 'fused', updatedAt: '2026-05-25T20:00:00.000Z' },
    { trackId: 'DRY-RUN-HEL-02', stage: 3, round: 1, targetType: 'Helikopter', friendFoe: 'Dost', rangeM: 8.1, bearingDeg: 4, confidence: 0.91, source: 'fused', updatedAt: '2026-05-25T20:00:00.000Z' },
    { trackId: 'DRY-RUN-UAV-03', stage: 3, round: 1, targetType: 'Mini/Micro İHA', friendFoe: 'Bilinmeyen', rangeM: 4.2, bearingDeg: 23, confidence: 0.42, source: 'radar-lidar', updatedAt: '2026-05-25T20:00:00.000Z' },
  ],
};

const dryRunTracks = dryRunTracksByStage[3];

const localSensorHealth: OperatorSensorHealth = {
  schemaVersion: 1,
  status: 'replay',
  adapterConnected: false,
  perceptionConnected: false,
  replayOnly: true,
  sourceDataset: 'Gökkalkan recorded-style dry-run fixture; gerçek radar/LiDAR adapterı bağlandığında aynı SensorFrame sözleşmesi canlı akışa döner.',
  latestFrameAt: '2026-05-25T20:00:00.000Z',
  frameCount: 0,
  physicalOutputEnabled: false,
};

function sensorSourceLabel(sensorHealth: OperatorSensorHealth, safetySensorConnected: boolean) {
  if (sensorHealth.status === 'live' && !sensorHealth.replayOnly && (sensorHealth.adapterConnected || safetySensorConnected)) {
    return 'Canlı';
  }
  if (sensorHealth.replayOnly || sensorHealth.status === 'replay') return 'Replay';
  if (sensorHealth.status === 'empty') return 'Veri yok';
  return 'Beklemede';
}

function affiliationClass(friendFoe: OperatorTrackState['friendFoe']) {
  if (friendFoe === 'Düşman') return 'enemy';
  if (friendFoe === 'Dost') return 'friend';
  return 'unknown';
}

function isTrackUnidentified(track: Pick<OperatorTrackState, 'friendFoe' | 'confidence'>) {
  return track.friendFoe === 'Bilinmeyen' || track.confidence < 0.6;
}

function isFrameUnidentified(frame: Pick<OperatorSensorFrame, 'friendFoe' | 'classificationConfidence'>) {
  return frame.friendFoe === 'Bilinmeyen' || frame.classificationConfidence < 0.6;
}

function hostilityConfidence(frame: OperatorSensorFrame) {
  return isFrameUnidentified(frame) ? Math.max(0.52, 1 - frame.classificationConfidence) : frame.quality;
}

function sensorRecommendation(track: OperatorTrackState, stage: Stage) {
  if (track.friendFoe === 'Dost') return 'Dost unsur korunur; FireIntent kilitli.';
  if (track.friendFoe === 'Bilinmeyen') return 'Kimlik kesinleşmeden FireIntent kilitli; yazılım katmanı sınıf/dost-düşman güvenini izler.';
  if (stage === 2) return 'Aşama 2: sınıflandırma zorunlu değil; takip/imha önceliği.';
  if (stage === 1) return 'Aşama 1: operatör manuel yönlendirme ve ateş niyetiyle ilerler.';
  return targetRangeGateOk(track) ? 'Aşama 3: düşman ve menzil uygun; Safety Gate beklenir.' : 'Aşama 3: hedef izlenir, menzil kapısı beklenir.';
}

function makeLocalSensorFrames(stage: Stage, round: number): OperatorSensorFrame[] {
  return dryRunTracksByStage[stage].flatMap((track, index) => {
    const sourceDataset = stage === 3
      ? 'Gökkalkan recorded-style radar/LiDAR replay; Oxford Radar RobotCar ve nuScenes benzeri offline veriler bu şemaya map edilebilir.'
      : 'Gökkalkan recorded-style dry-run replay; gerçek sensör adapterı TBD.';
    const unidentified = isTrackUnidentified(track);
    const rangeGate = unidentified ? 'Kimlik bekleniyor' : stage === 2 ? 'Takip önceliği' : stage === 3 ? (targetRangeGateOk(track) ? 'Uygun' : 'Kilitli') : 'Manuel hedef sırası';
    const typeConfidence = unidentified ? Math.min(track.confidence, 0.45) : stage === 2 ? 0.52 : track.confidence;
    const hostilityConfidence = unidentified ? Math.max(0.52, 1 - typeConfidence) : track.confidence;
    return [
      {
        frameId: `LOCAL-S${stage}-R${round}-${index + 1}-RADAR`,
        stage,
        round,
        trackId: track.trackId,
        sensor: 'radar',
        timestamp: track.updatedAt,
        rangeM: track.rangeM,
        bearingDeg: track.bearingDeg,
        elevationDeg: 0.4 + index * 0.2,
        radialVelocityMps: -4.8 + index,
        rcsDbsm: track.friendFoe === 'Düşman' ? 13.5 - index : 5.2,
        snrDb: 23 - index,
        pointCount: 0,
        quality: Math.min(0.98, hostilityConfidence + 0.01),
        targetType: track.targetType,
        friendFoe: track.friendFoe,
        classificationConfidence: typeConfidence,
        rangeGate,
        recommendation: sensorRecommendation(track, stage),
        sourceDataset,
        replayOnly: true,
        rawSampleRef: `local/stage-${stage}/round-${round}/radar/${track.trackId}`,
      },
      {
        frameId: `LOCAL-S${stage}-R${round}-${index + 1}-FUSION`,
        stage,
        round,
        trackId: track.trackId,
        sensor: 'fusion',
        timestamp: track.updatedAt,
        rangeM: track.rangeM,
        bearingDeg: track.bearingDeg,
        elevationDeg: 0.3 + index * 0.1,
        radialVelocityMps: -4.5 + index,
        rcsDbsm: track.friendFoe === 'Düşman' ? 12 - index : 5,
        snrDb: 21 - index,
        pointCount: 86 + index * 24,
        quality: hostilityConfidence,
        targetType: track.targetType,
        friendFoe: track.friendFoe,
        classificationConfidence: typeConfidence,
        rangeGate,
        recommendation: sensorRecommendation(track, stage),
        sourceDataset,
        replayOnly: true,
        rawSampleRef: `local/stage-${stage}/round-${round}/fusion/${track.trackId}`,
      },
    ];
  });
}

const readinessCopy: Record<OperatorReadinessStatus, string> = {
  ready: 'Hazır',
  partial: 'Kısmi',
  tbd: 'TBD',
  blocked: 'Kilitli',
};

function readinessTone(status: OperatorReadinessStatus) {
  if (status === 'ready') return 'border-[#33e68c]/30 bg-[#33e68c]/10 text-[#bfffe0]';
  if (status === 'partial') return 'border-[#ffbb42]/30 bg-[#ffbb42]/10 text-[#ffe4ad]';
  if (status === 'blocked') return 'border-[#ff4757]/30 bg-[#ff4757]/10 text-[#ffbdc4]';
  return 'border-[#48a8ff]/30 bg-[#48a8ff]/10 text-[#cbe9ff]';
}

function operatorXForRange(range: number) {
  return 88 - range * 5;
}

function clampPercent(value: number, min = 7, max = 93) {
  return Math.min(max, Math.max(min, value));
}

function clampNumber(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
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
  const size = isTrackUnidentified(track) ? { w: 6.2, h: 6.2 } : visualSizeForTarget(track.targetType);
  const x = stage === 1
    ? clampPercent(operatorXForRange(track.rangeM) + (index % 2 === 0 ? -2.4 : 2.4), 12, 82)
    : clampPercent(operatorXForRange(track.rangeM) + Math.sin(radians) * 7, 13, 72);
  const y = stage === 1
    ? clampPercent(35 + index * 8, 24, 74)
    : clampPercent(30 + index * 13.5 + Math.sin(radians) * 4, 26, 78);
  const rangeGate = targetRangeGateOk(track) ? 'Uygun' : track.rangeM > 15 ? 'Erken' : 'Geçersiz';
  const candidate = track.friendFoe === 'Düşman' && (stage === 1 || stage === 2 || targetRangeGateOk(track));
  const lane = ((index % 3) + 1) as 1 | 2 | 3;
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
const OPERATOR_SYSTEM_POSITION = { x: 91, y: 50 };

function domeRotationForVisualTrack(track?: ReturnType<typeof visualTrackFor>) {
  if (!track) return DOME_DEFAULT_ROTATION_DEG;
  const targetAngle = (Math.atan2(track.y - OPERATOR_SYSTEM_POSITION.y, track.x - OPERATOR_SYSTEM_POSITION.x) * 180) / Math.PI;
  return targetAngle - DOME_SOURCE_NOSE_SCREEN_DEG;
}

function targetRangeGateOk(track: OperatorTrackState | undefined) {
  if (!track) return false;
  if (track.targetType === 'F16') return track.rangeM >= 10 && track.rangeM <= 15;
  if (track.targetType === 'Helikopter' || track.targetType === 'Balistik Füze') return track.rangeM >= 5 && track.rangeM <= 15;
  if (track.targetType === 'Mini/Micro İHA') return track.rangeM >= 0 && track.rangeM <= 15;
  return false;
}

function targetGateOkForStage(stage: Stage, track: OperatorTrackState | undefined) {
  if (!track || track.friendFoe !== 'Düşman') return false;
  if (stage === 1 || stage === 2) return track.rangeM > 0 && track.rangeM <= 15;
  return targetRangeGateOk(track);
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
  if (isFrameUnidentified(frame)) {
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

function commandLabel(result: CommandResult) {
  if (result.kind === 'FireIntent') return 'FireIntent';
  if (result.kind === 'ManualAimCommand') return 'ManualAimCommand';
  if (result.kind === 'StageRequest') return 'StageRequest';
  return 'ModeRequest';
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
  lastIntent,
  onSelect,
  compact = false,
}: {
  stage: Stage;
  tracks: OperatorTrackState[];
  selectedTrackId: string;
  lastIntent?: FireIntent;
  onSelect: (trackId: string) => void;
  compact?: boolean;
}) {
  const visualTracks = tracks.map((track, index) => visualTrackFor(track, index, stage));
  const selectedVisualTrack = visualTracks.find((track) => track.trackId === selectedTrackId) ?? visualTracks[0];
  const firedVisualTrack = visualTracks.find((track) => track.trackId === lastIntent?.targetId);
  const ruleWindow = selectedVisualTrack && stage !== 1
    ? { start: Math.min(operatorXForRange(15), operatorXForRange(5)), width: Math.abs(operatorXForRange(5) - operatorXForRange(15)) }
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
      <div className="relative z-[2] flex flex-wrap items-start justify-between gap-3 p-5 pb-2">
        <div>
          <h2 className="m-0 text-2xl font-black">Görüntü</h2>
        </div>
      </div>

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
            <text className="stage1-title" x="9" y="10">A1 · MANUEL ATIŞ</text>
          </g>
        ) : (
          <g className="moving-course-field">
            {selectedVisualTrack && (
              <>
                <rect className={`valid-window ${selectedVisualTrack.candidate ? 'active' : ''}`} x={ruleWindow.start} y="15" width={ruleWindow.width} height="77" />
                <text className={`window-label ${selectedVisualTrack.candidate ? 'active' : ''}`} x={Math.min(84, Math.max(16, ruleWindow.start + ruleWindow.width / 2))} y="18.2" textAnchor="middle">
                  {visualRangeLabel(selectedVisualTrack)}
                </text>
              </>
            )}
            {[15, 10, 5].map((range) => (
              <g key={range} className={`range-line ${selectedVisualTrack?.candidate && Math.abs(selectedVisualTrack.rangeM - range) <= 2.5 ? 'active' : ''}`} data-testid={`operator-range-${range}m`}>
                <line x1={operatorXForRange(range)} y1="10" x2={operatorXForRange(range)} y2="93" />
                <text x={operatorXForRange(range) + 0.7} y="12">{range} m</text>
              </g>
            ))}
            <text className="point-label" x="7" y="12">A</text>
            <text className="point-label" x="78" y="12">B</text>
            <text className="escape-label" x="70" y="91">B KAÇIŞ</text>
            {COMPETITION_COURSE.lanes.map((lane) => (
              <g key={lane.lane} className={`lane-path lane-${lane.lane}`}>
                <polyline points={lane.points.map((point) => `${point.x},${point.y}`).join(' ')} markerEnd={`url(#operator-arrow-${stage})`} />
                <text x="8" y={lane.points[0].y - 2}>KOL {lane.lane}</text>
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
        {firedVisualTrack && (
          <g className="strike hit" data-testid="operator-shot-trace">
            <line className="shot-trail" x1={OPERATOR_SYSTEM_POSITION.x} y1={OPERATOR_SYSTEM_POSITION.y} x2={firedVisualTrack.x} y2={firedVisualTrack.y} />
            <circle className="shot-bullet" cx={OPERATOR_SYSTEM_POSITION.x} cy={OPERATOR_SYSTEM_POSITION.y} r="1.05">
              <animate attributeName="cx" from={OPERATOR_SYSTEM_POSITION.x} to={firedVisualTrack.x} dur="0.26s" fill="freeze" />
              <animate attributeName="cy" from={OPERATOR_SYSTEM_POSITION.y} to={firedVisualTrack.y} dur="0.26s" fill="freeze" />
            </circle>
            <circle className="impact-ring" cx={firedVisualTrack.x} cy={firedVisualTrack.y} r="2.8" />
            <text x={Math.min(88, firedVisualTrack.x + 2)} y={Math.max(9, firedVisualTrack.y - 2)}>KAYIT</text>
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
          const unknown = isTrackUnidentified(track);
          const statusText = unknown ? 'kimlik bekliyor' : `${targetLabel[track.targetType]} ${track.friendFoe}`;
          return (
            <button
              key={track.trackId}
              className={`aircraft absolute z-[6] grid min-h-[62px] min-w-[58px] -translate-x-1/2 -translate-y-1/2 content-center place-items-center rounded-full border-0 bg-transparent p-0.5 text-center shadow-none transition-[color,filter,transform] duration-150 will-change-[left,top] ${affiliationClass(track.friendFoe)} ${unknown ? 'unknown-object' : ''} ${stage !== 1 ? 'moving' : 'stationary'} ${selected ? 'selected' : ''} ${track.candidate ? 'candidate' : ''}`}
              style={{ left: `${track.x}%`, top: `${track.y}%`, width: `${track.w}%`, height: `${track.h}%` }}
              data-testid={`operator-track-${track.trackId}`}
              data-track-id={track.trackId}
              data-affiliation={track.friendFoe}
              data-identification={unknown ? 'unknown' : 'identified'}
              aria-label={`${track.trackId} ${statusText} ${track.rangeM.toFixed(1)} metre`}
              onClick={() => onSelect(track.trackId)}
            >
              <span className="motion-trail" />
              <span className="target-visual">{unknown ? <span className="target-unknown-sphere" aria-hidden="true" /> : <OperatorTargetSilhouette type={track.targetType} />}</span>
            </button>
          );
        })}
      </div>

      <div className="map-legend absolute bottom-3 left-3.5 z-[8] flex flex-wrap gap-1.5 rounded-lg border border-white/10 bg-[rgba(2,4,7,.76)] px-2 py-1.5 backdrop-blur">
        <span className="flex items-center gap-1.5 text-[11px] font-extrabold text-[#cde1ec]"><i className="enemy-dot" />Düşman</span>
        <span className="flex items-center gap-1.5 text-[11px] font-extrabold text-[#cde1ec]"><i className="friend-dot" />Dost</span>
        <span className="flex items-center gap-1.5 text-[11px] font-extrabold text-[#cde1ec]"><i className="unknown-dot" />Bilinmeyen</span>
        <span className="flex items-center gap-1.5 text-[11px] font-extrabold text-[#cde1ec]"><i className="window-dot" />Menzil</span>
      </div>
    </section>
  );
}

function SensorFusion3DView({
  frames,
  selectedTrackId,
  onSelect,
  sensorHealth,
  sensorSource,
  connectedSensorFramesEmpty,
}: {
  frames: OperatorSensorFrame[];
  selectedTrackId: string;
  onSelect: (trackId: string) => void;
  sensorHealth: OperatorSensorHealth;
  sensorSource: string;
  connectedSensorFramesEmpty: boolean;
}) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const glResourcesRef = useRef<SensorGlResources | undefined>(undefined);
  const [view, setView] = useState<SensorViewState>(defaultSensorView);
  const [dragState, setDragState] = useState<SensorDragState>();
  const [renderTick, setRenderTick] = useState(0);
  const [webglAvailable, setWebglAvailable] = useState(true);
  const [overlayPoints, setOverlayPoints] = useState<SensorOverlayPoint[]>([]);

  const zoomLevel = SENSOR_DEFAULT_DISTANCE / view.distance;

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
      const result = renderSensorWebGlScene(gl, resources, frames, selectedTrackId, view);
      setOverlayPoints((current) => (overlayPointsEqual(current, result.overlayPoints) ? current : result.overlayPoints));
    } catch (error) {
      console.warn('Radar/LiDAR WebGL çizimi devre dışı kaldı:', error);
      setWebglAvailable(false);
    }
  }, [frames, selectedTrackId, view, renderTick]);

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

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
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

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    if (!dragState || dragState.pointerId !== event.pointerId) return;
    const deltaX = event.clientX - dragState.startX;
    const deltaY = event.clientY - dragState.startY;
    setView((current) => ({
      ...current,
      pitch: dragState.mode === 'orbit' ? clampNumber(dragState.basePitch - deltaY * 0.16, 22, 72) : current.pitch,
      yaw: dragState.mode === 'orbit' ? dragState.baseYaw + deltaX * 0.36 : current.yaw,
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
      aria-label="Etkileşimli üç boyutlu Radar LiDAR iz görüntüsü"
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={endPointerDrag}
      onPointerCancel={endPointerDrag}
      onWheel={handleWheel}
    >
      <canvas ref={canvasRef} className="sensor-3d-canvas" data-testid="operator-sensor-3d-canvas" aria-hidden="true" />
      <div className="sensor-3d-hud">
        <span>Radar / LiDAR</span>
        <b>3D SensorFrame</b>
        <small>Sürükle: döndür · Shift+sürükle: kaydır · Tekerlek: yakınlaştır</small>
      </div>
      <div className="sensor-3d-stats" aria-label="SensorFrame akış özeti">
        <span>{sensorSource}</span>
        <span>{sensorHealth.status} · replayOnly={String(sensorHealth.replayOnly)}</span>
        <span>{sensorHealth.frameCount} frame</span>
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
      {frames.map((frame, index) => {
        const fallbackPoint = sensorFrame3DPoint(frame, index);
        const point = overlayPoints[index] ?? {
          frameId: frame.frameId,
          trackId: frame.trackId,
          left: fallbackPoint.x,
          top: fallbackPoint.y,
          visible: true,
        };
        const selected = selectedTrackId === frame.trackId;
        const unknown = isFrameUnidentified(frame);
        return (
          <button
            key={frame.frameId}
            className={`sensor-3d-target ${affiliationClass(frame.friendFoe)} ${unknown ? 'unknown-object' : ''} ${selected ? 'selected' : ''} ${point.visible ? '' : 'is-off-axis'}`}
            data-testid={`operator-sensor-3d-target-${frame.trackId}`}
            data-track-id={frame.trackId}
            data-affiliation={frame.friendFoe}
            data-identification={unknown ? 'unknown' : 'identified'}
            data-type-confidence={frame.classificationConfidence.toFixed(2)}
            data-color-confidence={hostilityConfidence(frame).toFixed(2)}
            style={{ left: `${point.left}%`, top: `${point.top}%` }}
            aria-label={`${frame.trackId} ${unknown ? 'kimlik bekliyor' : targetLabel[frame.targetType]} ${frame.rangeM.toFixed(1)} metre`}
            onPointerDown={(event) => event.stopPropagation()}
            onClick={() => onSelect(frame.trackId)}
          />
        );
      })}
      {!webglAvailable && (
        <span className="sensor-3d-empty sensor-3d-webgl-warning">WebGL açılamadı; sensör akışı yazılım katmanında tutuluyor.</span>
      )}
      {(connectedSensorFramesEmpty || frames.length === 0) && (
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

function ConfidencePanel({ frames, selectedTrackId }: { frames: OperatorSensorFrame[]; selectedTrackId: string }) {
  const uniqueFrames = frames.filter((frame, index, all) => all.findIndex((candidate) => candidate.trackId === frame.trackId) === index);

  return (
    <section className="operator-confidence-panel rounded-xl border border-[#25d8ff]/18 bg-[rgba(7,10,14,.94)] p-4" data-testid="operator-confidence-panel" aria-label="Sınıf ve dost düşman doğruluk yüzdeleri">
      <p className="m-0 text-xs font-black uppercase tracking-[.16em] text-[#25d8ff]">DOĞRULUK</p>
      <div
        className="operator-confidence-grid mt-3"
        style={{ '--confidence-count': Math.max(1, uniqueFrames.length) } as CSSProperties}
      >
        {uniqueFrames.map((frame) => {
          const unknown = isFrameUnidentified(frame);
          const colorValue = hostilityConfidence(frame);
          const selected = frame.trackId === selectedTrackId;
          const displayType = unknown ? 'Bilinmeyen cisim' : targetLabel[frame.targetType];
          return (
            <article
              key={frame.trackId}
              className={`confidence-row rounded-lg border p-2.5 ${selected ? 'border-[#ffbb42]/35 bg-[#ffbb42]/10' : 'border-white/[.07] bg-white/[.04]'}`}
              data-testid={`operator-confidence-${frame.trackId}`}
              data-affiliation={frame.friendFoe}
              data-identification={unknown ? 'unknown' : 'identified'}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <b className="block overflow-hidden text-ellipsis whitespace-nowrap text-sm text-white">{displayType}</b>
                  <span className="block overflow-hidden text-ellipsis whitespace-nowrap text-xs font-black text-[#91a6b7]">{frame.friendFoe}</span>
                </div>
                <i className={`confidence-swatch ${affiliationClass(frame.friendFoe)}`} aria-hidden="true" />
              </div>
              <div className="accuracy-circle-grid mt-3">
                <AccuracyCircle
                  label="Renk"
                  value={colorValue}
                  tone={affiliationClass(frame.friendFoe)}
                  testId={`operator-accuracy-${frame.trackId}-color`}
                />
                <AccuracyCircle
                  label="Tip"
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
  const liveArmEnabled = import.meta.env.VITE_GOKKALKAN_OPERATOR_LIVE_ARMED === '1';
  const dryRun = true;
  const [mode, setMode] = useState<Mode>(stageExpectedMode(3));
  const [stage, setStage] = useState<Stage>(3);
  const [round, setRound] = useState(1);
  const [selectedTrackId, setSelectedTrackId] = useState(dryRunTracks[0]?.trackId ?? '');
  const [lastIntent, setLastIntent] = useState<FireIntent>();
  const [, setLastHardwareResult] = useState<HardwareResult>();
  const [operatorStopActive, setOperatorStopActive] = useState(false);
  const [maintenanceOpen, setMaintenanceOpen] = useState(false);
  const [apiSnapshot, setApiSnapshot] = useState<OperatorApiSnapshot>();
  const [apiError, setApiError] = useState('');
  const [apiBusy, setApiBusy] = useState(false);
  const [readinessReport, setReadinessReport] = useState<OperatorReadinessReport>();
  const [, setReadinessError] = useState('');
  const [telemetryExport, setTelemetryExport] = useState<OperatorTelemetryExport>();
  const [replayBundle, setReplayBundle] = useState<OperatorReplayBundle>();
  const [evidenceBusy, setEvidenceBusy] = useState(false);
  const [evidenceError, setEvidenceError] = useState('');
  const [evidenceNotice, setEvidenceNotice] = useState('');
  const [commandResults, setCommandResults] = useState<CommandResult[]>([
    makeCommandResult({
      commandId: 'BOOT-DRY-RUN',
      kind: 'ModeRequest',
      accepted: true,
      dryRun: true,
      safetyBlockReason: 'ALLOWED',
      createdAt: new Date('2026-05-25T20:00:00Z'),
    }),
  ]);

  useEffect(() => {
    if (!apiBaseUrl) {
      setApiSnapshot(undefined);
      setReadinessReport(undefined);
      setTelemetryExport(undefined);
      setReplayBundle(undefined);
      setApiError('');
      setReadinessError('');
      setEvidenceError('');
      setEvidenceNotice('Backend API bağlantısı olmadan yalnız yerel dry-run olay akışı gösterilir.');
      return;
    }

    let cancelled = false;
    setApiBusy(true);
    Promise.all([
      fetchOperatorSnapshot(apiBaseUrl),
      fetchOperatorReadiness(apiBaseUrl).catch((error: unknown) => {
        if (!cancelled) setReadinessError(error instanceof Error ? error.message : 'Readiness raporu alınamadı.');
        return undefined;
      }),
    ])
      .then(([snapshot, readiness]) => {
        if (cancelled) return;
        setApiSnapshot(snapshot);
        setReadinessReport(readiness);
        setApiError('');
        if (readiness) setReadinessError('');
        setMode(snapshot.mode);
        setStage(snapshot.stage);
        setRound(snapshot.round);
        if (snapshot.commandResults.length > 0) setCommandResults(snapshot.commandResults);
        if (snapshot.tracks[0] && !snapshot.tracks.some((track) => track.trackId === selectedTrackId)) {
          setSelectedTrackId(snapshot.tracks[0].trackId);
        }
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setApiSnapshot(undefined);
        setReadinessReport(undefined);
        setApiError(error instanceof Error ? error.message : 'Backend API bağlantısı kurulamadı.');
      })
      .finally(() => {
        if (!cancelled) setApiBusy(false);
      });

    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, selectedTrackId]);

  const config: OperatorPanelConfig = useMemo(() => {
    const apiReady = Boolean(apiSnapshot && !apiError);
    const connectionState = dryRun ? 'dry-run' : apiReady ? (apiSnapshot?.dryRun ? 'dry-run' : 'live') : 'offline';
    return {
      apiBaseUrl: apiBaseUrl || 'local-dry-run-adapter',
      connectionState,
      dryRun,
      liveArmEnabled: liveArmEnabled && !dryRun,
    };
  }, [apiBaseUrl, apiError, apiSnapshot, dryRun, liveArmEnabled]);

  const displayStage = apiSnapshot?.stage ?? stage;
  const displayRound = apiSnapshot?.round ?? round;
  const visibleTracks = apiSnapshot?.tracks.length ? apiSnapshot.tracks : dryRunTracksByStage[displayStage].map((track) => ({ ...track, round: displayRound }));
  const selectedTrack = visibleTracks.find((track) => track.trackId === selectedTrackId) ?? visibleTracks[0];
  const selectedTargetGateOk = targetGateOkForStage(displayStage, selectedTrack);
  const localFrames = useMemo(() => makeLocalSensorFrames(displayStage, displayRound), [displayStage, displayRound]);
  const sensorFrames = apiSnapshot ? (apiSnapshot.sensorFrames ?? []) : localFrames;
  const fusedSensorFrames = sensorFrames.filter((frame) => frame.sensor === 'fusion');
  const interpretedSensorFrames = fusedSensorFrames.length > 0 ? fusedSensorFrames : sensorFrames;
  const sensorHealth: OperatorSensorHealth = apiSnapshot?.sensorHealth ?? { ...localSensorHealth, frameCount: sensorFrames.length, latestFrameAt: sensorFrames[0]?.timestamp ?? localSensorHealth.latestFrameAt };
  const connectedSensorFramesEmpty = Boolean(apiSnapshot && sensorFrames.length === 0);
  const safety = evaluateOperatorSafety({
    estop: operatorStopActive || (apiSnapshot?.safety.estop ?? false),
    motionZoneOk: apiSnapshot?.safety.motionZoneOk ?? true,
    fireZoneOk: apiSnapshot?.safety.fireZoneOk ?? true,
    targetGateOk: selectedTargetGateOk,
    modeOk: !operatorStopActive && (displayStage === 1 ? mode === 'manual' : mode === 'autonomous' || mode === 'engagement'),
    backendConnected: apiSnapshot?.safety.backendConnected ?? config.connectionState !== 'offline',
    perceptionConnected: apiSnapshot?.safety.perceptionConnected ?? config.connectionState === 'live',
    sensorAdapterConnected: apiSnapshot?.safety.sensorAdapterConnected ?? config.connectionState === 'live',
    dryRun: config.dryRun,
    liveArmEnabled: config.liveArmEnabled,
  });
  const sensorSource = sensorSourceLabel(sensorHealth, safety.sensorAdapterConnected);
  const safetyFireReady = canSendFireIntent(safety, selectedTrack?.trackId);
  const operatorFireAllowedByStage = stageExpectedMode(displayStage) === 'manual';
  const fireReady = safetyFireReady && operatorFireAllowedByStage;
  const fireBlockedCopy = operatorFireAllowedByStage
    ? operatorBlockCopy[safety.blockReason]
    : 'Bu aşamada atış otonom mod tarafından yönetilir.';
  const maintenanceReady = !apiBusy && (operatorStopActive || stageExpectedMode(displayStage) === 'manual' || mode === 'maintenance');
  const telemetryMetadata = telemetryExport?.telemetry ?? apiSnapshot?.telemetry;
  const evidenceEntries = telemetryExport?.entries ?? replayBundle?.entries ?? [];
  const replayHardwareCount = replayBundle?.hardwareResults.length ?? 0;
  const replayCommandCount = replayBundle?.commandResults.length ?? 0;
  const replayEventCount = replayBundle?.events.length ?? 0;
  const unsafeReplayEvidence = Boolean(telemetryExport?.unsafeReplayEvidence || replayBundle?.unsafeReplayEvidence);
  const replayEvidenceWarning = telemetryExport?.evidenceWarning || replayBundle?.evidenceWarning;
  const fallbackReadiness: OperatorReadinessReport = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    summary: apiBaseUrl
      ? 'Backend readiness raporu alınamadı; panel temel state üzerinden çalışıyor.'
      : 'Backend API bağlanmadan yalnız operatör UI kabuğu ve yerel dry-run izleri görülebilir.',
    scoreBasis: 'Bu yüzde resmi yarışma uygunluk skoru değildir; repo içi entegrasyon kontrol listesidir.',
    readinessPercent: apiBaseUrl && !apiError ? 28 : 12,
    physicalOutputEnabled: false,
    mode,
    dryRun: config.dryRun,
    items: [
      {
        id: 'operator_panel_ui',
        label: 'Operatör Paneli UI',
        status: 'ready',
        owner: 'Frontend',
        evidence: 'Panel aşama/tur seçimi, radar/LiDAR replay katmanı, sınıf/dost-düşman güveni, FireIntent, Stop, Bakım ve kanıt/replay yüzeylerini gösterir.',
        nextStep: 'Canlı kamera/perception ve saha kiosk düzeni gerçek donanımla ayrıca denenmeli.',
        ktrInterface: 'Kullanıcı Arayüzü, StageRequest, SensorFrame',
      },
      {
        id: 'backend_api',
        label: 'Backend Operatör API',
        status: apiBaseUrl && !apiError ? 'partial' : 'tbd',
        owner: 'Backend',
        evidence: apiBaseUrl ? 'API base URL verilmiş; state/readiness yanıtı temel panelde kullanılabilir.' : 'API base URL yok.',
        nextStep: 'Dry-run API sunucusunu başlat ve operatorApi/VITE_GOKKALKAN_OPERATOR_API_BASE ile bağla.',
        ktrInterface: 'ModeRequest, StageRequest, FireIntent',
      },
      {
        id: 'perception_adapter',
        label: 'Perception Adapter',
        status: 'tbd',
        owner: 'Perception',
        evidence: 'Canlı sınıflandırma akışı bağlanmadı; UI TrackState sözleşmesini bekliyor.',
        nextStep: 'Kamera/model çıktısını TrackState olarak backend/UI akışına bağla.',
        ktrInterface: 'TrackState',
      },
      {
        id: 'radar_lidar_adapter',
        label: 'Radar/LiDAR Adapter',
        status: 'tbd',
        owner: 'Sensör',
        evidence: 'SensorFrame replay fixture panelde görünür; gerçek menzil/açı/kalite akışı henüz bağlı değil.',
        nextStep: 'Seçilen sensörün güç, veri, timestamp ve sağlık mesajı sözleşmesini doldur.',
        ktrInterface: 'SensorFrame',
      },
      {
        id: 'hardware_adapter',
        label: 'Hardware Adapter',
        status: 'partial',
        owner: 'Backend + Elektronik',
        evidence: 'Mock hardware sonucu fiziksel çıkışsız gösterilir; gerçek MCU protokolü seçilmedi.',
        nextStep: 'MCU mesaj çerçevesi ve pan/tilt limitlerini elektronik/mekanik ekiple netleştir.',
        ktrInterface: 'HardwareResult',
      },
      {
        id: 'live_arming',
        label: 'Canlı Arming / Fiziksel Çıkış',
        status: 'blocked',
        owner: 'Safety + Elektronik',
        evidence: 'Geliştirme paneli fiziksel çıkış üretmez.',
        nextStep: 'İki aşamalı arming ve fiziksel interlock doğrulaması tamamlanmadan canlı çıkış açma.',
        ktrInterface: 'ArmingState, InterlockState',
      },
    ],
    nextCriticalActions: [
      'Dry-run backend API ile readiness raporunu canlı doğrula.',
      'Radar/LiDAR ve perception adapter sözleşmelerini gerçek donanıma bağla.',
      'MCU haberleşme protokolü ve imha hattı interlock mesajlarını netleştir.',
    ],
  };
  const displayReadiness = readinessReport ?? fallbackReadiness;
  const readinessById = Object.fromEntries(displayReadiness.items.map((item) => [item.id, item])) as Record<string, OperatorReadinessItem | undefined>;

  const pushResult = (result: CommandResult) => {
    setCommandResults((previous) => [result, ...previous].slice(0, 8));
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

  const recordMode = (nextMode: Mode) => {
    setMode(nextMode);
    if (apiBaseUrl) {
      setApiBusy(true);
      void sendOperatorModeRequest(apiBaseUrl, {
        kind: 'ModeRequest',
        requestedMode: nextMode,
        operatorId: 'OP-UI-1',
        timestamp: new Date().toISOString(),
        reason: 'operator-panel',
        dryRun: config.dryRun,
      })
        .then((response) => {
          pushResult(response.result);
          setApiSnapshot(response.state);
          setLastHardwareResult(response.hardwareResult ?? undefined);
          setApiError('');
        })
        .catch((error: unknown) => {
          pushResult(makeCommandResult({
            commandId: `MODE-BLOCK-${Date.now()}`,
            kind: 'ModeRequest',
            accepted: false,
            dryRun: config.dryRun,
            safetyBlockReason: 'BLOCKED_BACKEND',
          }));
          setApiError(error instanceof Error ? error.message : 'Backend API mode komutunu kabul etmedi.');
        })
        .finally(() => setApiBusy(false));
      return;
    }

    const accepted = config.connectionState !== 'offline';
    pushResult(makeCommandResult({
      commandId: `MODE-${nextMode}-${Date.now()}`,
      kind: 'ModeRequest',
      accepted,
      dryRun: config.dryRun,
      safetyBlockReason: accepted ? 'ALLOWED' : 'BLOCKED_BACKEND',
    }));
  };

  const recordStage = (nextStage: Stage, nextRound = 1) => {
    const boundedRound = Math.max(1, Math.min(stageRoundLimit(nextStage), nextRound));
    const expectedMode = stageExpectedMode(nextStage);
    setStage(nextStage);
    setRound(boundedRound);
    setMode(expectedMode);
    const fallbackTrack = dryRunTracksByStage[nextStage][0];
    if (fallbackTrack) setSelectedTrackId(fallbackTrack.trackId);

    const request = makeStageRequest({
      stage: nextStage,
      round: boundedRound,
      dryRun: config.dryRun,
      reason: 'operator-stage-control',
    });

    if (apiBaseUrl) {
      setApiBusy(true);
      void sendOperatorStageRequest(apiBaseUrl, request)
        .then((response) => {
          pushResult(response.result);
          setApiSnapshot(response.state);
          setStage(response.state.stage);
          setRound(response.state.round);
          setMode(response.state.mode);
          if (response.state.tracks[0]) setSelectedTrackId(response.state.tracks[0].trackId);
          setLastHardwareResult(undefined);
          setApiError('');
        })
        .catch((error: unknown) => {
          pushResult(makeCommandResult({
            commandId: `STAGE-BLOCK-${Date.now()}`,
            kind: 'StageRequest',
            accepted: false,
            dryRun: config.dryRun,
            safetyBlockReason: 'BLOCKED_BACKEND',
          }));
          setApiError(error instanceof Error ? error.message : 'Backend API aşama komutunu kabul etmedi.');
        })
        .finally(() => setApiBusy(false));
      return;
    }

    pushResult(makeCommandResult({
      commandId: `STAGE-${nextStage}-${boundedRound}-${Date.now()}`,
      kind: 'StageRequest',
      accepted: true,
      dryRun: config.dryRun,
      safetyBlockReason: 'ALLOWED',
    }));
  };

  const sendFireIntent = () => {
    if (!selectedTrack || !fireReady) {
      pushResult(makeCommandResult({
        commandId: `BLOCK-${Date.now()}`,
        kind: 'FireIntent',
        accepted: false,
        dryRun: config.dryRun,
        safetyBlockReason: operatorFireAllowedByStage ? safety.blockReason : 'BLOCKED_MODE',
      }));
      return;
    }

    const intent = makeFireIntent({ targetId: selectedTrack.trackId, stage: displayStage, round: displayRound, dryRun: config.dryRun });
    setLastIntent(intent);
    if (apiBaseUrl) {
      setApiBusy(true);
      void sendOperatorFireIntent(apiBaseUrl, intent)
        .then((response) => {
          pushResult(response.result);
          setApiSnapshot(response.state);
          setLastHardwareResult(response.hardwareResult ?? undefined);
          setApiError('');
        })
        .catch((error: unknown) => {
          pushResult(makeCommandResult({
            commandId: `FIRE-BLOCK-${Date.now()}`,
            kind: 'FireIntent',
            accepted: false,
            dryRun: config.dryRun,
            safetyBlockReason: 'BLOCKED_BACKEND',
          }));
          setLastHardwareResult(undefined);
          setApiError(error instanceof Error ? error.message : 'Backend API fire intent komutunu kabul etmedi.');
        })
        .finally(() => setApiBusy(false));
      return;
    }

    const result = makeCommandResult({
      commandId: intent.requestedAt,
      kind: intent.kind,
      accepted: true,
      dryRun: intent.dryRun,
      safetyBlockReason: 'ALLOWED',
    });
    pushResult(result);
    setLastHardwareResult({
      adapter: 'local-ui.dry-run',
      commandId: result.commandId,
      kind: intent.kind,
      accepted: true,
      completed: true,
      physicalOutput: false,
      message: 'Yerel dry-run panel komutu kaydetti; fiziksel çıkış üretilmedi.',
      createdAt: result.createdAt,
    });
  };

  const triggerOperatorStop = () => {
    setOperatorStopActive(true);
    setMode('blocked');
    const result = makeCommandResult({
      commandId: `STOP-${Date.now()}`,
      kind: 'ModeRequest',
      accepted: true,
      dryRun: config.dryRun,
      safetyBlockReason: 'ALLOWED',
    });
    pushResult(result);
    setLastHardwareResult({
      adapter: 'local-ui.safety-gate',
      commandId: result.commandId,
      kind: 'ModeRequest',
      accepted: true,
      completed: true,
      physicalOutput: false,
      message: 'Operatör stop komutu yerel Safety Gate üzerinde kilidi aktif etti; fiziksel çıkış üretilmedi.',
      createdAt: result.createdAt,
    });
  };

  const openMaintenance = () => {
    if (!maintenanceReady) {
      pushResult(makeCommandResult({
        commandId: `MAINTENANCE-BLOCK-${Date.now()}`,
        kind: 'ModeRequest',
        accepted: false,
        dryRun: config.dryRun,
        safetyBlockReason: 'BLOCKED_MODE',
      }));
      return;
    }
    setMaintenanceOpen((value) => !value);
    recordMode('maintenance');
  };

  return (
    <main className="operator-shell min-h-screen bg-[#05070a] p-3 text-[#ecf7ff]" data-testid="operator-panel" data-desktop-shell={isDesktopShell ? 'true' : 'false'}>
      <header className="operator-header mb-3 grid gap-3 rounded-xl border border-[#25d8ff]/18 bg-[rgba(7,10,14,.94)] p-3 shadow-[0_18px_50px_rgba(0,0,0,.28)]">
        <div className="min-w-0">
          <p className="m-0 text-xs font-black uppercase tracking-[.18em] text-[#ffbb42]">Operasyon</p>
          <h1 className="m-0 mt-1 text-3xl font-black tracking-[.04em] text-white min-[760px]:text-4xl">GÖKKALKAN OPERATÖR PANELİ</h1>
        </div>
      </header>

      <section className="operator-primary-grid">
        <section className="operator-3d-panel rounded-xl border border-[#48a8ff]/18 bg-[rgba(7,10,14,.94)] p-0" data-testid="operator-sensor-fusion-panel" aria-label="Radar LiDAR ve yazılım füzyon katmanı">
          <SensorFusion3DView
            frames={interpretedSensorFrames}
            selectedTrackId={selectedTrackId}
            onSelect={setSelectedTrackId}
            sensorHealth={sensorHealth}
            sensorSource={sensorSource}
            connectedSensorFramesEmpty={connectedSensorFramesEmpty}
          />
        </section>

        <aside className="operator-side-rail">
          <section className="rounded-xl border border-[#25d8ff]/18 bg-[rgba(7,10,14,.94)] p-4" data-testid="operator-stage-control" aria-label="Aşama ve tur kontrolü">
            <p className="m-0 text-xs font-black uppercase tracking-[.16em] text-[#25d8ff]">Görev</p>
            <h2 className="m-0 mt-1 text-2xl font-black">Aşama / Tur</h2>
            <div className="mt-4 grid grid-cols-3 gap-2">
              {([1, 2, 3] as const).map((item) => (
                <button
                  key={item}
                  className={`rounded-lg border px-3 py-2 text-sm font-black ${displayStage === item ? 'border-[#33e68c]/40 bg-[#33e68c]/14 text-[#ccffe2]' : 'border-white/10 bg-white/[.06] text-[#c8d8e2]'}`}
                  disabled={apiBusy}
                  onClick={() => recordStage(item, 1)}
                >
                  Aşama {item}
                </button>
              ))}
            </div>
            <div
              className="operator-round-grid mt-3"
              style={{ '--round-count': stageRoundLimit(displayStage) } as CSSProperties}
            >
              {Array.from({ length: stageRoundLimit(displayStage) }, (_, index) => index + 1).map((item) => (
                <button
                  key={item}
                  className={`rounded-full border px-1.5 py-1 text-[11px] font-black ${displayRound === item ? 'border-[#ffbb42]/40 bg-[#ffbb42]/14 text-[#ffe4ad]' : 'border-white/10 bg-white/[.06] text-[#c8d8e2]'}`}
                  disabled={apiBusy}
                  onClick={() => recordStage(displayStage, item)}
                >
                  Tur {item}
                </button>
              ))}
            </div>
          </section>

          <OperatorTrackScene
            compact
            stage={displayStage}
            tracks={visibleTracks}
            selectedTrackId={selectedTrackId}
            lastIntent={lastIntent}
            onSelect={setSelectedTrackId}
          />

          <section className="operator-action-strip rounded-xl border border-[#25d8ff]/18 bg-[rgba(7,10,14,.94)] p-3" data-testid="operator-action-strip" aria-label="Operatör komutları">
            <div className="operator-action-buttons">
              <div className="rounded-xl border border-white/[.08] bg-black/20 p-2.5" data-testid="fire-cluster">
                <button
                  className={`min-h-16 w-full rounded-xl px-3 text-base font-black ${fireReady ? 'bg-[#ff3146] text-white shadow-[0_18px_42px_rgba(255,71,87,.28)] fire-ready-pulse' : 'bg-white/[.08] text-[#91a6b7]'}`}
                  disabled={!fireReady || apiBusy}
                  data-testid="operator-fire-button"
                  onClick={sendFireIntent}
                >
                  ATEŞ
                </button>
                <p className="m-0 mt-1 truncate text-center text-[11px] font-bold text-[#ffe4ad]">{fireReady ? selectedTrack?.trackId ?? 'Hedef' : fireBlockedCopy}</p>
              </div>

              <div className="rounded-xl border border-white/[.08] bg-black/20 p-2.5">
                <button
                  className="min-h-16 w-full rounded-xl border border-[#ff4757]/35 bg-[#ff4757]/14 px-3 text-base font-black text-[#ffd3d7]"
                  data-testid="operator-stop-button"
                  disabled={operatorStopActive}
                  onClick={triggerOperatorStop}
                >
                  STOP
                </button>
                <p className="m-0 mt-1 text-center text-[11px] font-bold text-[#ffbdc4]">{operatorStopActive ? 'AKTİF' : 'Hazır'}</p>
              </div>

              <div className="rounded-xl border border-white/[.08] bg-black/20 p-2.5">
                <button
                  className="min-h-16 w-full rounded-xl border border-[#48a8ff]/30 bg-[#48a8ff]/10 px-3 text-base font-black text-[#d7efff]"
                  data-testid="operator-maintenance-button"
                  disabled={!maintenanceReady}
                  onClick={openMaintenance}
                >
                  BAKIM
                </button>
                <p className="m-0 mt-1 text-center text-[11px] font-bold text-[#91cfff]">{maintenanceOpen ? 'Açık' : maintenanceReady ? 'Hazır' : 'STOP sonrası'}</p>
              </div>
            </div>
          </section>
        </aside>
      </section>

      <ConfidencePanel frames={interpretedSensorFrames} selectedTrackId={selectedTrackId} />

      <section className="operator-utility-grid mt-3 grid gap-3 min-[1100px]:grid-cols-[minmax(0,.75fr)_minmax(0,.75fr)_minmax(0,1fr)]">
        <section className="rounded-xl border border-[#ffbb42]/18 bg-[rgba(10,8,4,.88)] p-4" aria-label="Emniyet kilitleri">
          <h2 className="m-0 text-xl font-black text-[#ffe4ad]">Emniyet</h2>
          <div className="mt-3 grid gap-2 text-sm" data-testid="operator-safety-state">
            <EvidenceRow label="Acil Durdur" value={safety.estop ? 'AKTİF' : 'Pasif'} />
            <EvidenceRow label="Atış alanı" value={safety.fireZoneOk ? 'Uygun' : 'Kilitli'} />
            <EvidenceRow label="Hedef kapısı" value={safety.targetGateOk ? 'Uygun' : 'Dost/bilinmeyen/menzil dışı'} />
          </div>
        </section>

        <details className="rounded-xl border border-[#ffbb42]/18 bg-[rgba(10,8,4,.88)] p-4" data-testid="operator-maintenance-drawer" open={maintenanceOpen} onToggle={(event) => setMaintenanceOpen(event.currentTarget.open)}>
          <summary className="cursor-pointer list-none text-xl font-black text-[#ffe4ad]">Bakım / Diagnostik</summary>
          <div className="mt-3 grid gap-2">
            <AdapterRow
              label="Perception Adapter"
              item={readinessById.perception_adapter}
              fallback="Kamera/model çıktısı TrackState sözleşmesine bağlanacak; canlı sınıflandırma adapterı TBD."
            />
            <AdapterRow
              label="Radar/LiDAR Adapter"
              item={readinessById.radar_lidar_adapter}
              fallback="Menzil/açı/kalite protokolü seçilen sensöre göre TBD."
            />
            <AdapterRow
              label="MCU / Hardware Protocol"
              item={readinessById.hardware_adapter}
              fallback="UART/RS422/CAN/Ethernet ve mesaj çerçevesi elektronik ekibiyle netleşecek."
            />
            <AdapterRow
              label="Canlı Arming / Interlock"
              item={readinessById.live_arming}
              fallback="İki aşamalı arming, hakem/operatör kilidi ve fiziksel interlock tamamlanmadan kapalı."
            />
          </div>
          <div className="mt-3 grid gap-2 text-sm">
            <EvidenceRow label="API base" value={config.apiBaseUrl} />
            <EvidenceRow label="Komut endpointleri" value="POST /stage · POST /mode · POST /fire-intent" />
            <EvidenceRow label="Kanıt endpointleri" value="GET /sensor-frames · GET /readiness · GET /telemetry/export · GET /replay" />
          </div>
          <div className="mt-3 grid gap-2 text-sm" data-testid="operator-lidar-diagnostics">
            <EvidenceRow label="LiDAR viewer" value="Dış diagnostic / görev UI değil" />
            <EvidenceRow label="RPLIDAR / Livox" value="Kalibrasyon · firmware · ham point cloud" />
            <EvidenceRow label="Operasyon verisi" value="SDK/driver → SensorFrame → Backend" />
          </div>
        </details>

        <section className="rounded-xl border border-white/[.08] bg-[rgba(7,10,14,.94)] p-4" aria-label="Olay akışı">
          <h2 className="m-0 text-xl font-black">Olay akışı</h2>
          <div className="mt-3 grid max-h-80 gap-2 overflow-auto pr-1">
            {commandResults.length === 0 && <p className="m-0 rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-sm text-[#91a6b7]">Henüz komut sonucu yok.</p>}
            {commandResults.map((result) => (
              <article key={result.commandId} className="rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-sm">
                <b className={result.accepted ? 'text-[#bfffe0]' : 'text-[#ffbdc4]'}>{commandLabel(result)} · {result.accepted ? 'Kabul' : 'Blok'}</b>
                <p className="m-0 mt-1 text-[#c8d8e2]">{result.message}</p>
                <small className="mt-1 block text-[#91a6b7]">{result.createdAt}</small>
              </article>
            ))}
          </div>
        </section>
      </section>

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

function AdapterRow({ label, item }: { label: string; item: OperatorReadinessItem | undefined; fallback: string }) {
  const status = item?.status ?? 'tbd';
  return (
    <article className="rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <b className="text-white">{label}</b>
        <span className={`rounded-full border px-2 py-1 text-[11px] font-black uppercase tracking-[.08em] ${readinessTone(status)}`}>
          {readinessCopy[status]}
        </span>
      </div>
    </article>
  );
}
