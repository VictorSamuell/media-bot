import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readSession, saveSession, removeSession, SESSION_STORAGE_KEY } from './session.ts';

test('restores session without extending expiry and removes invalid data', () => {
  const values = new Map();
  globalThis.localStorage = {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  };
  const session = {token:'test-token', expiresAt:Date.now()+7200000};
  saveSession(session);
  assert.deepEqual(readSession(), session);
  assert.deepEqual(readSession(), session);
  removeSession();
  assert.equal(readSession(),null);
  for (const value of ['broken', JSON.stringify({token:'x',expiresAt:Date.now()-1}), '{}']) {
    values.set(SESSION_STORAGE_KEY,value);
    assert.equal(readSession(),null);
    assert.equal(values.has(SESSION_STORAGE_KEY),false);
  }
});
