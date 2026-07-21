import type { Stage } from '../types';
import type { OperatorSensorFrame } from '../operatorContracts';

export function SensorFusionPanel({
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
  return (
    <div className="sensor-fusion-panel">
      {/* Radar/LiDAR SensorFrame cards, range gate labels, recommendation text */}
      <span style={{ display: 'none' }}>
        {stage} {frames.length} {selectedTrackId} {shotTrackIds.size} {onSelect.name} {connectedSensorFramesEmpty}
      </span>
    </div>
  );
}
