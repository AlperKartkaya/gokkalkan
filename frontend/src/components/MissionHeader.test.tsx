import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MissionHeader } from './MissionHeader';
import type { OperatorPanelConfig } from '../operatorContracts';

const mockConfig: OperatorPanelConfig = {
  apiBaseUrl: 'http://localhost:8088',
  dryRun: false,
  connectionState: 'live',
  liveArmEnabled: false,
};

describe('MissionHeader', () => {
  it('renders mission remaining seconds and highlights if <= 30', () => {
    const { rerender } = render(
      <MissionHeader
        apiBusy={false}
        config={mockConfig}
        stage={1}
        mode="autonomous"
        round={1}
        onRawLidarOpen={vi.fn()}
        onRawCameraOpen={vi.fn()}
        onReset={vi.fn()}
        missionRemainingSeconds={45}
      />
    );

    // It should render 45s and not have animate-pulse
    const timerText = screen.getByText('45s');
    expect(timerText).toBeInTheDocument();
    
    // Check if the parent has the normal classes, not pulse
    const container = timerText.parentElement;
    expect(container).not.toHaveClass('animate-pulse');
    expect(container).toHaveClass('border-[#48a8ff]/30');

    // Rerender with critical time
    rerender(
      <MissionHeader
        apiBusy={false}
        config={mockConfig}
        stage={1}
        mode="autonomous"
        round={1}
        onRawLidarOpen={vi.fn()}
        onRawCameraOpen={vi.fn()}
        onReset={vi.fn()}
        missionRemainingSeconds={29}
      />
    );

    const criticalTimerText = screen.getByText('29s');
    expect(criticalTimerText).toBeInTheDocument();
    
    // Check if it has pulse animation
    const criticalContainer = criticalTimerText.parentElement;
    expect(criticalContainer).toHaveClass('animate-pulse');
    expect(criticalContainer).toHaveClass('border-[#ff4757]/60');
  });

  it('calls onReset when reset button is clicked', async () => {
    const mockReset = vi.fn();
    render(
      <MissionHeader
        apiBusy={false}
        config={mockConfig}
        stage={1}
        mode="autonomous"
        round={1}
        onRawLidarOpen={vi.fn()}
        onRawCameraOpen={vi.fn()}
        onReset={mockReset}
        missionRemainingSeconds={300}
      />
    );

    const resetButton = screen.getByTestId('operator-reset-button');
    await userEvent.click(resetButton);
    expect(mockReset).toHaveBeenCalledTimes(1);
  });
});
