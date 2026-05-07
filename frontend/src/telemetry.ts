import type { EventType, Mode, Stage, TelemetryEvent } from './types';

export function makeEvent(
  id: number,
  stage: Stage,
  mode: Mode,
  type: EventType,
  decision: string,
  reason: string,
): TelemetryEvent {
  return {
    id,
    timestamp: new Date().toLocaleTimeString('tr-TR', { hour12: false }),
    stage,
    mode,
    type,
    decision,
    reason,
  };
}

export function exportJsonl(events: TelemetryEvent[]) {
  const blob = new Blob([events.map((event) => JSON.stringify(event)).join('\n')], { type: 'application/jsonl' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `gokkalkan-mock-telemetry-${Date.now()}.jsonl`;
  link.click();
  URL.revokeObjectURL(url);
}
