import { describe, expect, it } from 'vitest';
import {
  COMPETITION_COURSE,
  bearingFromSystem,
  courseRangeFromPoint,
  laneFor,
  pointAtProgress,
} from './competitionCourse';

describe('canonical competition course geometry', () => {
  it('loads all poligon-only curve waypoints from the pinned drawing dataset', () => {
    expect(COMPETITION_COURSE.datasetId).toBe('PLG26-A-001-002-00-R1');
    expect(COMPETITION_COURSE.geometryScope).toBe('POLIGON_INTERIOR_ONLY');
    expect(COMPETITION_COURSE.outsideReturnIncluded).toBe(false);
    expect(COMPETITION_COURSE.lanes.map((route) => route.points.length)).toEqual([60, 72, 70]);
    expect(COMPETITION_COURSE.lanes.map((route) => route.lengthM)).toEqual([16.3831, 22.885, 15.9319]);
  });

  it('interpolates by canonical curve arc length rather than a straight chord', () => {
    const route = laneFor(2);
    const midpoint = pointAtProgress(2, 0.5);
    const start = pointAtProgress(2, 0);
    const end = pointAtProgress(2, 1);

    expect(route.lengthM).toBe(22.885);
    expect(midpoint).not.toEqual({
      x: (start.x + end.x) / 2,
      y: (start.y + end.y) / 2,
    });
  });

  it('preserves the east U-turn before each poligon exit', () => {
    COMPETITION_COURSE.lanes.forEach((route) => {
      expect(route.points.some((point, index) => index > 0 && point.x < route.points[index - 1].x)).toBe(true);
    });
  });

  it('derives exact nominal range and base bearing from course coordinates', () => {
    const entry = pointAtProgress(1, 0);

    expect(courseRangeFromPoint(entry)).toBeCloseTo(16.0099, 3);
    expect(bearingFromSystem(entry)).toBeCloseTo(-9.413, 1);
  });
});
