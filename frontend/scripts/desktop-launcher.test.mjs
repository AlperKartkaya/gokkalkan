import assert from 'node:assert/strict';
import test from 'node:test';
import { assertSafeBackendHealth, browserCommandCandidates, buildOperatorUrl, parseDesktopArgs, pythonCandidates } from './desktop-launcher.mjs';

test('buildOperatorUrl opens the operator panel with backend API and desktop flag', () => {
  const url = buildOperatorUrl({ uiBaseUrl: 'http://127.0.0.1:5173', apiBaseUrl: 'http://127.0.0.1:8088', desktop: true });
  const parsed = new URL(url);
  assert.equal(parsed.origin, 'http://127.0.0.1:5173');
  assert.equal(parsed.searchParams.get('operator'), '1');
  assert.equal(parsed.searchParams.get('operatorApi'), 'http://127.0.0.1:8088');
  assert.equal(parsed.searchParams.get('desktop'), '1');
});

test('parseDesktopArgs supports smoke checks on non-default ports', () => {
  const parsed = parseDesktopArgs(['--mode', 'preview', '--no-browser', '--smoke', '--ui-port', '5190', '--api-port', '8090', '--timeout-ms', '5000'], {});
  assert.equal(parsed.mode, 'preview');
  assert.equal(parsed.noBrowser, true);
  assert.equal(parsed.smoke, true);
  assert.equal(parsed.uiPort, 5190);
  assert.equal(parsed.apiPort, 8090);
  assert.equal(parsed.timeoutMs, 5000);
});

test('parseDesktopArgs defaults to dev desktop ports', () => {
  const parsed = parseDesktopArgs([], {});
  assert.equal(parsed.mode, 'dev');
  assert.equal(parsed.uiPort, 5173);
  assert.equal(parsed.apiPort, 8088);
});

test('browserCommandCandidates are cross-platform and keep vendor viewers out of the main panel', () => {
  const url = 'http://127.0.0.1:5173/?operator=1&desktop=1';
  const linux = browserCommandCandidates({ platform: 'linux', env: {}, exists: () => false, url });
  const mac = browserCommandCandidates({ platform: 'darwin', env: {}, exists: () => false, url });
  const win = browserCommandCandidates({ platform: 'win32', env: { LOCALAPPDATA: 'C:/Users/test/AppData/Local' }, exists: () => false, url });

  assert.ok(linux.some((item) => item.command === 'xdg-open'));
  assert.ok(mac.some((item) => item.command === 'open'));
  assert.ok(win.some((item) => item.command === 'cmd'));
  for (const candidates of [linux, mac, win]) {
    assert.equal(candidates.some((item) => /RPLIDAR|Livox/i.test(`${item.command} ${item.args.join(' ')}`)), false);
  }
});

test('pythonCandidates prefer Windows launcher on Windows and python3 elsewhere', () => {
  assert.equal(pythonCandidates('win32', {})[0].command, 'py');
  assert.equal(pythonCandidates('darwin', {})[0].command, 'python3');
  assert.equal(pythonCandidates('linux', {})[0].command, 'python3');
});

test('assertSafeBackendHealth accepts only SIM with physical output disabled', async () => {
  await assertSafeBackendHealth(new Response(JSON.stringify({
    runtimeMode: 'SIM',
    physicalOutputEnabled: false,
  })));
  await assert.rejects(
    assertSafeBackendHealth(new Response(JSON.stringify({
      runtimeMode: 'LIVE',
      physicalOutputEnabled: true,
    }))),
    /Unsafe desktop backend health/,
  );
});
