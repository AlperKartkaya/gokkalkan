export interface CoursePoint {
  x: number;
  y: number;
}

export interface CourseLane {
  lane: 1 | 2 | 3;
  label: string;
  points: CoursePoint[];
}

export interface RangeMarker {
  range: 5 | 10 | 15;
  x: number;
  y: number;
}

export const COMPETITION_COURSE = {
  source: {
    stage1: 'docs/sartname_v5.txt:494-498',
    movingCourse: 'docs/sartname_v5.txt:529-538,543-545,567-568',
    targetVisuals: 'docs/sartname_v5.txt:573-580',
  },
  assumptionNotice:
    'Şartname A/B noktası, üç kol ve 5/10/15 m işaretlerini verir; kesin koordinat/radar-LiDAR modeli vermediği için bu görünüm Şekil 4/5 üzerinden normalize edilmiş eğitim parkurudur.',
  systemPosition: { x: 82, y: 62 } satisfies CoursePoint,
  aPoint: { x: 8, y: 17 } satisfies CoursePoint,
  bPoint: { x: 80, y: 17 } satisfies CoursePoint,
  rangeMarkers: [
    { range: 15, x: 14, y: 20 },
    { range: 10, x: 47, y: 20 },
    { range: 5, x: 73, y: 20 },
  ] satisfies RangeMarker[],
  lanes: [
    {
      lane: 1,
      label: 'Kol 1',
      points: [
        { x: 8, y: 31 },
        { x: 19, y: 30 },
        { x: 31, y: 37 },
        { x: 46, y: 42 },
        { x: 61, y: 37 },
        { x: 72, y: 42 },
        { x: 78, y: 31 },
        { x: 78, y: 18 },
      ],
    },
    {
      lane: 2,
      label: 'Kol 2',
      points: [
        { x: 8, y: 55 },
        { x: 23, y: 50 },
        { x: 38, y: 56 },
        { x: 53, y: 52 },
        { x: 68, y: 56 },
        { x: 77, y: 53 },
        { x: 79, y: 61 },
      ],
    },
    {
      lane: 3,
      label: 'Kol 3',
      points: [
        { x: 8, y: 78 },
        { x: 19, y: 76 },
        { x: 31, y: 68 },
        { x: 46, y: 70 },
        { x: 60, y: 74 },
        { x: 72, y: 68 },
        { x: 78, y: 77 },
        { x: 78, y: 90 },
      ],
    },
  ] satisfies CourseLane[],
} as const;

export function laneFor(lane: 1 | 2 | 3): CourseLane {
  return COMPETITION_COURSE.lanes.find((item) => item.lane === lane) ?? COMPETITION_COURSE.lanes[0];
}

function distance(a: CoursePoint, b: CoursePoint): number {
  return Math.hypot(b.x - a.x, b.y - a.y);
}

export function pointAtProgress(lane: 1 | 2 | 3, progress: number): CoursePoint {
  const path = laneFor(lane).points;
  const boundedProgress = Math.min(1, Math.max(0, progress));
  const segmentLengths = path.slice(1).map((point, index) => distance(path[index], point));
  const total = segmentLengths.reduce((sum, item) => sum + item, 0);
  let remaining = boundedProgress * total;

  for (let index = 0; index < segmentLengths.length; index += 1) {
    const length = segmentLengths[index];
    if (remaining <= length || index === segmentLengths.length - 1) {
      const from = path[index];
      const to = path[index + 1];
      const ratio = length === 0 ? 0 : remaining / length;
      return {
        x: from.x + (to.x - from.x) * ratio,
        y: from.y + (to.y - from.y) * ratio,
      };
    }
    remaining -= length;
  }

  return path[path.length - 1];
}

export function courseRangeFromPoint(point: CoursePoint): number {
  const distanceToSystem = distance(point, COMPETITION_COURSE.systemPosition);
  return Math.min(18.5, Math.max(2.5, 2.4 + distanceToSystem * 0.19));
}

export function bearingFromSystem(point: CoursePoint): number {
  const dx = point.x - COMPETITION_COURSE.systemPosition.x;
  const dy = COMPETITION_COURSE.systemPosition.y - point.y;
  return Number(((Math.atan2(dx, dy) * 180) / Math.PI).toFixed(1));
}
