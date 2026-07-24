#!/usr/bin/env node
import { existsSync, mkdirSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawn } from 'node:child_process';

const scriptPath = fileURLToPath(import.meta.url);
const frontendDir = resolve(dirname(scriptPath), '..');
const repoRoot = resolve(frontendDir, '..');
const viteBin = join(frontendDir, 'node_modules', 'vite', 'bin', 'vite.js');
const telemetryDir = join(repoRoot, 'telemetry_data');
const defaultProfileDir = join(repoRoot, '.omx', 'browser-profiles', 'operator-desktop');

export function parseDesktopArgs(argv = process.argv.slice(2), env = process.env) {
  const parsed = {
    mode: env.GOKKALKAN_DESKTOP_MODE || 'dev',
    host: env.GOKKALKAN_DESKTOP_HOST || '127.0.0.1',
    apiHost: env.GOKKALKAN_DESKTOP_API_HOST || env.GOKKALKAN_DESKTOP_HOST || '127.0.0.1',
    uiPort: env.GOKKALKAN_DESKTOP_UI_PORT ? Number(env.GOKKALKAN_DESKTOP_UI_PORT) : undefined,
    apiPort: env.GOKKALKAN_DESKTOP_API_PORT ? Number(env.GOKKALKAN_DESKTOP_API_PORT) : 8088,
    timeoutMs: env.GOKKALKAN_DESKTOP_TIMEOUT_MS ? Number(env.GOKKALKAN_DESKTOP_TIMEOUT_MS) : 20_000,
    noBrowser: env.GOKKALKAN_DESKTOP_NO_BROWSER === '1',
    smoke: false,
    browser: env.GOKKALKAN_DESKTOP_BROWSER || '',
    help: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = () => argv[++index] ?? '';
    if (arg === '--mode') parsed.mode = next();
    else if (arg === '--host') parsed.host = next();
    else if (arg === '--api-host') parsed.apiHost = next();
    else if (arg === '--ui-port') parsed.uiPort = Number(next());
    else if (arg === '--api-port') parsed.apiPort = Number(next());
    else if (arg === '--timeout-ms') parsed.timeoutMs = Number(next());
    else if (arg === '--browser') parsed.browser = next();
    else if (arg === '--no-browser') parsed.noBrowser = true;
    else if (arg === '--smoke') parsed.smoke = true;
    else if (arg === '--help' || arg === '-h') parsed.help = true;
    else throw new Error(`Unknown desktop launcher argument: ${arg}`);
  }

  if (!['dev', 'preview'].includes(parsed.mode)) throw new Error('--mode must be dev or preview');
  if (!parsed.uiPort) parsed.uiPort = parsed.mode === 'preview' ? 4173 : 5173;
  for (const [name, value] of [['ui-port', parsed.uiPort], ['api-port', parsed.apiPort], ['timeout-ms', parsed.timeoutMs]]) {
    if (!Number.isFinite(value) || value <= 0) throw new Error(`--${name} must be a positive number`);
  }
  return parsed;
}

export function buildOperatorUrl({ uiBaseUrl, apiBaseUrl, desktop = true }) {
  const url = new URL('/', uiBaseUrl);
  url.searchParams.set('operator', '1');
  url.searchParams.set('operatorApi', apiBaseUrl);
  if (desktop) url.searchParams.set('desktop', '1');
  return url.toString();
}

export function pythonCandidates(platform = process.platform, env = process.env) {
  if (env.GOKKALKAN_PYTHON) return [{ command: env.GOKKALKAN_PYTHON, args: [] }];
  if (platform === 'win32') {
    return [
      { command: 'py', args: ['-3'] },
      { command: 'python', args: [] },
      { command: 'python3', args: [] },
    ];
  }
  return [
    { command: 'python3', args: [] },
    { command: 'python', args: [] },
  ];
}

