import { describe, expect, it } from 'vitest';
import { buildDateMetadata } from '../AnalyzeTab';

// `buildDateMetadata` is the translation layer between the UI enum (e.g.
// '9months' / '2024') and the backend metadata keys (`last_months` / `year`).
// Guarding it with focused unit tests prevents silent regressions when the
// dropdown grows — each option that we add to the UI must have a matching
// test here so the backend receives the right numeric window.
describe('AnalyzeTab buildDateMetadata', () => {
  it('maps "all" to only date_filter', () => {
    expect(buildDateMetadata('all')).toEqual({ date_filter: 'all' });
  });

  it.each([
    ['1months', 1],
    ['2months', 2],
    ['3months', 3],
    ['6months', 6],
    ['9months', 9],
    ['12months', 12],
    ['18months', 18],
    ['24months', 24],
  ] as const)('maps %s to last_months=%d', (filter, expected) => {
    expect(buildDateMetadata(filter)).toEqual({
      date_filter: filter,
      last_months: expected,
    });
  });

  it.each(['2023', '2024', '2025', '2026'] as const)(
    'maps %s to year',
    (year) => {
      expect(buildDateMetadata(year)).toEqual({ date_filter: year, year });
    },
  );
});
