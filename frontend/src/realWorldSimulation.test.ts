import { describe, expect, it } from 'vitest';
import { generateRealWorldTelemetry, generateRealWorldTracks } from './realWorldSimulation';

describe('real-world competition simulation feed', () => {
  it('creates stationary Aşama 1 targets in the expected competition order', () => {
    const tracks = generateRealWorldTracks(1, 0);
    expect(tracks.map((track) => track.type)).toEqual(['Balistik Füze', 'Helikopter', 'F16', 'Mini/Micro İHA']);
    expect(tracks.map((track) => track.range)).toEqual([5, 10, 15, 15]);
  });

  it('keeps exactly one Aşama 3 enemy candidate in a valid fire gate', () => {
    const tracks = generateRealWorldTracks(3, 0);
    const candidates = tracks.filter((track) => track.candidate);
    expect(candidates).toHaveLength(1);
    expect(candidates[0].friendFoe).toBe('Düşman');
    expect(candidates[0].rangeGate).toBe('Uygun');
  });

  it('reports camera and mechanics telemetry shaped like a live field feed', () => {
    const telemetry = generateRealWorldTelemetry(2, 12.5, true);
    expect(telemetry.source).toBe('real_camera_sim');
    expect(telemetry.frameId).toBeGreaterThan(0);
    expect(telemetry.fps).toBeGreaterThan(20);
    expect(telemetry.latencyMs).toBeGreaterThanOrEqual(0);
    expect(telemetry.batteryV).toBeGreaterThan(12);
  });
});
