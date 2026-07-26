import {
  dataset_id,
  geometry_scope,
  range_bands,
  raster_derivation,
  routes,
  source,
  status,
} from '../../config/course/plg26_a_001_002_r1.json';

export interface CoursePoint {
  x: number;
  y: number;
}

interface CoursePathPoint extends CoursePoint {
  sM: number;
  courseXM: number;
  courseYM: number;
}

export interface CourseLane {
  lane: 1 | 2 | 3;
  routeId: string;
  label: string;
  lengthM: number;
  points: CoursePathPoint[];
}

export interface RangeMarker {
  range: 5 | 10 | 15;
  x: number;
  y: number;
}

interface RawWaypoint {
  x_m: number;
  y_m: number;
  s_m: number;
}

interface RawRoute {
  id: string;
  route_number: number;
  label: string;
  derived_summary: { poligon_path_length_m: number };
  poligon_waypoints: RawWaypoint[];
}

interface RawCourseDataset {
  dataset_id: string;
  status: string;
  source: { path: string; sha256: string; revision: number };
  geometry_scope: {
    active_prediction_region: string;
    outside_return_included: boolean;
    poligon_bounds_course_m: {
      west_x: number;
      east_x: number;
      south_y: number;
      north_y: number;
    };
  };
  raster_derivation: {
    system_reference: { course_x_m: number; course_y_m: number };
  };
  range_bands: Array<{ label_m: number; x_mm: number }>;
  routes: RawRoute[];
}

const dataset = {
  dataset_id,
  status,
  source,
  geometry_scope,
  raster_derivation,
  range_bands,
  routes,
} as unknown as RawCourseDataset;
if (
  dataset.dataset_id !== 'PLG26-A-001-002-00-R1'
  || dataset.status !== 'CANONICAL_POLIGON_INTERIOR_GEOMETRY'
  || dataset.geometry_scope.active_prediction_region !== 'POLIGON_INTERIOR_ONLY'
  || dataset.geometry_scope.outside_return_included
) {
  throw new Error('Kanonik poligon geometrisi doğrulanamadı; parkur görünümü fail-closed durduruldu.');
}
const bounds = dataset.geometry_scope.poligon_bounds_course_m;
const DISPLAY = { left: 8, right: 82, top: 10, bottom: 90 } as const;

function toDisplay(point: { x_m: number; y_m: number }): CoursePoint {
  return {
    x: DISPLAY.left + ((point.x_m - bounds.west_x) / (bounds.east_x - bounds.west_x)) * (DISPLAY.right - DISPLAY.left),
    y: DISPLAY.bottom - ((point.y_m - bounds.south_y) / (bounds.north_y - bounds.south_y)) * (DISPLAY.bottom - DISPLAY.top),
  };
}

export function toDisplayCourseMeters(point: { x: number; y: number }): CoursePoint {
  return toDisplay({ x_m: point.x, y_m: point.y });
}

export function toCourseMeters(point: CoursePoint): { xM: number; yM: number } {
  return {
    xM: bounds.west_x + ((point.x - DISPLAY.left) / (DISPLAY.right - DISPLAY.left)) * (bounds.east_x - bounds.west_x),
    yM: bounds.south_y + ((DISPLAY.bottom - point.y) / (DISPLAY.bottom - DISPLAY.top)) * (bounds.north_y - bounds.south_y),
  };
}

function routeNumber(value: number): 1 | 2 | 3 {
  if (value === 1 || value === 2 || value === 3) return value;
  throw new Error(`Desteklenmeyen poligon rota numarası: ${value}`);
}

const lanes: CourseLane[] = dataset.routes.map((route) => ({
  lane: routeNumber(route.route_number),
  routeId: route.id,
  label: route.label,
  lengthM: route.derived_summary.poligon_path_length_m,
  points: route.poligon_waypoints.map((point) => ({
    ...toDisplay(point),
    sM: point.s_m,
    courseXM: point.x_m,
    courseYM: point.y_m,
  })),
}));

const systemReference = dataset.raster_derivation.system_reference;
const systemPosition = toDisplay({
  x_m: systemReference.course_x_m,
  y_m: systemReference.course_y_m,
});

const rangeMarkers: RangeMarker[] = dataset.range_bands.map((band) => {
  if (band.label_m !== 5 && band.label_m !== 10 && band.label_m !== 15) {
    throw new Error(`Desteklenmeyen menzil işareti: ${band.label_m}`);
  }
  return {
    range: band.label_m,
    ...toDisplay({ x_m: band.x_mm / 1000, y_m: bounds.north_y }),
  };
});

export const COMPETITION_COURSE = {
  datasetId: dataset.dataset_id,
  sourceRevision: dataset.source.revision,
  sourceSha256: dataset.source.sha256,
  source: {
    stage1: 'docs/sartname_v1_3.txt:475-480,578-585',
    movingCourse: `${dataset.source.path}; config/course/plg26_a_001_002_r1.json`,
    targetVisuals: 'docs/sartname_v1_3.txt:396-399; docs/sartname_v1_3.pdf:§6.2-6.3',
  },
  assumptionNotice:
    'PLG26-A-001-002-00-R1 ölçekli çiziminden türetilen yalnız poligon içi eğriler kullanılır; poligon dışı dönüşte rota tahmini kapalıdır. Sistem yaw referansı raster izidir ve yazılı ölçü toleransı iddiası taşımaz.',
  geometryScope: dataset.geometry_scope.active_prediction_region,
  outsideReturnIncluded: dataset.geometry_scope.outside_return_included,
  systemPosition,
  aPoint: lanes[0].points[0],
  bPoint: lanes[0].points[lanes[0].points.length - 1],
  rangeMarkers,
  lanes,
} as const;

export function laneFor(lane: 1 | 2 | 3): CourseLane {
  return COMPETITION_COURSE.lanes.find((item) => item.lane === lane) ?? COMPETITION_COURSE.lanes[0];
}

export function displayXForRangeBand(range: number): number {
  const marker = COMPETITION_COURSE.rangeMarkers.find((item) => item.range === range);
  if (marker) return marker.x;
  const scale = (DISPLAY.right - DISPLAY.left) / (bounds.east_x - bounds.west_x);
  return COMPETITION_COURSE.systemPosition.x - range * scale;
}

export function pointAtProgress(lane: 1 | 2 | 3, progress: number): CoursePoint {
  const route = laneFor(lane);
  const boundedS = Math.min(1, Math.max(0, progress)) * route.lengthM;
  const path = route.points;

  for (let index = 0; index < path.length - 1; index += 1) {
    const from = path[index];
    const to = path[index + 1];
    if (boundedS <= to.sM) {
      const span = to.sM - from.sM;
      const ratio = span === 0 ? 0 : (boundedS - from.sM) / span;
      return {
        x: from.x + (to.x - from.x) * ratio,
        y: from.y + (to.y - from.y) * ratio,
      };
    }
  }

  return path[path.length - 1];
}

export function courseRangeFromPoint(point: CoursePoint): number {
  const course = toCourseMeters(point);
  return Math.hypot(
    systemReference.course_x_m - course.xM,
    systemReference.course_y_m - course.yM,
  );
}

export function bearingFromSystem(point: CoursePoint): number {
  const course = toCourseMeters(point);
  const baseX = systemReference.course_x_m - course.xM;
  const baseY = systemReference.course_y_m - course.yM;
  return Number(((Math.atan2(baseY, baseX) * 180) / Math.PI).toFixed(1));
}
