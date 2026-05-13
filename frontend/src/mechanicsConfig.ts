const env = import.meta.env;

function numberFromEnv(key: string, fallback: number, min?: number, max?: number): number {
  const raw = env[key];
  const parsed = typeof raw === 'string' && raw.trim() !== '' ? Number(raw) : fallback;
  const finite = Number.isFinite(parsed) ? parsed : fallback;
  const aboveMin = min === undefined ? finite : Math.max(min, finite);
  return max === undefined ? aboveMin : Math.min(max, aboveMin);
}

function booleanFromEnv(key: string, fallback: boolean): boolean {
  const raw = env[key];
  if (typeof raw !== 'string') return fallback;
  if (['1', 'true', 'yes', 'on'].includes(raw.toLowerCase())) return true;
  if (['0', 'false', 'no', 'off'].includes(raw.toLowerCase())) return false;
  return fallback;
}

export const mechanicsConfig = {
  panMinDeg: numberFromEnv('VITE_GOKKALKAN_PAN_MIN_DEG', -75, -180, 180),
  panMaxDeg: numberFromEnv('VITE_GOKKALKAN_PAN_MAX_DEG', 75, -180, 180),
  tiltMinDeg: numberFromEnv('VITE_GOKKALKAN_TILT_MIN_DEG', -10, -90, 90),
  tiltMaxDeg: numberFromEnv('VITE_GOKKALKAN_TILT_MAX_DEG', 45, -90, 90),
  coarseStepDeg: numberFromEnv('VITE_GOKKALKAN_COARSE_STEP_DEG', 2, 0.1, 30),
  fineStepDeg: numberFromEnv('VITE_GOKKALKAN_FINE_STEP_DEG', 0.5, 0.1, 10),
  armHoldMs: numberFromEnv('VITE_GOKKALKAN_ARM_HOLD_MS', 500, 0, 5_000),
  armTimeoutMs: numberFromEnv('VITE_GOKKALKAN_ARM_TIMEOUT_MS', 2_500, 250, 30_000),
  prepSeconds: numberFromEnv('VITE_GOKKALKAN_PREP_SECONDS', 1_800, 0, 7_200),
  maintenanceBudgetSeconds: numberFromEnv('VITE_GOKKALKAN_MAINTENANCE_BUDGET_SECONDS', 600, 0, 3_600),
  maintenanceMinimumSeconds: numberFromEnv('VITE_GOKKALKAN_MAINTENANCE_MIN_SECONDS', 30, 0, 600),
  mockConnectionOk: booleanFromEnv('VITE_GOKKALKAN_MOCK_CONNECTION_OK', true),
  motionForbiddenLabel: env.VITE_GOKKALKAN_MOTION_FORBIDDEN_LABEL || 'arka ±105°',
  fireForbiddenLabel: env.VITE_GOKKALKAN_FIRE_FORBIDDEN_LABEL || 'seyirci ROI',
};

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

export function clampPan(value: number): number {
  return clamp(value, mechanicsConfig.panMinDeg, mechanicsConfig.panMaxDeg);
}

export function clampTilt(value: number): number {
  return clamp(value, mechanicsConfig.tiltMinDeg, mechanicsConfig.tiltMaxDeg);
}

export function signedDegrees(value: number): string {
  return `${value >= 0 ? '+' : ''}${value.toFixed(1)}°`;
}
