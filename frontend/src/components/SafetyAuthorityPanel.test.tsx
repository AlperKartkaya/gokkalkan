import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SafetyAuthorityPanel } from './SafetyAuthorityPanel';
import type { OperatorSafetyState } from '../operatorContracts';

const defaultSafety: OperatorSafetyState = {
  estop: false,
  motionZoneOk: true,
  fireZoneOk: true,
  targetGateOk: true,
  modeOk: true,
  backendConnected: true,
  perceptionConnected: true,
  sensorAdapterConnected: true,
  dryRun: true,
  liveArmEnabled: false,
  blockReason: 'ALLOWED',
  explanation: 'Test ok'
};

describe('SafetyAuthorityPanel', () => {
  it('renders E-Stop as ready when not active', () => {
    render(<SafetyAuthorityPanel safety={defaultSafety} onEStop={vi.fn()} eStopBusy={false} />);
    
    const button = screen.getByRole('button', { name: 'Acil Durdur — Yazılım E-Stop' });
    expect(button).toBeInTheDocument();
    expect(button).not.toBeDisabled();
    expect(screen.getByText('Pasif ✓')).toBeInTheDocument();
  });

  it('renders E-Stop as disabled and DURDURULDU when active', () => {
    const activeSafety: OperatorSafetyState = { ...defaultSafety, estop: true, blockReason: 'BLOCKED_ESTOP' };
    render(<SafetyAuthorityPanel safety={activeSafety} onEStop={vi.fn()} eStopBusy={false} />);
    
    const button = screen.getByRole('button', { name: 'Acil Durdur — Yazılım E-Stop' });
    expect(button).toHaveClass('cursor-not-allowed');
    expect(button).toBeDisabled();
    expect(screen.getByText('AKTİF ⚠️')).toBeInTheDocument();
  });

  it('calls onEStop when clicked', async () => {
    const mockEStop = vi.fn();
    render(<SafetyAuthorityPanel safety={defaultSafety} onEStop={mockEStop} eStopBusy={false} />);
    
    const button = screen.getByRole('button', { name: 'Acil Durdur — Yazılım E-Stop' });
    await userEvent.click(button);
    expect(mockEStop).toHaveBeenCalledTimes(1);
  });
});
