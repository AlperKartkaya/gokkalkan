import { useEffect, useMemo, useState } from 'react';
import {
  MANUAL_AIM_RATE_LIMIT_DEG_PER_SEC,
  MANUAL_AIM_STEP_DEG,
  canSendManualAim,
  canSendFireIntent,
  evaluateOperatorSafety,
  makeCommandResult,
  makeFireIntent,
  makeManualAimCommand,
  operatorBlockCopy,
  type CommandResult,
  type FireIntent,
  type ManualAimCommand,
  type OperatorPanelConfig,
  type OperatorTrackState,
} from './operatorContracts';
import {
  fetchOperatorReplay,
  fetchOperatorReadiness,
  fetchOperatorSnapshot,
  fetchOperatorTelemetryExport,
  resetOperatorTelemetry,
  sendOperatorFireIntent,
  sendOperatorManualAimCommand,
  sendOperatorModeRequest,
  type HardwareResult,
  type OperatorApiSnapshot,
  type OperatorReplayBundle,
  type OperatorReadinessItem,
  type OperatorReadinessReport,
  type OperatorReadinessStatus,
  type OperatorTelemetryExport,
  type OperatorTelemetryLogRecord,
} from './operatorApiClient';
import type { Mode, TargetType } from './types';

const targetLabel: Record<TargetType, string> = {
  F16: 'Savaş Uçağı / F16',
  Helikopter: 'Helikopter',
  'Balistik Füze': 'Balistik Füze',
  'Mini/Micro İHA': 'Mini/Micro İHA',
};

const dryRunTracks: OperatorTrackState[] = [
  {
    trackId: 'DRY-RUN-F16-01',
    stage: 3,
    round: 1,
    targetType: 'F16',
    friendFoe: 'Düşman',
    rangeM: 12.4,
    bearingDeg: -18,
    confidence: 0.96,
    source: 'dry-run',
    updatedAt: '2026-05-25T20:00:00.000Z',
  },
  {
    trackId: 'DRY-RUN-HEL-02',
    stage: 3,
    round: 1,
    targetType: 'Helikopter',
    friendFoe: 'Dost',
    rangeM: 8.1,
    bearingDeg: 4,
    confidence: 0.91,
    source: 'dry-run',
    updatedAt: '2026-05-25T20:00:00.000Z',
  },
  {
    trackId: 'DRY-RUN-UAV-03',
    stage: 3,
    round: 1,
    targetType: 'Mini/Micro İHA',
    friendFoe: 'Dost',
    rangeM: 4.2,
    bearingDeg: 23,
    confidence: 0.88,
    source: 'dry-run',
    updatedAt: '2026-05-25T20:00:00.000Z',
  },
];

function statusTone(ok: boolean) {
  return ok ? 'border-[#33e68c]/30 bg-[#33e68c]/10 text-[#bfffe0]' : 'border-[#ffbb42]/30 bg-[#ffbb42]/10 text-[#ffe4ad]';
}

const readinessCopy: Record<OperatorReadinessStatus, string> = {
  ready: 'Hazır',
  partial: 'Kısmi',
  tbd: 'TBD',
  blocked: 'Kilitli',
};

function readinessTone(status: OperatorReadinessStatus) {
  if (status === 'ready') return 'border-[#33e68c]/30 bg-[#33e68c]/10 text-[#bfffe0]';
  if (status === 'partial') return 'border-[#ffbb42]/30 bg-[#ffbb42]/10 text-[#ffe4ad]';
  if (status === 'blocked') return 'border-[#ff4757]/30 bg-[#ff4757]/10 text-[#ffbdc4]';
  return 'border-[#48a8ff]/30 bg-[#48a8ff]/10 text-[#cbe9ff]';
}

function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function targetRangeGateOk(track: OperatorTrackState | undefined) {
  if (!track) return false;
  if (track.targetType === 'F16') return track.rangeM >= 10 && track.rangeM <= 15;
  if (track.targetType === 'Helikopter' || track.targetType === 'Balistik Füze') return track.rangeM >= 5 && track.rangeM <= 15;
  if (track.targetType === 'Mini/Micro İHA') return track.rangeM >= 0 && track.rangeM <= 15;
  return false;
}

function commandLabel(result: CommandResult) {
  if (result.kind === 'FireIntent') return 'FireIntent';
  if (result.kind === 'ManualAimCommand') return 'ManualAimCommand';
  return 'ModeRequest';
}

function shortRecordPayload(record: OperatorTelemetryLogRecord) {
  const value = record.payload ? JSON.stringify(record.payload) : record.raw ?? 'payload yok';
  return value.length > 120 ? `${value.slice(0, 120)}…` : value;
}

