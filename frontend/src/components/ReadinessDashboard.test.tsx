import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ReadinessDashboard } from './ReadinessDashboard';

describe('ReadinessDashboard', () => {
  it('shows explicit fail-closed adapter states when readiness is unavailable', () => {
    render(
      <ReadinessDashboard
        maintenanceOpen
        setMaintenanceOpen={vi.fn()}
        readinessById={{}}
        config={{
          apiBaseUrl: '/api',
          connectionState: 'dry-run',
          dryRun: true,
          liveArmEnabled: false,
        }}
      />,
    );

    expect(screen.getByText('TFA50-L 1D LiDAR')).toBeInTheDocument();
    expect(screen.getByText(/5\/10\/15 m fiziksel kalibrasyon kanıtı bekleniyor/)).toBeInTheDocument();
    expect(screen.getByText(/Klasik CAN v1/)).toBeInTheDocument();
    expect(screen.queryByText(/RPLIDAR|Livox|point cloud/i)).not.toBeInTheDocument();
    expect(screen.queryByText('Radar/LiDAR Adapter')).not.toBeInTheDocument();
  });
});
