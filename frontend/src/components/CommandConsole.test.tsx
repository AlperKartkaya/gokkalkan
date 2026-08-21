import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { CommandConsole } from './CommandConsole';

function renderConsole(overrides: Partial<Parameters<typeof CommandConsole>[0]> = {}) {
  const props: Parameters<typeof CommandConsole>[0] = {
    apiBusy: false,
    fireReady: false,
    fireCaption: 'blocked',
    operatorStopActive: false,
    maintenanceReady: true,
    maintenanceStatusCopy: 'hazır',
    maintenanceSessionActive: false,
    maintenanceRemainingSeconds: 90,
    onSendFireIntent: vi.fn(),
    onTriggerOperatorStop: vi.fn(),
    onOpenMaintenance: vi.fn(),
    ...overrides,
  };
  render(<CommandConsole {...props} />);
  return props;
}

describe('CommandConsole', () => {
  it('disables the fire button when not ready or busy', () => {
    renderConsole({ fireReady: false });
    expect(screen.getByRole('button', { name: 'ATEŞ' })).toBeDisabled();
  });

  it('triggers fire intent when fire button is ready and clicked', async () => {
    const onSendFireIntent = vi.fn();
    renderConsole({
      fireReady: true,
      onSendFireIntent,
    });

    const fireButton = screen.getByRole('button', { name: 'ATEŞ' });
    expect(fireButton).not.toBeDisabled();
    await userEvent.click(fireButton);
    expect(onSendFireIntent).toHaveBeenCalledOnce();
  });

  it('ends an active maintenance session through the visible maintenance control', async () => {
    const onOpenMaintenance = vi.fn();
    renderConsole({
      maintenanceReady: false,
      maintenanceSessionActive: true,
      maintenanceRemainingSeconds: 42.2,
      onOpenMaintenance,
    });

    await userEvent.click(screen.getByRole('button', { name: 'BİTİR · 43s' }));
    expect(onOpenMaintenance).toHaveBeenCalledOnce();
  });
});