export function browserCommandCandidates({ platform = process.platform, env = process.env, exists = existsSync, url, profileDir = defaultProfileDir, explicitBrowser = '' }) {
  const appArgs = [`--app=${url}`, `--user-data-dir=${profileDir}`, '--no-first-run'];
  if (explicitBrowser) return [{ command: explicitBrowser, args: appArgs, label: 'custom browser' }];
  if (env.BROWSER) return [{ command: env.BROWSER, args: appArgs, label: 'BROWSER env' }];

  if (platform === 'darwin') {
    return [
      { command: 'open', args: ['-na', 'Google Chrome', '--args', ...appArgs], label: 'Google Chrome app window' },
      { command: 'open', args: ['-na', 'Microsoft Edge', '--args', ...appArgs], label: 'Microsoft Edge app window' },
      { command: 'open', args: ['-na', 'Chromium', '--args', ...appArgs], label: 'Chromium app window' },
      { command: 'open', args: [url], label: 'default browser fallback' },
    ];
  }

  if (platform === 'win32') {
    const local = env.LOCALAPPDATA || '';
    const programFiles = env.PROGRAMFILES || 'C:\\Program Files';
    const programFilesX86 = env['PROGRAMFILES(X86)'] || 'C:\\Program Files (x86)';
    const browserPaths = [
      join(local, 'Google', 'Chrome', 'Application', 'chrome.exe'),
      join(programFiles, 'Google', 'Chrome', 'Application', 'chrome.exe'),
      join(programFilesX86, 'Google', 'Chrome', 'Application', 'chrome.exe'),
      join(programFiles, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
      join(programFilesX86, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    ].filter((candidate) => candidate && exists(candidate));
    return [
      ...browserPaths.map((command) => ({ command, args: appArgs, label: 'installed Chromium app window' })),
      { command: 'cmd', args: ['/c', 'start', '""', 'msedge', ...appArgs], label: 'Edge app window fallback' },
      { command: 'cmd', args: ['/c', 'start', '""', url], label: 'default browser fallback' },
    ];
  }

  return [
    { command: 'google-chrome', args: appArgs, label: 'Google Chrome app window' },
    { command: 'google-chrome-stable', args: appArgs, label: 'Google Chrome Stable app window' },
    { command: 'chromium', args: appArgs, label: 'Chromium app window' },
    { command: 'chromium-browser', args: appArgs, label: 'Chromium Browser app window' },
    { command: 'microsoft-edge', args: appArgs, label: 'Microsoft Edge app window' },
    { command: 'brave-browser', args: appArgs, label: 'Brave app window' },
    { command: 'xdg-open', args: [url], label: 'default browser fallback' },
  ];
}

function printHelp() {
  console.log(`Gökkalkan desktop launcher\n\nUsage:\n  npm run desktop -- [options]\n  npm run desktop:preview\n  npm run desktop:check\n\nOptions:\n  --mode dev|preview      Start Vite dev server or built preview server\n  --host 127.0.0.1        UI bind host\n  --api-host 127.0.0.1    Backend API bind host\n  --ui-port 5173          UI port\n  --api-port 8088         Dry-run backend API port\n  --browser <path>        Explicit Chromium/Chrome/Edge executable\n  --no-browser            Start services without opening an app window\n  --smoke                 Verify services and exit cleanly\n  --timeout-ms <ms>       Startup wait timeout\n\nEnvironment:\n  GOKKALKAN_PYTHON, GOKKALKAN_DESKTOP_BROWSER, GOKKALKAN_DESKTOP_*\n`);
}

function spawnWithInheritedOutput(command, args, options = {}) {
  return spawn(command, args, { stdio: 'inherit', ...options });
}

async function spawnFirstAvailable(candidates, trailingArgs, options, label) {
  let lastError;
  for (const candidate of candidates) {
    const args = [...candidate.args, ...trailingArgs];
    try {
      const child = spawnWithInheritedOutput(candidate.command, args, options);
      await new Promise((resolve, reject) => {
        child.once('spawn', resolve);
        child.once('error', reject);
      });
      return { child, command: candidate.command, args };
    } catch (error) {
      lastError = error;
      if (error?.code !== 'ENOENT') throw error;
    }
  }
  throw new Error(`${label} could not be started. Last error: ${lastError?.message ?? 'unknown'}`);
}

function startVite({ mode, host, uiPort }) {
  const args = mode === 'preview'
    ? [viteBin, 'preview', '--host', host, '--port', String(uiPort), '--strictPort']
    : [viteBin, '--host', host, '--port', String(uiPort), '--strictPort'];
  return spawnWithInheritedOutput(process.execPath, args, { cwd: frontendDir, env: process.env });
}

function startBackend({ apiHost, apiPort }) {
  mkdirSync(telemetryDir, { recursive: true });
  const telemetryPath = join(telemetryDir, 'operator-api-desktop-dry-run.jsonl');
  const configPath = join(repoRoot, 'config', 'runtime', 'sim.toml');
  const venvPython = process.platform === 'win32'
    ? join(repoRoot, '.venv', 'Scripts', 'python.exe')
    : join(repoRoot, '.venv', 'bin', 'python');
  const candidates = [
    ...(existsSync(venvPython) ? [{ command: venvPython, args: [] }] : []),
    ...pythonCandidates(process.platform, process.env),
  ];
  const args = [
    '-m', 'gokkalkan_backend.operator_http_server',
    '--config', configPath,
    '--host', apiHost,
    '--port', String(apiPort),
    '--telemetry-jsonl', telemetryPath,
  ];
  return spawnFirstAvailable(candidates, args, { cwd: repoRoot, env: process.env }, 'Python backend');
}

export async function waitForHttp(url, { timeoutMs = 20_000, label = url } = {}) {
  const startedAt = Date.now();
  let lastError = '';
  while (Date.now() - startedAt < timeoutMs) {
    try {
      const response = await fetch(url, { cache: 'no-store' });
      if (response.ok) return response;
      lastError = `HTTP ${response.status}`;
    } catch (error) {
      lastError = error instanceof Error ? error.message : String(error);
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`${label} did not become ready within ${timeoutMs}ms (${lastError})`);
}

export async function assertSafeBackendHealth(response) {
  const health = await response.json();
  if (health.runtimeMode !== 'SIM' || health.physicalOutputEnabled !== false) {
    throw new Error(`Unsafe desktop backend health: ${JSON.stringify(health)}`);
  }
  return health;
}

async function launchBrowserApp(url, options) {
  if (options.noBrowser) {
    console.log(`[desktop] Browser launch skipped: ${url}`);
    return undefined;
  }
  mkdirSync(defaultProfileDir, { recursive: true });
  const candidates = browserCommandCandidates({ url, explicitBrowser: options.browser });
  let lastError;
  for (const candidate of candidates) {
    try {
      const child = spawn(candidate.command, candidate.args, { detached: true, stdio: 'ignore' });
      await waitForBrowserLaunch(candidate, child);
      child.unref();
      console.log(`[desktop] Opened ${candidate.label}: ${url}`);
      return child;
    } catch (error) {
      lastError = error;
      if (error?.code !== 'ENOENT') console.warn(`[desktop] Browser candidate failed (${candidate.label}): ${error.message}`);
    }
  }
  throw new Error(`No browser app window could be opened. Last error: ${lastError?.message ?? 'unknown'}`);
}

function waitForBrowserLaunch(candidate, child) {
  const launcherCommands = new Set(['open', 'cmd', 'xdg-open']);
  return new Promise((resolve, reject) => {
    child.once('error', reject);
    child.once('spawn', () => {
      if (!launcherCommands.has(candidate.command)) {
        resolve();
        return;
      }

      child.once('exit', (code) => {
        if (code === 0) resolve();
        else reject(new Error(`${candidate.label} exited with code ${code}`));
      });
    });
  });
}

function terminate(child) {
  if (!child || child.killed) return;
  try {
    child.kill(process.platform === 'win32' ? undefined : 'SIGTERM');
  } catch {
    // Process may already be closed.
  }
}

export async function runDesktopLauncher(rawOptions = parseDesktopArgs()) {
  if (rawOptions.help) {
    printHelp();
    return 0;
  }

  const uiBaseUrl = `http://${rawOptions.host}:${rawOptions.uiPort}`;
  const apiBaseUrl = `http://${rawOptions.apiHost}:${rawOptions.apiPort}`;
  const operatorUrl = buildOperatorUrl({ uiBaseUrl, apiBaseUrl, desktop: true });
  const children = [];

  const cleanup = () => {
    for (const child of children.reverse()) terminate(child);
  };
  process.once('SIGINT', () => {
    cleanup();
    process.exit(130);
  });
  process.once('SIGTERM', () => {
    cleanup();
    process.exit(143);
  });

  try {
    console.log('[desktop] Starting dry-run backend API...');
    const backend = await startBackend(rawOptions);
    children.push(backend.child);

    console.log(`[desktop] Starting ${rawOptions.mode === 'preview' ? 'Vite preview' : 'Vite dev'} UI...`);
    const vite = startVite(rawOptions);
    children.push(vite);

    const healthResponse = await waitForHttp(`${apiBaseUrl}/health`, { timeoutMs: rawOptions.timeoutMs, label: 'Operator API /health' });
    await assertSafeBackendHealth(healthResponse);
    await waitForHttp(uiBaseUrl, { timeoutMs: rawOptions.timeoutMs, label: 'Operator UI' });
    console.log(`[desktop] Ready: ${operatorUrl}`);

    if (rawOptions.smoke) {
      cleanup();
      return 0;
    }

    await launchBrowserApp(operatorUrl, rawOptions);
    console.log('[desktop] Gökkalkan Operator Panel is running. Press Ctrl+C to stop backend/UI services.');
    await new Promise((resolve) => {
      for (const child of children) child.once('exit', resolve);
    });
    cleanup();
    return 0;
  } catch (error) {
    cleanup();
    console.error(`[desktop] ${error instanceof Error ? error.message : String(error)}`);
    return 1;
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  runDesktopLauncher().then((code) => process.exit(code));
}
