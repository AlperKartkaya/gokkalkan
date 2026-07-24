import { describe, expect, it } from 'vitest';
import { generateRealWorldTelemetry, generateRealWorldTracks, generateSensorFusionFrame } from './realWorldSimulation';

describe('real-world competition simulation feed', () => {
  it('creates stationary Aşama 1 targets in the expected competition order', () => {
    const tracks = generateRealWorldTracks(1, 0);
    expect(tracks.map((track) => track.type)).toEqual(['Balistik Füze', 'Helikopter', 'F16', 'Mini/Micro İHA']);
    expect(tracks.map((track) => track.range)).toEqual([5, 10, 15, 15]);
  });

  it('moves Aşama 2 targets across the three A→B parkur lanes', () => {
    const start = generateRealWorldTracks(2, 0);
    const later = generateRealWorldTracks(2, 10);

    expect(start.map((track) => track.lane)).toEqual([1, 2, 3]);
    expect(later.map((track) => track.lane)).toEqual([1, 2, 3]);

    start.forEach((track, index) => {
      expect(later[index].x).not.toBeCloseTo(track.x, 1);
      expect(later[index].range).not.toBeCloseTo(track.range, 1);
      expect(later[index].x).toBeGreaterThanOrEqual(6);
      expect(later[index].x).toBeLessThanOrEqual(92);
      expect(later[index].direction).toContain('A→B');
    });
  });

  it('keeps exactly one Aşama 3 enemy candidate in a valid fire gate while friends stay locked', () => {
    [0, 10, 20].forEach((elapsed) => {
      const tracks = generateRealWorldTracks(3, elapsed);
      const candidates = tracks.filter((track) => track.candidate);
      expect(candidates).toHaveLength(1);
      expect(candidates[0].friendFoe).toBe('Düşman');
      expect(candidates[0].rangeGate).toBe('Uygun');
      expect(tracks.filter((track) => track.friendFoe === 'Dost').every((track) => !track.candidate)).toBe(true);
    });
  });

  it('reports camera, LiDAR mock, radar mock, and fusion channels', () => {
    const tracks = generateRealWorldTracks(2, 7);
    const frame = generateSensorFusionFrame(2, 7, tracks);

    expect(frame.cameraDetections).toHaveLength(3);
    expect(frame.lidarReturns).toHaveLength(3);
    expect(frame.radarReturns).toHaveLength(3);
    expect(frame.fusedTargetId).toBeTruthy();
    expect(frame.assumptionNotice).toContain('kesin koordinat');
    expect(frame.sourceLineRefs.join(' ')).toContain('docs/sartname_v1_3.txt');
  });

  it('reports camera and mechanics telemetry shaped like a live field feed', () => {
    const telemetry = generateRealWorldTelemetry(2, 12.5, true, 3);
    expect(telemetry.source).toBe('real_camera_sim');
    expect(telemetry.frameId).toBeGreaterThan(0);
    expect(telemetry.fps).toBeGreaterThan(20);
    expect(telemetry.latencyMs).toBeGreaterThanOrEqual(0);
    expect(telemetry.batteryV).toBeGreaterThan(12);
    expect(telemetry.lidarReturns).toBe(3);
    expect(telemetry.radarTracks).toBe(3);
  });
});
