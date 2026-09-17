/**
 * Event-loop yield helper — ADR-0018.
 */
import { describe, expect, it, vi } from 'vitest';
import { openDb, type Db } from '../src/db/connection.js';
import {
  createEventLoopYieldState,
  pollCancelAndYield,
} from '../src/jobs/yield.js';

describe('pollCancelAndYield', () => {
  it('returns true immediately when already cancelled', async () => {
    const db = openDb(':memory:');
    try {
      const state = createEventLoopYieldState();
      expect(await pollCancelAndYield(db, () => true, state)).toBe(true);
    } finally {
      db.close();
    }
  });

  it('returns false without yielding when inside the time budget', async () => {
    const db = openDb(':memory:');
    const setImmediateSpy = vi.spyOn(global, 'setImmediate');
    try {
      const state = createEventLoopYieldState();
      expect(await pollCancelAndYield(db, () => false, state)).toBe(false);
      expect(setImmediateSpy).not.toHaveBeenCalled();
    } finally {
      setImmediateSpy.mockRestore();
      db.close();
    }
  });

  it('yields via setImmediate once the budget has elapsed', async () => {
    const db = openDb(':memory:');
    const setImmediateSpy = vi.spyOn(global, 'setImmediate');
    try {
      const state = createEventLoopYieldState();
      state.lastYieldAt = 0;
      expect(await pollCancelAndYield(db, () => false, state)).toBe(false);
      expect(setImmediateSpy).toHaveBeenCalledTimes(1);
    } finally {
      setImmediateSpy.mockRestore();
      db.close();
    }
  });

  it('notices cancellation after yielding', async () => {
    const db = openDb(':memory:');
    try {
      const state = createEventLoopYieldState();
      state.lastYieldAt = 0;
      let cancelled = false;
      setImmediate(() => {
        cancelled = true;
      });
      expect(await pollCancelAndYield(db, () => cancelled, state)).toBe(true);
    } finally {
      db.close();
    }
  });

  it('refuses to yield inside an open library.db transaction', async () => {
    const db = openDb(':memory:');
    try {
      const state = createEventLoopYieldState();
      state.lastYieldAt = 0;
      libraryWrite(db, () => {
        /* transaction is open; pollCancelAndYield must not be awaited here */
      });
      // Nested libraryWrite above committed; open one explicitly instead.
      db.exec('BEGIN IMMEDIATE');
      await expect(pollCancelAndYield(db, () => false, state)).rejects.toThrow(
        /cannot yield while library.db transaction is open/,
      );
      db.exec('ROLLBACK');
    } finally {
      db.close();
    }
  });
});
