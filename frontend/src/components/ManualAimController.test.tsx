import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { ManualAimController } from './ManualAimController';

describe('ManualAimController field mapping', () => {
  it('uses the Arduino 50-pulse angle and real field axes', () => {
    const onManualAim = vi.fn();
    render(
      <ManualAimController
        apiBusy={false}
        manualAimReady
        onManualAim={onManualAim}
      />,
    );

    const deadman = screen.getByTestId('operator-deadman-button');
    fireEvent.pointerDown(deadman);
    fireEvent.click(screen.getByTestId('operator-aim-up'));
    fireEvent.click(screen.getByTestId('operator-aim-left'));
    fireEvent.click(screen.getByTestId('operator-aim-right'));
    fireEvent.click(screen.getByTestId('operator-aim-down'));
    fireEvent.pointerUp(deadman);

    expect(onManualAim.mock.calls).toEqual([
      [0, 11.25],
      [-11.25, 0],
      [11.25, 0],
      [0, -11.25],
    ]);
    expect(screen.getByTestId('operator-aim-right')).toBeDisabled();
    expect(screen.getByText(/Saha adımı: 11.25°/)).toBeInTheDocument();
  });
});
