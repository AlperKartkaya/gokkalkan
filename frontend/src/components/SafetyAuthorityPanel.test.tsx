import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
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
  it('renders normal safety status when not blocked', () => {
    render(<SafetyAuthorityPanel safety={defaultSafety} />);
    
    expect(screen.getByText('Emniyet Durumu')).toBeInTheDocument();
    expect(screen.getByText('SİSTEM HAZIR · NORMAL')).toBeInTheDocument();
    expect(screen.getByText('Pasif ✓')).toBeInTheDocument();
  });

  it('renders locked status and active warning when estop is active', () => {
    const activeSafety: OperatorSafetyState = { ...defaultSafety, estop: true, blockReason: 'BLOCKED_ESTOP' };
    render(<SafetyAuthorityPanel safety={activeSafety} />);
    
    expect(screen.getByText('KİLİTLİ / GÜVENLİK DEVREDE')).toBeInTheDocument();
    expect(screen.getByText('AKTİF ⚠️')).toBeInTheDocument();
  });

  it('renders all evidence rows and block reason summary', () => {
    const blockedSafety: OperatorSafetyState = {
      ...defaultSafety,
      motionZoneOk: false,
      blockReason: 'BLOCKED_MOTION_ZONE',
    };
    render(<SafetyAuthorityPanel safety={blockedSafety} />);
    
    expect(screen.getByText('Kilitli ⚠️')).toBeInTheDocument();
    expect(screen.getByTestId('operator-safety-state')).toBeInTheDocument();
  });
});

