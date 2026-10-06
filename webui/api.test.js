import assert from 'node:assert/strict';
import test from 'node:test';

const values = new Map([
  ['atulya-server-url', 'https://old-server.example'],
  ['atulya-dashboard-token', 'stale-token'],
  ['atulya-user', '{"username":"old"}'],
]);

Object.defineProperty(globalThis, 'window', {
  configurable: true,
  value: {
    Telegram: { WebApp: {} },
    location: { origin: 'https://current-server.example', search: '' },
  },
});
Object.defineProperty(globalThis, 'document', {
  configurable: true,
  value: { referrer: '', head: {}, createElement: () => ({}) },
});
Object.defineProperty(globalThis, 'navigator', {
  configurable: true,
  value: { userAgent: '' },
});
globalThis.localStorage = {
  getItem: (key) => values.get(key) ?? null,
  setItem: (key, value) => values.set(key, String(value)),
  removeItem: (key) => values.delete(key),
};

const { connectTelegramOrigin, getServerUrl, getToken } = await import('./api.js');

test('Telegram Mini App connects to its hosting server and drops another server session', () => {
  assert.equal(connectTelegramOrigin(), true);
  assert.equal(getServerUrl(), 'https://current-server.example');
  assert.equal(values.get('atulya-server-url'), 'https://current-server.example');
  assert.equal(getToken(), '');
  assert.equal(values.has('atulya-user'), false);
});

test('ordinary browsers do not have their saved server changed', () => {
  window.Telegram = undefined;
  values.set('atulya-server-url', 'https://saved-server.example');
  assert.equal(connectTelegramOrigin(), false);
  assert.equal(getServerUrl(), 'https://saved-server.example');
});
