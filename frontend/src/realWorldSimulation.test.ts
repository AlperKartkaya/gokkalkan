import { describe, expect, it } from 'vitest';
import { generateRealWorldTelemetry, generateRealWorldTracks, generateSensorFusionFrame } from './realWorldSimulation';

describe('real-world competition simulation feed', () => {
  it('creates stationary Aşama 1 targets in the expected competition order', () => {
    const tracks = generateRealWorldTracks(1, 0);
    expect(tracks.map((track) => track.type)).toEqual(['Balistik Füze', 'Helikopter', 'F16', 'Mini/Micro İHA']);
    expect(tracks.map((track) => track.range)).toEqual([5, 10, 15, 15]);
  });

  it('moves Aşama 2 targets across the three canonical poligon routes', () => {
    const start = generateRealWorldTracks(2, 0);
    const later = generateRealWorldTracks(2, 10);

    expect(start.map((track) => track.lane)).toEqual([1, 2, 3]);
    expect(later.map((track) => track.lane)).toEqual([1, 2, 3]);

    start.forEach((track, index) => {
      expect(later[index].x).not.toBeCloseTo(track.x, 1);
      expect(later[index].range).not.toBeCloseTo(track.range, 1);
      expect(later[index].x).toBeGreaterThanOrEqual(6);
      expect(later[index].x).toBeLessThanOrEqual(92);
      expect(later[index].direction).toContain('Poligon giriş→çıkış');
    });
  });

  it('only marks an Aşama 3 enemy when its geometry-derived range is in the fire gate', () => {
    let validCandidateCount = 0;
    [0, 5, 10, 15, 20].forEach((elapsed) => {
      const tracks = generateRealWorldTracks(3, elapsed);
      const candidates = tracks.filter((track) => track.candidate);
      expect(candidates.length).toBeLessThanOrEqual(1);
      candidates.forEach((candidate) => {
        expect(candidate.friendFoe).toBe('Düşman');
        expect(candidate.rangeGate).toBe('Uygun');
        validCandidateCount += 1;
      });
      expect(tracks.filter((track) => track.friendFoe === 'Dost').every((track) => !track.candidate)).toBe(true);
    });
    expect(validCandidateCount).toBeGreaterThan(0);
  });

  it('reports camera, LiDAR mock, radar mock, and fusion channels', () => {
    const tracks = generateRealWorldTracks(2, 7);
    const frame = generateSensorFusionFrame(2, 7, tracks);

    expect(frame.cameraDetections).toHaveLength(3);
    expect(frame.lidarReturns).toHaveLength(3);
    expect(frame.radarReturns).toHaveLength(3);
    expect(frame.fusedTargetId).toBeTruthy();
    expect(frame.assumptionNotice).toContain('PLG26-A-001-002-00-R1');
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
