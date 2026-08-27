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
    expect(screen.getByText(/Fiziksel hareket çıkışı: KAPALI/)).toBeInTheDocument();
  });

  it('warns explicitly when the physical HIL motion path is enabled', async () => {
    (globalThis.fetch as any).mockResolvedValue({
      ok: true,
      json: async () => ({
        adapter: 'arduino_uno_serial',
        busConnected: true,
        arduinoReachable: true,
        dryRun: false,
        physicalOutputEnabled: true,
      })
    });

    render(<HardwareHealthBadge apiBaseUrl="http://api" />);

    expect(await screen.findByText(/Fiziksel hareket çıkışı: AÇIK/)).toBeInTheDocument();
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

    // Active field transport is Arduino USB serial.
    const usb = screen.getByText(/Arduino USB Seri/);
    expect(usb).toBeInTheDocument();
  });
});
