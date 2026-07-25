import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { HardwareHealthBadge } from './HardwareHealthBadge';

describe('HardwareHealthBadge', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders loading state initially', () => {
    (globalThis.fetch as any).mockResolvedValue(new Promise(() => {})); // Never resolves
    render(<HardwareHealthBadge apiBaseUrl="http://api" />);
    
    expect(screen.getByText('Yükleniyor…')).toBeInTheDocument();
  });

  it('renders hardware ok state when backend returns ok', async () => {
    (globalThis.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        adapter: 'test-adapter',
        busConnected: true,
        picoReachable: true,
        dryRun: false,
        physicalOutputEnabled: false,
      })
    });

    render(<HardwareHealthBadge apiBaseUrl="http://api" />);


    await waitFor(() => {
      expect(screen.getByText('test-adapter')).toBeInTheDocument();
    });
    
    // Physical Output Should be Kapalı
    expect(screen.getByText(/Fiziksel Çıkış Kapalı/)).toBeInTheDocument();
  });

  it('renders warning state when hardware is not ok', async () => {
    (globalThis.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        adapter: 'test-adapter',
        busConnected: false,
        picoReachable: true,
        dryRun: true,
        physicalOutputEnabled: false,
      })
    });

    render(<HardwareHealthBadge apiBaseUrl="http://api" />);


    await waitFor(() => {
      expect(screen.getByText('test-adapter')).toBeInTheDocument();
    });

    // CAN BUS should be rendered
    const canBus = screen.getByText(/CAN Veriyolu/);
    expect(canBus).toBeInTheDocument();
  });
});