export default function OperatorPanel({ onBack, onOpenSimulator }: { onBack: () => void; onOpenSimulator: () => void }) {
  const queryApiBaseUrl = useMemo(() => new URLSearchParams(window.location.search).get('operatorApi')?.trim() ?? '', []);
  const envApiBaseUrl = (import.meta.env.VITE_GOKKALKAN_OPERATOR_API_BASE as string | undefined)?.trim() ?? '';
  const apiBaseUrl = queryApiBaseUrl || envApiBaseUrl;
  const liveArmEnabled = import.meta.env.VITE_GOKKALKAN_OPERATOR_LIVE_ARMED === '1';
  const [dryRun, setDryRun] = useState(true);
  const [mode, setMode] = useState<Mode>('safe');
  const [selectedTrackId, setSelectedTrackId] = useState(dryRunTracks[0]?.trackId ?? '');
  const [lastIntent, setLastIntent] = useState<FireIntent>();
  const [lastManualAim, setLastManualAim] = useState<ManualAimCommand>();
  const [lastHardwareResult, setLastHardwareResult] = useState<HardwareResult>();
  const [deadmanActive, setDeadmanActive] = useState(false);
  const [manualAimRate, setManualAimRate] = useState(MANUAL_AIM_RATE_LIMIT_DEG_PER_SEC);
  const [apiSnapshot, setApiSnapshot] = useState<OperatorApiSnapshot>();
  const [apiError, setApiError] = useState('');
  const [apiBusy, setApiBusy] = useState(false);
  const [readinessReport, setReadinessReport] = useState<OperatorReadinessReport>();
  const [readinessError, setReadinessError] = useState('');
  const [telemetryExport, setTelemetryExport] = useState<OperatorTelemetryExport>();
  const [replayBundle, setReplayBundle] = useState<OperatorReplayBundle>();
  const [evidenceBusy, setEvidenceBusy] = useState(false);
  const [evidenceError, setEvidenceError] = useState('');
  const [evidenceNotice, setEvidenceNotice] = useState('');
  const [commandResults, setCommandResults] = useState<CommandResult[]>([
    makeCommandResult({
      commandId: 'BOOT-DRY-RUN',
      kind: 'ModeRequest',
      accepted: true,
      dryRun: true,
      safetyBlockReason: 'ALLOWED',
      createdAt: new Date('2026-05-25T20:00:00Z'),
    }),
  ]);

  useEffect(() => {
    if (!apiBaseUrl) {
      setApiSnapshot(undefined);
      setReadinessReport(undefined);
      setTelemetryExport(undefined);
      setReplayBundle(undefined);
      setApiError('');
      setReadinessError('');
      setEvidenceError('');
      setEvidenceNotice('Backend API bağlantısı olmadan yalnız yerel dry-run olay akışı gösterilir.');
      return;
    }

    let cancelled = false;
    setApiBusy(true);
    Promise.all([
      fetchOperatorSnapshot(apiBaseUrl),
      fetchOperatorReadiness(apiBaseUrl).catch((error: unknown) => {
        if (!cancelled) setReadinessError(error instanceof Error ? error.message : 'Readiness raporu alınamadı.');
        return undefined;
      }),
    ])
      .then(([snapshot, readiness]) => {
        if (cancelled) return;
        setApiSnapshot(snapshot);
        setReadinessReport(readiness);
        setApiError('');
        if (readiness) setReadinessError('');
        setMode(snapshot.mode);
        if (snapshot.commandResults.length > 0) setCommandResults(snapshot.commandResults);
        if (snapshot.tracks[0] && !snapshot.tracks.some((track) => track.trackId === selectedTrackId)) {
          setSelectedTrackId(snapshot.tracks[0].trackId);
        }
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setApiSnapshot(undefined);
        setReadinessReport(undefined);
        setApiError(error instanceof Error ? error.message : 'Backend API bağlantısı kurulamadı.');
      })
      .finally(() => {
        if (!cancelled) setApiBusy(false);
      });

    return () => {
      cancelled = true;
    };
  }, [apiBaseUrl, selectedTrackId]);

  const config: OperatorPanelConfig = useMemo(() => {
    const apiReady = Boolean(apiSnapshot && !apiError);
    const connectionState = dryRun ? 'dry-run' : apiReady ? (apiSnapshot?.dryRun ? 'dry-run' : 'live') : 'offline';
    return {
      apiBaseUrl: apiBaseUrl || 'local-dry-run-adapter',
      connectionState,
      dryRun,
      liveArmEnabled: liveArmEnabled && !dryRun,
    };
  }, [apiBaseUrl, apiError, apiSnapshot, dryRun, liveArmEnabled]);

  const visibleTracks = apiSnapshot?.tracks.length ? apiSnapshot.tracks : dryRunTracks;
  const selectedTrack = visibleTracks.find((track) => track.trackId === selectedTrackId);
  const selectedTargetGateOk = Boolean(selectedTrack && selectedTrack.friendFoe === 'Düşman' && targetRangeGateOk(selectedTrack));
  const safety = evaluateOperatorSafety({
    estop: apiSnapshot?.safety.estop ?? false,
    motionZoneOk: apiSnapshot?.safety.motionZoneOk ?? true,
    fireZoneOk: apiSnapshot?.safety.fireZoneOk ?? true,
    targetGateOk: selectedTargetGateOk,
    modeOk: mode === 'manual' || mode === 'autonomous',
    backendConnected: apiSnapshot?.safety.backendConnected ?? config.connectionState !== 'offline',
    perceptionConnected: apiSnapshot?.safety.perceptionConnected ?? config.connectionState === 'live',
    sensorAdapterConnected: apiSnapshot?.safety.sensorAdapterConnected ?? config.connectionState === 'live',
    dryRun: config.dryRun,
    liveArmEnabled: config.liveArmEnabled,
  });
  const fireReady = canSendFireIntent(safety, selectedTrack?.trackId);
  const manualAimReady = canSendManualAim({
    mode,
    deadmanActive,
    dryRun: config.dryRun,
    liveArmEnabled: config.liveArmEnabled,
    backendConnected: config.connectionState !== 'offline',
  });
  const manualAimBlockReason = config.connectionState === 'offline'
    ? 'BLOCKED_BACKEND'
    : !config.dryRun && !config.liveArmEnabled
      ? 'BLOCKED_ARMING'
      : 'BLOCKED_MODE';
  const telemetryMetadata = telemetryExport?.telemetry ?? apiSnapshot?.telemetry;
  const evidenceEntries = telemetryExport?.entries ?? replayBundle?.entries ?? [];
  const replayHardwareCount = replayBundle?.hardwareResults.length ?? 0;
  const replayCommandCount = replayBundle?.commandResults.length ?? 0;
  const replayEventCount = replayBundle?.events.length ?? 0;
  const fallbackReadiness: OperatorReadinessReport = {
    schemaVersion: 1,
    generatedAt: new Date().toISOString(),
    summary: apiBaseUrl
      ? 'Backend readiness raporu alınamadı; panel temel state üzerinden çalışıyor.'
      : 'Backend API bağlanmadan yalnız operatör UI kabuğu ve yerel dry-run izleri görülebilir.',
    scoreBasis: 'Bu yüzde resmi yarışma uygunluk skoru değildir; repo içi entegrasyon kontrol listesidir.',
    readinessPercent: apiBaseUrl && !apiError ? 28 : 12,
    physicalOutputEnabled: false,
    mode,
    dryRun: config.dryRun,
    items: [
      {
        id: 'operator_panel_ui',
        label: 'Operatör Paneli UI',
        status: 'ready',
        owner: 'Frontend',
        evidence: 'Panel mod, manuel yönlendirme, FireIntent, hedef detayı, Safety Gate, readiness ve kanıt/replay yüzeylerini gösterir.',
        nextStep: 'Canlı kamera/perception ve saha kiosk düzeni gerçek donanımla ayrıca denenmeli.',
        ktrInterface: 'Kullanıcı Arayüzü, ManualAimCommand',
      },
      {
        id: 'backend_api',
        label: 'Backend Operatör API',
        status: apiBaseUrl && !apiError ? 'partial' : 'tbd',
        owner: 'Backend',
        evidence: apiBaseUrl ? 'API base URL verilmiş; state/readiness yanıtı temel panelde kullanılabilir.' : 'API base URL yok.',
        nextStep: 'Dry-run API sunucusunu başlat ve operatorApi/VITE_GOKKALKAN_OPERATOR_API_BASE ile bağla.',
        ktrInterface: 'ModeRequest, ManualAimCommand, FireIntent',
      },
      {
        id: 'perception_adapter',
        label: 'Perception Adapter',
        status: 'tbd',
        owner: 'Perception',
        evidence: 'Canlı sınıflandırma akışı bağlanmadı; UI TrackState sözleşmesini bekliyor.',
        nextStep: 'Kamera/model çıktısını TrackState olarak backend/UI akışına bağla.',
        ktrInterface: 'TrackState',
      },
      {
        id: 'radar_lidar_adapter',
        label: 'Radar/LiDAR Adapter',
        status: 'tbd',
        owner: 'Sensör',
        evidence: 'Gerçek menzil/açı/kalite akışı henüz bağlı değil.',
        nextStep: 'Seçilen sensörün güç, veri, timestamp ve sağlık mesajı sözleşmesini doldur.',
        ktrInterface: 'SensorFrame',
      },
      {
        id: 'hardware_adapter',
        label: 'Hardware Adapter',
        status: 'partial',
        owner: 'Backend + Elektronik',
        evidence: 'Mock hardware sonucu fiziksel çıkışsız gösterilir; gerçek MCU protokolü seçilmedi.',
        nextStep: 'MCU mesaj çerçevesi ve pan/tilt limitlerini elektronik/mekanik ekiple netleştir.',
        ktrInterface: 'HardwareResult',
      },
      {
        id: 'live_arming',
        label: 'Canlı Arming / Fiziksel Çıkış',
        status: 'blocked',
        owner: 'Safety + Elektronik',
        evidence: 'Geliştirme paneli fiziksel çıkış üretmez.',
        nextStep: 'İki aşamalı arming ve fiziksel interlock doğrulaması tamamlanmadan canlı çıkış açma.',
        ktrInterface: 'ArmingState, InterlockState',
      },
    ],
    nextCriticalActions: [
      'Dry-run backend API ile readiness raporunu canlı doğrula.',
      'Radar/LiDAR ve perception adapter sözleşmelerini gerçek donanıma bağla.',
      'MCU haberleşme protokolü ve imha hattı interlock mesajlarını netleştir.',
    ],
  };
  const displayReadiness = readinessReport ?? fallbackReadiness;
  const topReadinessItems = displayReadiness.items.slice(0, 6);
  const readinessById = Object.fromEntries(displayReadiness.items.map((item) => [item.id, item])) as Record<string, OperatorReadinessItem | undefined>;

  const pushResult = (result: CommandResult) => {
    setCommandResults((previous) => [result, ...previous].slice(0, 8));
  };

  const loadTelemetryEvidence = async () => {
    if (!apiBaseUrl) {
      setEvidenceError('Backend API bağlantısı yok; export/replay için dry-run API başlatılmalı.');
      setEvidenceNotice('Yerel panel olay akışı görüntüleniyor.');
      return;
    }

    const [exported, replay, readiness] = await Promise.all([
      fetchOperatorTelemetryExport(apiBaseUrl),
      fetchOperatorReplay(apiBaseUrl),
      fetchOperatorReadiness(apiBaseUrl).catch((error: unknown) => {
        setReadinessError(error instanceof Error ? error.message : 'Readiness raporu alınamadı.');
        return undefined;
      }),
    ]);
    setTelemetryExport(exported);
    setReplayBundle(replay);
    if (readiness) {
      setReadinessReport(readiness);
      setReadinessError('');
    }
    setApiSnapshot(exported.state);
    if (exported.commandResults.length > 0) setCommandResults(exported.commandResults);
    setEvidenceError('');
    setEvidenceNotice('Kanıt paketi güncellendi; replay yalnız kayıt okur.');
  };

  const refreshTelemetryEvidence = () => {
    setEvidenceBusy(true);
    void loadTelemetryEvidence()
      .catch((error: unknown) => {
        setEvidenceError(error instanceof Error ? error.message : 'Telemetri kanıtı alınamadı.');
        setEvidenceNotice('');
      })
      .finally(() => setEvidenceBusy(false));
  };

  const resetTelemetryEvidence = () => {
    if (!apiBaseUrl) {
      setEvidenceError('Backend API bağlantısı yok; sıfırlama yalnız API üzerinden yapılır.');
      return;
    }

    setEvidenceBusy(true);
    void resetOperatorTelemetry(apiBaseUrl)
      .then(async (response) => {
        setApiSnapshot(response.state);
        setCommandResults(response.state.commandResults);
        setEvidenceNotice('Telemetri sıfırlandı; safe moda dönüldü ve fiziksel çıkış üretilmedi.');
        setEvidenceError('');
        const [exported, replay, readiness] = await Promise.all([
          fetchOperatorTelemetryExport(apiBaseUrl),
          fetchOperatorReplay(apiBaseUrl),
          fetchOperatorReadiness(apiBaseUrl).catch((error: unknown) => {
            setReadinessError(error instanceof Error ? error.message : 'Readiness raporu alınamadı.');
            return undefined;
          }),
        ]);
        setTelemetryExport(exported);
        setReplayBundle(replay);
        if (readiness) {
          setReadinessReport(readiness);
          setReadinessError('');
        }
      })
      .catch((error: unknown) => {
        setEvidenceError(error instanceof Error ? error.message : 'Telemetri sıfırlanamadı.');
        setEvidenceNotice('');
      })
      .finally(() => setEvidenceBusy(false));
  };

  const recordMode = (nextMode: Mode) => {
    setMode(nextMode);
    if (nextMode !== 'manual') setDeadmanActive(false);
    if (apiBaseUrl) {
      setApiBusy(true);
      void sendOperatorModeRequest(apiBaseUrl, {
        kind: 'ModeRequest',
        requestedMode: nextMode,
        operatorId: 'OP-UI-1',
        timestamp: new Date().toISOString(),
        reason: 'operator-panel',
        dryRun: config.dryRun,
      })
        .then((response) => {
          pushResult(response.result);
          setApiSnapshot(response.state);
          setLastHardwareResult(response.hardwareResult ?? undefined);
          setApiError('');
        })
        .catch((error: unknown) => {
          pushResult(makeCommandResult({
            commandId: `MODE-BLOCK-${Date.now()}`,
            kind: 'ModeRequest',
            accepted: false,
            dryRun: config.dryRun,
            safetyBlockReason: 'BLOCKED_BACKEND',
          }));
          setApiError(error instanceof Error ? error.message : 'Backend API mode komutunu kabul etmedi.');
        })
        .finally(() => setApiBusy(false));
      return;
    }

    const accepted = config.connectionState !== 'offline';
    pushResult(makeCommandResult({
      commandId: `MODE-${nextMode}-${Date.now()}`,
      kind: 'ModeRequest',
      accepted,
      dryRun: config.dryRun,
      safetyBlockReason: accepted ? 'ALLOWED' : 'BLOCKED_BACKEND',
    }));
  };

  const sendFireIntent = () => {
    if (!selectedTrack || !fireReady) {
      pushResult(makeCommandResult({
        commandId: `BLOCK-${Date.now()}`,
        kind: 'FireIntent',
        accepted: false,
        dryRun: config.dryRun,
        safetyBlockReason: safety.blockReason,
      }));
      return;
    }

    const intent = makeFireIntent({ targetId: selectedTrack.trackId, stage: selectedTrack.stage, round: selectedTrack.round, dryRun: config.dryRun });
    setLastIntent(intent);
    if (apiBaseUrl) {
      setApiBusy(true);
      void sendOperatorFireIntent(apiBaseUrl, intent)
        .then((response) => {
          pushResult(response.result);
          setApiSnapshot(response.state);
          setApiError('');
        })
        .catch((error: unknown) => {
          pushResult(makeCommandResult({
            commandId: `FIRE-BLOCK-${Date.now()}`,
            kind: 'FireIntent',
            accepted: false,
            dryRun: config.dryRun,
            safetyBlockReason: 'BLOCKED_BACKEND',
          }));
          setLastHardwareResult(undefined);
          setApiError(error instanceof Error ? error.message : 'Backend API fire intent komutunu kabul etmedi.');
        })
        .finally(() => setApiBusy(false));
      return;
    }

    const result = makeCommandResult({
      commandId: intent.requestedAt,
      kind: intent.kind,
      accepted: true,
      dryRun: intent.dryRun,
      safetyBlockReason: 'ALLOWED',
    });
    pushResult(result);
    setLastHardwareResult({
      adapter: 'local-ui.dry-run',
      commandId: result.commandId,
      kind: intent.kind,
      accepted: true,
      completed: true,
      physicalOutput: false,
      message: 'Yerel dry-run panel komutu kaydetti; fiziksel çıkış üretilmedi.',
      createdAt: result.createdAt,
    });
  };

  const sendManualAim = (panDeltaDeg: number, tiltDeltaDeg: number) => {
    const command = makeManualAimCommand({
      panDeltaDeg,
      tiltDeltaDeg,
      deadmanActive,
      dryRun: config.dryRun,
      rateLimitDegPerSec: manualAimRate,
    });
    setLastManualAim(command);

    if (!manualAimReady) {
      pushResult(makeCommandResult({
        commandId: `AIM-BLOCK-${Date.now()}`,
        kind: 'ManualAimCommand',
        accepted: false,
        dryRun: config.dryRun,
        safetyBlockReason: manualAimBlockReason,
      }));
      setLastHardwareResult(undefined);
      return;
    }

    if (apiBaseUrl) {
      setApiBusy(true);
      void sendOperatorManualAimCommand(apiBaseUrl, command)
        .then((response) => {
          pushResult(response.result);
          setApiSnapshot(response.state);
          setLastHardwareResult(response.hardwareResult ?? undefined);
          setApiError('');
        })
        .catch((error: unknown) => {
          pushResult(makeCommandResult({
            commandId: `AIM-BLOCK-${Date.now()}`,
            kind: 'ManualAimCommand',
            accepted: false,
            dryRun: config.dryRun,
            safetyBlockReason: 'BLOCKED_BACKEND',
          }));
          setLastHardwareResult(undefined);
          setApiError(error instanceof Error ? error.message : 'Backend API manuel yönlendirme komutunu kabul etmedi.');
        })
        .finally(() => setApiBusy(false));
      return;
    }

    const result = makeCommandResult({
      commandId: `AIM-${Date.now()}`,
      kind: 'ManualAimCommand',
      accepted: true,
      dryRun: command.dryRun,
      safetyBlockReason: 'ALLOWED',
    });
    pushResult(result);
    setLastHardwareResult({
      adapter: 'local-ui.dry-run',
      commandId: result.commandId,
      kind: command.kind,
      accepted: true,
      completed: true,
      physicalOutput: false,
      message: 'Yerel dry-run manuel yönlendirme kaydedildi; pan/tilt çıkışı üretilmedi.',
      createdAt: result.createdAt,
    });
  };

  return (
    <main className="operator-shell min-h-screen bg-[#05070a] p-3 text-[#ecf7ff]" data-testid="operator-panel">
      <header className="mb-3 grid gap-3 rounded-xl border border-[#25d8ff]/18 bg-[rgba(7,10,14,.94)] p-3 shadow-[0_18px_50px_rgba(0,0,0,.28)] min-[1000px]:grid-cols-[1fr_auto]">
        <div>
          <p className="m-0 text-xs font-black uppercase tracking-[.18em] text-[#ffbb42]">Gerçek sistem paneli · ilk entegrasyon geçişi</p>
          <h1 className="m-0 mt-1 text-3xl font-black tracking-[.04em] text-white min-[760px]:text-4xl">GÖKKALKAN OPERATÖR PANELİ</h1>
          <p className="m-0 mt-2 max-w-[78ch] text-sm leading-relaxed text-[#b7c9d5]">
            Bu ekran simülasyon değildir; backend/perception/hardware entegrasyonu için hazırlanmış güvenli operatör yüzeyidir. Bu geçişte komutlar dry-run niyeti olarak loglanır, fiziksel çıkış üretilmez.
          </p>
        </div>
        <div className="grid content-start gap-2 min-[560px]:grid-cols-2 min-[1000px]:min-w-[360px]">
          <button className="rounded-lg border border-white/10 bg-white/[.07] px-3 py-2 text-sm font-black text-[#eaf7ff]" onClick={onBack}>Landing’e dön</button>
          <button className="rounded-lg border border-[#25d8ff]/25 bg-[#25d8ff]/10 px-3 py-2 text-sm font-black text-[#bff2ff]" onClick={onOpenSimulator}>Simülatöre dön</button>
          <button className="col-span-full rounded-lg border border-[#ffbb42]/30 bg-[#ffbb42]/10 px-3 py-2 text-sm font-black text-[#ffe4ad]" onClick={() => setDryRun((value) => !value)}>
            {dryRun ? 'DRY-RUN AÇIK · fiziksel çıkış yok' : 'DRY-RUN KAPALI · canlı kilit gerekli'}
          </button>
        </div>
      </header>

      <section className="mb-3 grid gap-2 min-[900px]:grid-cols-5" aria-label="Canlı bağlantı durumları">
        <span className={`rounded-lg border px-3 py-2 text-sm font-black ${statusTone(config.connectionState !== 'offline')}`}>Backend: {apiBusy ? 'kontrol ediliyor' : config.connectionState === 'offline' ? 'bağlantı yok' : config.connectionState === 'dry-run' ? 'dry-run adapter' : 'canlı API'}</span>
        <span className={`rounded-lg border px-3 py-2 text-sm font-black ${statusTone(safety.perceptionConnected)}`}>Perception: {safety.perceptionConnected ? 'canlı' : 'placeholder'}</span>
        <span className={`rounded-lg border px-3 py-2 text-sm font-black ${statusTone(safety.sensorAdapterConnected)}`}>Radar/LiDAR: {safety.sensorAdapterConnected ? 'canlı' : 'TBD'}</span>
        <span className={`rounded-lg border px-3 py-2 text-sm font-black ${statusTone(safety.blockReason === 'ALLOWED')}`}>Safety Gate: {safety.blockReason}</span>
        <span className="rounded-lg border border-[#48a8ff]/30 bg-[#48a8ff]/10 px-3 py-2 text-sm font-black text-[#cbe9ff]">API: {apiError || config.apiBaseUrl}</span>
      </section>

      <section className="mb-3 rounded-xl border border-[#25d8ff]/18 bg-[rgba(7,10,14,.94)] p-4" data-testid="operator-readiness-dashboard" aria-label="Finale hazırlık göstergesi">
        <div className="grid gap-4 min-[1000px]:grid-cols-[minmax(260px,.42fr)_1fr]">
          <div>
            <p className="m-0 text-xs font-black uppercase tracking-[.16em] text-[#25d8ff]">Finale Hazırlık</p>
            <h2 className="m-0 mt-1 text-2xl font-black text-white">Gerçek sisteme yakınlık: %{displayReadiness.readinessPercent}</h2>
            <div className="mt-3 h-3 overflow-hidden rounded-full border border-white/[.08] bg-white/[.06]" aria-label="Readiness progress">
              <div className="h-full rounded-full bg-gradient-to-r from-[#ffbb42] via-[#25d8ff] to-[#33e68c]" style={{ width: `${Math.max(4, Math.min(100, displayReadiness.readinessPercent))}%` }} />
            </div>
            <p className="m-0 mt-3 text-sm leading-relaxed text-[#b7c9d5]">{displayReadiness.summary}</p>
            <p className="m-0 mt-2 text-xs font-bold text-[#91a6b7]">{displayReadiness.scoreBasis}</p>
            {readinessError && <p className="m-0 mt-3 rounded-lg border border-[#ffbb42]/25 bg-[#ffbb42]/10 p-3 text-sm font-bold text-[#ffe4ad]">Hazırlık API uyarısı: {readinessError}</p>}
            <div className="mt-3 rounded-lg border border-[#ffbb42]/25 bg-[#ffbb42]/10 p-3">
              <b className="block text-sm text-[#ffe4ad]">Sıradaki kritik adım</b>
              <p className="m-0 mt-1 text-sm leading-relaxed text-[#f4e4bf]">{displayReadiness.nextCriticalActions[0] ?? 'Plan güncel; sıradaki entegrasyon adımı seçilmeli.'}</p>
            </div>
          </div>
          <div className="grid gap-2 min-[760px]:grid-cols-2 min-[1300px]:grid-cols-3">
            {topReadinessItems.map((item) => (
              <ReadinessCard key={item.id} item={item} />
            ))}
          </div>
        </div>
      </section>

      <section className="grid gap-3 min-[1100px]:grid-cols-[minmax(0,1.25fr)_minmax(330px,.75fr)]">
        <div className="grid gap-3">
          <section className="relative min-h-[420px] overflow-hidden rounded-xl border border-[#25d8ff]/18 bg-[radial-gradient(circle_at_50%_45%,rgba(37,216,255,.12),rgba(4,7,10,.96)_58%)] p-4" aria-label="Canlı görüntü ve sensör füzyonu">
            <div className="absolute inset-0 opacity-40 [background-image:linear-gradient(rgba(255,255,255,.04)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,.035)_1px,transparent_1px)] [background-size:34px_34px]" />
            <div className="relative z-[1] flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="m-0 text-xs font-black uppercase tracking-[.16em] text-[#25d8ff]">Canlı görüntü / sensör füzyonu</p>
                <h2 className="m-0 mt-1 text-2xl font-black">Kamera ve iz bindirmesi</h2>
                <p className="m-0 mt-1 max-w-[62ch] text-sm text-[#b7c9d5]">Kamera, radar ve LiDAR bağlantısı geldiğinde bu alan `TrackState` ve `SensorFrame` akışıyla beslenecek. Şu an dry-run hedef izleri gösteriliyor.</p>
              </div>
              <span className="rounded-full border border-[#ffbb42]/35 bg-[#ffbb42]/10 px-3 py-1 text-xs font-black text-[#ffe4ad]">Fiziksel çıkış yok</span>
            </div>
            <div className="relative z-[1] mt-8 h-[290px] rounded-lg border border-white/[.08] bg-black/25">
              <div className="absolute left-[12%] top-[18%] text-xs font-black text-[#91a6b7]">15 m</div>
              <div className="absolute left-[42%] top-[18%] text-xs font-black text-[#91a6b7]">10 m</div>
              <div className="absolute left-[68%] top-[18%] text-xs font-black text-[#91a6b7]">5 m</div>
              <div className="absolute bottom-6 right-6 grid h-20 w-20 place-items-center rounded-full border border-[#33e68c]/40 bg-[#33e68c]/10 text-xs font-black text-[#ccffe2]">Gökkalkan</div>
              {visibleTracks.map((track, index) => (
                <button
                  key={track.trackId}
                  className={`absolute min-w-[132px] rounded-lg border px-3 py-2 text-left text-xs shadow-[0_12px_24px_rgba(0,0,0,.28)] ${track.trackId === selectedTrackId ? 'border-[#ffbb42] bg-[#ffbb42]/20 text-white' : track.friendFoe === 'Düşman' ? 'border-[#ff4757]/45 bg-[#ff4757]/12 text-[#ffd6da]' : 'border-[#48a8ff]/45 bg-[#48a8ff]/12 text-[#d7efff]'}`}
                  style={{ left: `${18 + index * 25}%`, top: `${38 + index * 13}%` }}
                  onClick={() => setSelectedTrackId(track.trackId)}
                >
                  <b className="block text-sm">{targetLabel[track.targetType]}</b>
                  <span>{track.friendFoe} · {track.rangeM.toFixed(1)} m · {formatPercent(track.confidence)}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="grid gap-3 min-[760px]:grid-cols-3">
            <InfoCard title="Seçili hedef" value={selectedTrack ? selectedTrack.trackId : 'Yok'} detail={selectedTrack ? `${targetLabel[selectedTrack.targetType]} · ${selectedTrack.friendFoe} · ${selectedTrack.rangeM.toFixed(1)} m` : 'FireIntent kapalı'} />
            <InfoCard title="Safety açıklaması" value={safety.blockReason} detail={safety.explanation} />
            <InfoCard title="Son niyet" value={lastManualAim?.kind ?? lastIntent?.kind ?? 'Henüz yok'} detail={lastManualAim ? `pan=${lastManualAim.panDeltaDeg}° · tilt=${lastManualAim.tiltDeltaDeg}° · deadman=${String(lastManualAim.deadmanActive)}` : lastIntent ? `${lastIntent.targetId} · dryRun=${String(lastIntent.dryRun)}` : 'Komut gönderilmedi'} />
          </section>

          <section className="rounded-xl border border-[#25d8ff]/18 bg-[rgba(7,10,14,.94)] p-4" data-testid="operator-target-detail" aria-label="Seçili hedef ve adapter ayrıntısı">
            <div className="grid gap-3 min-[760px]:grid-cols-[1fr_1fr]">
              <div>
                <p className="m-0 text-xs font-black uppercase tracking-[.14em] text-[#25d8ff]">Seçili iz ayrıntısı</p>
                <h2 className="m-0 mt-1 text-xl font-black text-white">{selectedTrack ? targetLabel[selectedTrack.targetType] : 'Hedef seçilmedi'}</h2>
                <div className="mt-3 grid gap-2 text-sm">
                  <EvidenceRow label="Track ID" value={selectedTrack?.trackId ?? 'Yok'} />
                  <EvidenceRow label="Dost/Düşman · Kaynak" value={selectedTrack ? `${selectedTrack.friendFoe} · ${selectedTrack.source}` : 'Yok'} />
                  <EvidenceRow label="Menzil · Açı · Güven" value={selectedTrack ? `${selectedTrack.rangeM.toFixed(1)} m · ${selectedTrack.bearingDeg.toFixed(1)}° · ${formatPercent(selectedTrack.confidence)}` : 'Yok'} />
                  <EvidenceRow label="Son güncelleme" value={selectedTrack?.updatedAt ?? 'Yok'} />
                </div>
              </div>
              <div>
                <p className="m-0 text-xs font-black uppercase tracking-[.14em] text-[#ffbb42]">Adapter sınırı</p>
                <h2 className="m-0 mt-1 text-xl font-black text-white">Dry-run sözleşme görünümü</h2>
                <ul className="mt-3 grid gap-2 pl-5 text-sm leading-relaxed text-[#c8d8e2]">
                  <li>`TrackState` görüntülenir; gerçek perception adapter henüz TBD.</li>
                  <li>`SensorFrame`/Radar-LiDAR ölçümü için donanım protokolü henüz TBD.</li>
                  <li>`ManualAimCommand` ve `FireIntent` backend Safety Gate’e gider; UI doğrudan motor/imha hattı sürmez.</li>
                </ul>
              </div>
            </div>
          </section>
        </div>

        <aside className="grid gap-3 content-start">
          <section className="rounded-xl border border-[#25d8ff]/18 bg-[rgba(7,10,14,.94)] p-4" aria-label="Komut paneli">
            <p className="m-0 text-xs font-black uppercase tracking-[.16em] text-[#25d8ff]">Komut paneli</p>
            <h2 className="m-0 mt-1 text-2xl font-black">Backend’e niyet gönder</h2>
            <p className="mt-2 text-sm leading-relaxed text-[#b7c9d5]">Bu geçişte butonlar yalnız yüksek seviye mesaj modeli üretir. Gerçek sistemde backend Safety Gate onayı olmadan Hardware Adapter çağrılmaz.</p>
            <div className="mt-4 grid grid-cols-2 gap-2">
              {(['safe', 'manual', 'autonomous', 'maintenance'] as const).map((item) => (
                <button key={item} className={`rounded-lg border px-3 py-2 text-sm font-black ${mode === item ? 'border-[#33e68c]/40 bg-[#33e68c]/14 text-[#ccffe2]' : 'border-white/10 bg-white/[.06] text-[#c8d8e2]'}`} onClick={() => recordMode(item)}>
                  {item === 'safe' ? 'Safe' : item === 'manual' ? 'Manuel' : item === 'autonomous' ? 'Otonom' : 'Bakım'}
                </button>
              ))}
            </div>
            <section className="mt-4 rounded-xl border border-white/[.08] bg-black/20 p-3" data-testid="manual-aim-controls" aria-label="Manuel yönlendirme kontrolleri">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <b className="text-sm text-white">Manuel pan/tilt yönlendirme</b>
                  <p className="m-0 mt-1 text-xs font-bold text-[#91a6b7]">WP-01 için `ManualAimCommand`; manuel mod + deadman olmadan kilitli.</p>
                </div>
                <button
                  className={`rounded-lg border px-3 py-2 text-xs font-black ${deadmanActive ? 'border-[#33e68c]/35 bg-[#33e68c]/14 text-[#ccffe2]' : 'border-[#ffbb42]/30 bg-[#ffbb42]/10 text-[#ffe4ad]'}`}
                  onClick={() => setDeadmanActive((value) => !value)}
                >
                  {deadmanActive ? 'DEADMAN AKTİF' : 'DEADMAN PASİF'}
                </button>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2">
                <button className="rounded-lg border border-white/10 bg-white/[.06] px-2 py-2 text-xs font-black text-[#c8d8e2] disabled:opacity-45" disabled={!manualAimReady || apiBusy} onClick={() => sendManualAim(0, MANUAL_AIM_STEP_DEG)}>YUKARI {MANUAL_AIM_STEP_DEG}°</button>
                <button className="rounded-lg border border-white/10 bg-white/[.06] px-2 py-2 text-xs font-black text-[#c8d8e2] disabled:opacity-45" disabled={!manualAimReady || apiBusy} onClick={() => sendManualAim(0, 0)}>DUR / 0°</button>
                <button className="rounded-lg border border-white/10 bg-white/[.06] px-2 py-2 text-xs font-black text-[#c8d8e2] disabled:opacity-45" disabled={!manualAimReady || apiBusy} onClick={() => sendManualAim(0, -MANUAL_AIM_STEP_DEG)}>AŞAĞI {MANUAL_AIM_STEP_DEG}°</button>
                <button className="rounded-lg border border-white/10 bg-white/[.06] px-2 py-2 text-xs font-black text-[#c8d8e2] disabled:opacity-45" disabled={!manualAimReady || apiBusy} onClick={() => sendManualAim(-MANUAL_AIM_STEP_DEG, 0)}>SOLA {MANUAL_AIM_STEP_DEG}°</button>
                <button className="rounded-lg border border-white/10 bg-white/[.06] px-2 py-2 text-xs font-black text-[#c8d8e2] disabled:opacity-45" disabled={!manualAimReady || apiBusy} onClick={() => sendManualAim(MANUAL_AIM_STEP_DEG, 0)}>SAĞA {MANUAL_AIM_STEP_DEG}°</button>
                <button className="rounded-lg border border-white/10 bg-white/[.06] px-2 py-2 text-xs font-black text-[#c8d8e2] disabled:opacity-45" disabled={!manualAimReady || apiBusy} onClick={() => sendManualAim(MANUAL_AIM_STEP_DEG, -MANUAL_AIM_STEP_DEG)}>SAĞ/AŞAĞI</button>
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-bold text-[#c8d8e2]">
                <span className="rounded-full border border-[#48a8ff]/25 bg-[#48a8ff]/10 px-2 py-1 text-[#cbe9ff]">Hız limiti: {manualAimRate}°/s</span>
                <button className="rounded-full border border-white/10 bg-white/[.06] px-2 py-1 text-[#c8d8e2]" onClick={() => setManualAimRate(6)}>Yavaş 6°/s</button>
                <button className="rounded-full border border-white/10 bg-white/[.06] px-2 py-1 text-[#c8d8e2]" onClick={() => setManualAimRate(MANUAL_AIM_RATE_LIMIT_DEG_PER_SEC)}>Standart {MANUAL_AIM_RATE_LIMIT_DEG_PER_SEC}°/s</button>
              </div>
              <p className="m-0 mt-2 text-sm font-bold text-[#ffe4ad]">{manualAimReady ? 'Manuel yönlendirme dry-run komutu gönderilebilir; fiziksel pan/tilt çıkışı yok.' : operatorBlockCopy[manualAimBlockReason]}</p>
            </section>
            <button
              className={`mt-4 min-h-16 w-full rounded-xl px-4 text-lg font-black ${fireReady ? 'bg-[#ff3146] text-white shadow-[0_18px_42px_rgba(255,71,87,.28)]' : 'bg-white/[.08] text-[#91a6b7]'}`}
              disabled={!fireReady}
              onClick={sendFireIntent}
            >
              {fireReady ? 'FIRE INTENT GÖNDER (DRY-RUN)' : 'FIRE INTENT KİLİTLİ'}
            </button>
            <p className="m-0 mt-2 text-sm font-bold text-[#ffe4ad]">{fireReady ? 'Puan veya fiziksel çıkış yok; yalnız CommandResult loglanır.' : operatorBlockCopy[safety.blockReason]}</p>
            <div className="mt-4 rounded-xl border border-[#33e68c]/18 bg-[#33e68c]/[.06] p-3" data-testid="operator-hardware-result">
              <b className="text-sm text-[#bfffe0]">Son hardware/mock sonucu</b>
              <p className="m-0 mt-1 text-sm text-[#c8d8e2]">{lastHardwareResult ? `${lastHardwareResult.kind} · ${lastHardwareResult.adapter} · physicalOutput=${String(lastHardwareResult.physicalOutput)}` : 'Henüz hardware adapter sonucu yok; backend kabul ederse dry-run sonuç burada görünür.'}</p>
              {lastHardwareResult && <p className="m-0 mt-1 text-xs font-bold text-[#91a6b7]">{lastHardwareResult.message}</p>}
            </div>
          </section>

          <section className="rounded-xl border border-[#ffbb42]/18 bg-[rgba(10,8,4,.88)] p-4" aria-label="Güvenlik ilkeleri">
            <h2 className="m-0 text-xl font-black text-[#ffe4ad]">Güvenlik sınırı</h2>
            <ul className="mt-3 grid gap-2 pl-5 text-sm leading-relaxed text-[#f4e4bf]">
              <li>UI doğrudan ateşleme/imha hattını enerjilendirmez.</li>
              <li>Acil Durdur ve yasak alan kontrolleri backend/hardware katmanında uygulanır.</li>
              <li>Canlı kullanım için radar/LiDAR, perception ve MCU adapter kararları ayrıca bağlanmalıdır.</li>
            </ul>
            <div className="mt-3 grid gap-2 text-sm" data-testid="operator-safety-state">
              <EvidenceRow label="Acil Durdur" value={safety.estop ? 'AKTİF · komutlar kilitli' : 'Pasif / backend state güvenli'} />
              <EvidenceRow label="Hareket alanı" value={safety.motionZoneOk ? 'Uygun' : 'Yasak alan · hareket kilitli'} />
              <EvidenceRow label="Atış alanı" value={safety.fireZoneOk ? 'Uygun' : 'Yasak alan · FireIntent kilitli'} />
              <EvidenceRow label="Hedef kapısı" value={safety.targetGateOk ? 'Düşman + menzil uygun' : 'Dost, bilinmeyen veya menzil dışı'} />
              <EvidenceRow label="Mod kapısı" value={safety.modeOk ? 'Komuta uygun' : 'Safe/Bakım/Kilitli mod'} />
              <EvidenceRow label="Backend bağlantısı" value={safety.backendConnected ? 'State alınıyor veya yerel dry-run' : 'Bağlantı yok'} />
            </div>
          </section>

          <details className="rounded-xl border border-[#ffbb42]/18 bg-[rgba(10,8,4,.88)] p-4" data-testid="operator-maintenance-drawer">
            <summary className="cursor-pointer list-none text-xl font-black text-[#ffe4ad]">
              Bakım / Adapter TBD
              <span className="ml-2 rounded-full border border-[#ffbb42]/25 bg-[#ffbb42]/10 px-2 py-1 align-middle text-xs text-[#ffe4ad]">Mekanik + Elektronik rehberi bekliyor</span>
            </summary>
            <p className="mt-3 text-sm leading-relaxed text-[#f4e4bf]">
              Operatör panelinin yazılım yüzeyi tamamlandı; aşağıdaki satırlar gerçek donanım seçimine bağlı olduğu için bilinçli olarak TBD veya kilitli tutulur.
            </p>
            <div className="mt-3 grid gap-2">
              <AdapterRow
                label="Perception Adapter"
                item={readinessById.perception_adapter}
                fallback="Kamera/model çıktısı TrackState sözleşmesine bağlanacak; canlı sınıflandırma adapterı TBD."
              />
              <AdapterRow
                label="Radar/LiDAR Adapter"
                item={readinessById.radar_lidar_adapter}
                fallback="Menzil/açı/kalite protokolü seçilen sensöre göre TBD."
              />
              <AdapterRow
                label="MCU / Hardware Protocol"
                item={readinessById.hardware_adapter}
                fallback="UART/RS422/CAN/Ethernet ve mesaj çerçevesi elektronik ekibiyle netleşecek."
              />
              <AdapterRow
                label="Canlı Arming / Interlock"
                item={readinessById.live_arming}
                fallback="İki aşamalı arming, hakem/operatör kilidi ve fiziksel interlock tamamlanmadan kapalı."
              />
            </div>
            <div className="mt-3 grid gap-2 text-sm">
              <EvidenceRow label="API base" value={config.apiBaseUrl} />
              <EvidenceRow label="Komut endpointleri" value="POST /mode · POST /manual-aim · POST /fire-intent" />
              <EvidenceRow label="Kanıt endpointleri" value="GET /readiness · GET /telemetry/export · GET /replay" />
              <EvidenceRow label="Canlı çıkış" value={config.liveArmEnabled ? 'Arming env açık olsa bile backend interlock zorunlu' : 'Kilitli / TBD'} />
            </div>
          </details>

          <section className="rounded-xl border border-white/[.08] bg-[rgba(7,10,14,.94)] p-4" aria-label="Olay akışı">
            <h2 className="m-0 text-xl font-black">Olay akışı</h2>
            <div className="mt-3 grid gap-2">
              {commandResults.length === 0 && <p className="m-0 rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-sm text-[#91a6b7]">Henüz komut sonucu yok.</p>}
              {commandResults.map((result) => (
                <article key={result.commandId} className="rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-sm">
                  <b className={result.accepted ? 'text-[#bfffe0]' : 'text-[#ffbdc4]'}>{commandLabel(result)} · {result.accepted ? 'Kabul' : 'Blok'}</b>
                  <p className="m-0 mt-1 text-[#c8d8e2]">{result.message}</p>
                  <small className="mt-1 block text-[#91a6b7]">{result.createdAt}</small>
                </article>
              ))}
            </div>
          </section>

          <details className="rounded-xl border border-[#48a8ff]/18 bg-[rgba(7,10,14,.94)] p-4" data-testid="operator-evidence-drawer">
            <summary className="cursor-pointer list-none text-xl font-black text-[#d7efff]">
              Kanıt / Replay
              <span className="ml-2 rounded-full border border-[#48a8ff]/25 bg-[#48a8ff]/10 px-2 py-1 align-middle text-xs text-[#bfe7ff]">Gelişmiş</span>
            </summary>
            <p className="mt-3 text-sm leading-relaxed text-[#b7c9d5]">
              Bu çekmece KTR/debug kanıtı içindir. Export ve replay sadece dry-run JSONL kayıtlarını okur; replay hardware adapter çağırmaz.
            </p>
            <div className="mt-3 grid grid-cols-2 gap-2">
              <button className="rounded-lg border border-[#48a8ff]/30 bg-[#48a8ff]/10 px-3 py-2 text-sm font-black text-[#cbe9ff] disabled:cursor-not-allowed disabled:opacity-45" disabled={!apiBaseUrl || evidenceBusy} onClick={refreshTelemetryEvidence}>
                {evidenceBusy ? 'Kanıt alınıyor' : 'Kanıtı Yenile'}
              </button>
              <button className="rounded-lg border border-[#ffbb42]/30 bg-[#ffbb42]/10 px-3 py-2 text-sm font-black text-[#ffe4ad] disabled:cursor-not-allowed disabled:opacity-45" disabled={!apiBaseUrl || evidenceBusy} onClick={resetTelemetryEvidence}>
                Telemetriyi Sıfırla
              </button>
            </div>
            {!apiBaseUrl && <p className="m-0 mt-3 rounded-lg border border-[#ffbb42]/25 bg-[#ffbb42]/10 p-3 text-sm font-bold text-[#ffe4ad]">Backend API yok: panel yerel dry-run modunda. Export/replay için `operatorApi` veya VITE_GOKKALKAN_OPERATOR_API_BASE gerekir.</p>}
            {evidenceError && <p className="m-0 mt-3 rounded-lg border border-[#ff4757]/25 bg-[#ff4757]/10 p-3 text-sm font-bold text-[#ffbdc4]">{evidenceError}</p>}
            {evidenceNotice && !evidenceError && <p className="m-0 mt-3 rounded-lg border border-[#33e68c]/25 bg-[#33e68c]/10 p-3 text-sm font-bold text-[#bfffe0]">{evidenceNotice}</p>}
            <div className="mt-3 grid gap-2 text-sm">
              <EvidenceRow label="JSONL kayıt yolu" value={telemetryMetadata?.path ?? 'Henüz backend kanıtı alınmadı'} />
              <EvidenceRow label="Kayıt sayısı" value={String(telemetryMetadata?.recordCount ?? evidenceEntries.length)} />
              <EvidenceRow label="Replay özeti" value={`${replayEventCount} olay · ${replayCommandCount} komut · ${replayHardwareCount} dry-run hardware sonucu`} />
              <EvidenceRow label="Fiziksel çıkış" value={(telemetryExport?.physicalOutputEnabled ?? replayBundle?.physicalOutputEnabled ?? apiSnapshot?.physicalOutputEnabled) ? 'AÇIK' : 'KAPALI / YOK'} />
            </div>
            <div className="mt-3 grid max-h-64 gap-2 overflow-auto pr-1" aria-label="Replay kayıtları">
              {evidenceEntries.length === 0 && <p className="m-0 rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-sm text-[#91a6b7]">Henüz export/replay kaydı alınmadı.</p>}
              {evidenceEntries.slice(0, 8).map((record, index) => (
                <article key={`${record.recordId ?? index}-${record.timestamp ?? 'no-time'}`} className="rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-xs">
                  <b className="text-[#d7efff]">{record.recordType}</b>
                  <small className="ml-2 text-[#91a6b7]">{record.timestamp ?? 'timestamp yok'}</small>
                  <p className="m-0 mt-1 break-words text-[#c8d8e2]">{shortRecordPayload(record)}</p>
                </article>
              ))}
            </div>
          </details>
        </aside>
      </section>
    </main>
  );
}

function EvidenceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-white/[.07] bg-white/[.04] p-3">
      <span className="block text-xs font-black uppercase tracking-[.12em] text-[#91a6b7]">{label}</span>
      <b className="mt-1 block break-words text-[#eaf7ff]">{value}</b>
    </div>
  );
}

function ReadinessCard({ item }: { item: OperatorReadinessItem }) {
  return (
    <article className="rounded-lg border border-white/[.07] bg-white/[.04] p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <b className="text-sm text-white">{item.label}</b>
        <span className={`rounded-full border px-2 py-1 text-[11px] font-black uppercase tracking-[.08em] ${readinessTone(item.status)}`}>
          {readinessCopy[item.status]}
        </span>
      </div>
      <p className="m-0 mt-2 text-xs font-bold uppercase tracking-[.12em] text-[#91a6b7]">{item.owner} · {item.ktrInterface}</p>
      <p className="m-0 mt-2 text-sm leading-snug text-[#c8d8e2]">{item.evidence}</p>
      <p className="m-0 mt-2 text-xs leading-snug text-[#ffe4ad]">Sonraki: {item.nextStep}</p>
    </article>
  );
}

function AdapterRow({ label, item, fallback }: { label: string; item: OperatorReadinessItem | undefined; fallback: string }) {
  const status = item?.status ?? 'tbd';
  return (
    <article className="rounded-lg border border-white/[.07] bg-white/[.04] p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <b className="text-white">{label}</b>
        <span className={`rounded-full border px-2 py-1 text-[11px] font-black uppercase tracking-[.08em] ${readinessTone(status)}`}>
          {readinessCopy[status]}
        </span>
      </div>
      <p className="m-0 mt-2 text-[#c8d8e2]">{item?.evidence ?? fallback}</p>
      <p className="m-0 mt-1 text-xs font-bold text-[#ffe4ad]">Sonraki: {item?.nextStep ?? fallback}</p>
    </article>
  );
}

function InfoCard({ title, value, detail }: { title: string; value: string; detail: string }) {
  return (
    <section className="min-w-0 rounded-xl border border-white/[.08] bg-[rgba(7,10,14,.94)] p-4">
      <p className="m-0 text-xs font-black uppercase tracking-[.14em] text-[#91a6b7]">{title}</p>
      <b className="mt-1 block overflow-hidden text-ellipsis whitespace-nowrap text-lg text-white">{value}</b>
      <p className="m-0 mt-1 text-sm leading-snug text-[#b7c9d5]">{detail}</p>
    </section>
  );
}
