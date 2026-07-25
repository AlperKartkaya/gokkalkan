import { useEffect, useState } from 'react';
import type { Dispatch, SetStateAction } from 'react';
import {
  fetchOperatorReadiness,
  fetchOperatorSnapshot,
  operatorStateStreamUrl,
  type OperatorApiSnapshot,
  type OperatorReadinessReport,
} from '../operatorApiClient';

export interface OperatorBackendState {
  snapshot?: OperatorApiSnapshot;
  setSnapshot: Dispatch<SetStateAction<OperatorApiSnapshot | undefined>>;
  readiness?: OperatorReadinessReport;
  setReadiness: Dispatch<SetStateAction<OperatorReadinessReport | undefined>>;
  busy: boolean;
  error: string;
  readinessError: string;
}

/**
 * Owns the authoritative snapshot connection.
 *
 * SSE is the fast path. Any parse/transport failure triggers a full GET
 * snapshot, so a changed Mission Core runId after backend restart is never
 * merged into stale local safety state.
 */
export function useOperatorBackendState(apiBaseUrl: string): OperatorBackendState {
  const [snapshot, setSnapshot] = useState<OperatorApiSnapshot>();
  const [readiness, setReadiness] = useState<OperatorReadinessReport>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [readinessError, setReadinessError] = useState('');

  useEffect(() => {
    if (!apiBaseUrl) {
      setSnapshot(undefined);
      setReadiness(undefined);
      setBusy(false);
      setError('Backend API bağlı değil; komut ve güvenlik yüzeyi fail-closed.');
      setReadinessError('');
      return;
    }

    let cancelled = false;
    let fallbackTimer: number | undefined;
    let readinessTimer: number | undefined;
    let stream: EventSource | undefined;

    const applySnapshot = (next: OperatorApiSnapshot) => {
      if (cancelled) return;
      setSnapshot(next);
      setError('');
    };

    const loadSnapshot = (continueFallback = false) => {
      setBusy(true);
      void fetchOperatorSnapshot(apiBaseUrl)
        .then(applySnapshot)
        .catch((reason: unknown) => {
          if (!cancelled) {
            setError(reason instanceof Error ? reason.message : 'Backend snapshot alınamadı.');
          }
        })
        .finally(() => {
          if (cancelled) return;
          setBusy(false);
          if (continueFallback) scheduleFallback();
        });
    };

    const loadReadiness = () => {
      void fetchOperatorReadiness(apiBaseUrl)
        .then((report) => {
          if (cancelled) return;
          setReadiness(report);
          setReadinessError('');
        })
        .catch((reason: unknown) => {
          if (!cancelled) {
            setReadinessError(reason instanceof Error ? reason.message : 'Readiness raporu alınamadı.');
          }
        });
    };

    const scheduleFallback = () => {
      if (cancelled || fallbackTimer !== undefined) return;
      fallbackTimer = window.setTimeout(() => {
        fallbackTimer = undefined;
        loadSnapshot(true);
      }, 2_000);
    };

    loadSnapshot();
    loadReadiness();
    readinessTimer = window.setInterval(loadReadiness, 5_000);

    if (typeof EventSource === 'function') {
      stream = new EventSource(operatorStateStreamUrl(apiBaseUrl));
      stream.addEventListener('state', (event) => {
        try {
          applySnapshot(JSON.parse((event as MessageEvent<string>).data) as OperatorApiSnapshot);
          if (fallbackTimer !== undefined) {
            window.clearTimeout(fallbackTimer);
            fallbackTimer = undefined;
          }
          setBusy(false);
        } catch {
          setError('Backend state stream geçersiz JSON üretti.');
          scheduleFallback();
        }
      });
      stream.onerror = () => {
        if (cancelled) return;
        setError('Backend state stream kesildi; tam snapshot ile yeniden eşitleniyor.');
        scheduleFallback();
      };
    } else {
      scheduleFallback();
    }

    return () => {
      cancelled = true;
      stream?.close();
      if (fallbackTimer !== undefined) window.clearTimeout(fallbackTimer);
      if (readinessTimer !== undefined) window.clearInterval(readinessTimer);
    };
  }, [apiBaseUrl]);

  return {
    snapshot,
    setSnapshot,
    readiness,
    setReadiness,
    busy,
    error,
    readinessError,
  };
}
