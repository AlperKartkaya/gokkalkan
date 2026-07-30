import type { EventType, Stage, TargetType, TelemetryEvent } from './types';

export const TARGET_ORDER: TargetType[] = ['Balistik Füze', 'Helikopter', 'F16', 'Mini/Micro İHA'];

export interface StageConfig {
  stage: Stage;
  title: string;
  modeExpectation: 'Manuel Mod' | 'Otonom Mod';
  summary: string;
  threshold: number;
  rounds?: number;
  durationSeconds?: number;
  classificationRequired: boolean;
}

export const STAGE_CONFIGS: Record<Stage, StageConfig> = {
  1: {
    stage: 1,
    title: 'Farklı Menzillerde Duran Hedef İmhası',
    modeExpectation: 'Manuel Mod',
    summary: 'Manuel · 5 dk · hedef sırası · ≥20 puan',
    threshold: 20,
    durationSeconds: 300,
    classificationRequired: false,
  },
  2: {
    stage: 2,
    title: 'Sürü Saldırısı ve Hedeflerin İmhası',
    modeExpectation: 'Otonom Mod',
    summary: 'Otonom · 4 tur · sınıflandırma beklenmez · ≥20 puan',
    threshold: 20,
    rounds: 4,
    classificationRequired: false,
  },
  3: {
    stage: 3,
    title: 'Farklı Katmanlardaki Hareketli Hedeflerin İmhası',
    modeExpectation: 'Otonom Mod',
    summary: 'Otonom · 8 tur · dost/düşman + menzil · ≥10 puan',
    threshold: 10,
    rounds: 8,
    classificationRequired: true,
  },
};

export interface RangeRule {
  min: number;
  max: number;
  label: string;
}

export const RANGE_RULES: Record<TargetType, RangeRule> = {
  F16: { min: 10, max: 15, label: '10-15 m' },
  Helikopter: { min: 5, max: 15, label: '5-15 m' },
  'Balistik Füze': { min: 5, max: 15, label: '5-15 m' },
  'Mini/Micro İHA': { min: 0, max: 15, label: '0-15 m' },
};

export function rangeRuleFor(type: TargetType): RangeRule {
  return RANGE_RULES[type];
}

export function stageConfigFor(stage: Stage): StageConfig {
  return STAGE_CONFIGS[stage];
}

export function maxRoundFor(stage: Stage): number {
  return STAGE_CONFIGS[stage].rounds ?? 1;
}

export function thresholdFor(stage: Stage): number {
  return STAGE_CONFIGS[stage].threshold;
}

export interface VideoEvidenceStep {
  id: `Y${number}`;
  label: string;
  description: string;
  match: (event: TelemetryEvent) => boolean;
}

export const VIDEO_EVIDENCE_STEPS: VideoEvidenceStep[] = [
  {
    id: 'Y1',
    label: 'Kullanıcı komut arayüzleri',
    description: 'UI/joystick/klavye fonksiyonları',
    match: (event) => event.type === 'command' && (event.decision.startsWith('MOVE_') || event.decision.startsWith('ARM_')),
  },
  {
    id: 'Y2',
    label: '15 m durağan hedef imhası',
    description: '15 m balon atışı',
    match: (event) => event.decision === 'FIRE_MOCK' && event.reason.includes('15.0 m'),
  },
  {
    id: 'Y3',
    label: 'Hareket sırasında Acil Durdur',
    description: 'Hareket kesme kanıtı',
    match: (event) => event.decision === 'ESTOP_ON' && event.reason.includes('hareket'),
  },
  {
    id: 'Y4',
    label: 'Ateş sırasında Acil Durdur',
    description: 'Ateş kesme kanıtı',
    match: (event) => event.decision === 'ESTOP_ON' && event.reason.includes('atış'),
  },
  {
    id: 'Y5',
    label: 'Yan/yükseliş ekseninde takip',
    description: 'Yaw/elev hareketli hedef takibi',
    match: (event) => event.decision === 'OTONOM_START' || event.decision === 'AUTO_ENGAGE',
  },
  {
    id: 'Y6',
    label: '5/10/15 m sınıflandırma',
    description: 'Zorunlu hedef tipi kanıtı',
    match: (event) => event.stage === 3 && event.type === 'target',
  },
  {
    id: 'Y7',
    label: 'Dost/düşman otonom gösterimi',
    description: 'Opsiyonel kırmızı düşman ve mavi dost koruma kanıtı',
    match: (event) => event.stage === 3 && event.decision === 'AUTO_ENGAGE',
  },
];

export const EVENT_FILTERS: EventType[] = ['command', 'target', 'safety', 'fire', 'mode', 'telemetry'];
