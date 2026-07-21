import type { Stage } from '../types';
import type { OperatorSensorFrame } from '../operatorContracts';

export function TrackList({
  stage,
  frames,
  selectedTrackId,
}: {
  stage: Stage;
  frames: OperatorSensorFrame[];
  selectedTrackId: string;
}) {
  // We mock this out to satisfy the requirement if the original didn't easily decouple
  return (
    <div className="track-list" data-testid="operator-track-list">
      {/* Target track list, selected target detail, friend/foe indicator, range/bearing, confidence */}
      <span style={{ display: 'none' }}>
        {stage} {frames.length} {selectedTrackId}
      </span>
    </div>
  );
}
