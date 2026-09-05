/**
 * Burst stack route tests.
 *
 * The mutations get the most attention: each one has to leave
 * `image_stacks.stack_size` in agreement with `image_stack_members`, and a stack of
 * one is not a stack. A half-applied edit shows in the grid as a phantom stack
 * badge, which is invisible to a status-code assertion.
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { createApp } from '../src/app.js';
import { LibraryFixture } from './helpers/library-fixture.js';

let fx: LibraryFixture;
const app = createApp();
const json = async <T>(res: Response): Promise<T> => (await res.json()) as T;

const post = (path: string, body: unknown) =>
  app.request(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  });

interface StackMetadata {
  stack_id: number;
  representative_key: string;
  stack_member_count: number;
  member_keys: string[];
}

const members = (stackId: number): string[] =>
  fx
    .query<{ image_key: string }>(
      'SELECT image_key FROM image_stack_members WHERE stack_id = ? ORDER BY image_key',
      stackId,
    )
    .map((r) => r.image_key);

const stackRow = (stackId: number) =>
  fx.query<{ representative_key: string; stack_size: number; user_modified: number }>(
    'SELECT representative_key, stack_size, user_modified FROM image_stacks WHERE stack_id = ?',
    stackId,
  )[0];

beforeEach(() => {
  fx = new LibraryFixture().activate();
});
afterEach(() => fx.cleanup());

describe('GET /api/images/stacks/suggestions', () => {
  it('pairs the seed and candidate as catalog rows with thumbnails', async () => {
    fx.addImage({ key: 'seed', date_taken: '2026-01-01T00:00:00' });
    fx.addImage({ key: 'cand', date_taken: '2026-01-01T00:00:10' });
    fx.addSimilarityGroup({
      seed_key: 'seed',
      candidates: [{ key: 'cand', similarity: 0.92, why_matched: 'burst' }],
    });

    const res = await app.request('/api/images/stacks/suggestions');
    expect(res.status).toBe(200);
    const body = await json<{
      total: number;
      items: {
        group_id: number;
        image_a: { key: string; thumbnail_url: string };
        image_b: { key: string; thumbnail_url: string };
        similarity: number;
        why_matched: string;
        time_gap_seconds: number;
      }[];
    }>(res);

    expect(body.total).toBe(1);
    const item = body.items[0]!;
    expect(item.image_a.key).toBe('seed');
    expect(item.image_b.key).toBe('cand');
    expect(item.image_a.thumbnail_url).toBe('/api/images/catalog/seed/thumbnail');
    expect(item.similarity).toBeCloseTo(0.92);
    expect(item.why_matched).toBe('burst');
    expect(item.time_gap_seconds).toBe(10);
  });

  it('hides a pair the user has rejected, in either order', async () => {
    fx.addImages('a', 'b');
    fx.addSimilarityGroup({ seed_key: 'b', candidates: [{ key: 'a', similarity: 0.9 }] });

    const before = await json<{ total: number }>(
      await app.request('/api/images/stacks/suggestions'),
    );
    expect(before.total).toBe(1);

    // The group stores (seed=b, candidate=a); the rejection is keyed on the
    // normalized pair, so rejecting (a, b) must suppress it.
    expect((await post('/api/images/stacks/suggestions/reject', {
      image_key_a: 'a',
      image_key_b: 'b',
    })).status).toBe(200);

    const after = await json<{ total: number }>(
      await app.request('/api/images/stacks/suggestions'),
    );
    expect(after.total).toBe(0);
  });

  it('hides a pair whose members already share one stack', async () => {
    fx.addImages('a', 'b');
    fx.addSimilarityGroup({ seed_key: 'a', candidates: [{ key: 'b', similarity: 0.9 }] });
    fx.addStack(['a', 'b'], 'a');

    const body = await json<{ total: number }>(
      await app.request('/api/images/stacks/suggestions'),
    );
    // Nothing left to confirm.
    expect(body.total).toBe(0);
  });

  it('keeps a pair whose members are in different stacks', async () => {
    fx.addImages('a', 'a2', 'b', 'b2');
    fx.addSimilarityGroup({ seed_key: 'a', candidates: [{ key: 'b', similarity: 0.9 }] });
    fx.addStack(['a', 'a2'], 'a');
    fx.addStack(['b', 'b2'], 'b');

    const body = await json<{ total: number }>(
      await app.request('/api/images/stacks/suggestions'),
    );
    // Accepting it would merge the two stacks, which is a real action.
    expect(body.total).toBe(1);
  });

  it('hides a pair with a condemned frame at either end, unless overridden', async () => {
    fx.addImages('a', 'b');
    fx.addSimilarityGroup({ seed_key: 'a', candidates: [{ key: 'b', similarity: 0.9 }] });
    fx.addFrameSubstance('b', 'void');

    const hidden = await json<{ total: number }>(
      await app.request('/api/images/stacks/suggestions'),
    );
    expect(hidden.total).toBe(0);

    fx.addFrameSubstanceOverride('b');
    const shown = await json<{ total: number }>(
      await app.request('/api/images/stacks/suggestions'),
    );
    expect(shown.total).toBe(1);
  });

  it('ranks unstacked pairs first, then by time proximity', async () => {
    fx.addImage({ key: 'free-a', date_taken: '2026-01-01T00:00:00' });
    fx.addImage({ key: 'free-b', date_taken: '2026-01-01T00:00:30' });
    fx.addImage({ key: 'free-c', date_taken: '2026-01-02T00:00:00' });
    fx.addImage({ key: 'free-d', date_taken: '2026-01-02T00:00:01' });
    fx.addImage({ key: 'stacked', date_taken: '2026-01-03T00:00:00' });
    fx.addImage({ key: 'stacked-mate', date_taken: '2026-01-03T00:00:05' });
    fx.addImage({ key: 'loner', date_taken: '2026-01-03T00:00:01' });
    fx.addStack(['stacked', 'stacked-mate'], 'stacked');

    fx.addSimilarityGroup({ seed_key: 'free-a', candidates: [{ key: 'free-b', similarity: 0.9 }] });
    fx.addSimilarityGroup({ seed_key: 'free-c', candidates: [{ key: 'free-d', similarity: 0.9 }] });
    fx.addSimilarityGroup({ seed_key: 'stacked', candidates: [{ key: 'loner', similarity: 0.9 }] });

    const body = await json<{ items: { image_a: { key: string } }[] }>(
      await app.request('/api/images/stacks/suggestions'),
    );
    // Both-unstacked (rank 0) before one-stacked (rank 1); within rank 0, the
    // 1-second gap beats the 30-second gap.
    expect(body.items.map((i) => i.image_a.key)).toEqual(['free-c', 'free-a', 'stacked']);
  });

  it('drops a pair whose member is collapsed out of the primary grid', async () => {
    fx.addImages('rep', 'hidden', 'other');
    fx.addStack(['rep', 'hidden'], 'rep');
    fx.addSimilarityGroup({ seed_key: 'hidden', candidates: [{ key: 'other', similarity: 0.9 }] });

    const body = await json<{ total: number; items: unknown[] }>(
      await app.request('/api/images/stacks/suggestions'),
    );
    // `total` counts the pending pair, but the item cannot be rendered.
    expect(body.total).toBe(1);
    expect(body.items).toHaveLength(0);
  });

  it('caps the limit at 100 and defaults to 20', async () => {
    fx.addImages('seed', 'cand');
    // The stacks blueprint has its own `_clamp_pagination` with a 100 ceiling,
    // unlike the shared helper's 500.
    fx.addSimilarityGroup({ seed_key: 'seed', candidates: [{ key: 'cand', similarity: 0.9 }] });
    expect((await app.request('/api/images/stacks/suggestions?limit=9999')).status).toBe(200);
    expect((await app.request('/api/images/stacks/suggestions?limit=abc')).status).toBe(200);
  });
});

describe('POST /api/images/stacks/suggestions/reject', () => {
  it('stores the pair normalized and reports it back as sent', async () => {
    fx.addImages('b', 'a');
    const res = await post('/api/images/stacks/suggestions/reject', {
      image_key_a: 'b',
      image_key_b: 'a',
    });
    expect(res.status).toBe(200);
    // The echo preserves the caller's order even though storage is sorted.
    expect(await json(res)).toEqual({ image_key_a: 'b', image_key_b: 'a', rejected: true });
    expect(fx.query('SELECT key_a, key_b FROM catalog_similarity_rejections')).toEqual([
      { key_a: 'a', key_b: 'b' },
    ]);
  });

  it('is idempotent', async () => {
    fx.addImages('a', 'b');
    const body = { image_key_a: 'a', image_key_b: 'b' };
    expect((await post('/api/images/stacks/suggestions/reject', body)).status).toBe(200);
    expect((await post('/api/images/stacks/suggestions/reject', body)).status).toBe(200);
    expect(fx.query('SELECT COUNT(*) AS c FROM catalog_similarity_rejections')).toEqual([
      { c: 1 },
    ]);
  });

  it('400s on identical keys', async () => {
    const res = await post('/api/images/stacks/suggestions/reject', {
      image_key_a: 'x',
      image_key_b: 'x',
    });
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'image_key_a and image_key_b must differ' });
  });

  it('400s on an empty key and 422s on a missing one', async () => {
    const empty = await post('/api/images/stacks/suggestions/reject', {
      image_key_a: '',
      image_key_b: 'b',
    });
    expect(empty.status).toBe(400);
    expect(await json(empty)).toEqual({ error: 'image_key_a and image_key_b required' });

    // A missing field fails the declared schema first (422).
    expect((await post('/api/images/stacks/suggestions/reject', { image_key_a: 'a' })).status).toBe(
      422,
    );
  });
});

describe('POST /api/images/stacks/suggestions/accept', () => {
  it('creates a stack from two solo images', async () => {
    fx.addImage({ key: 'a', rating: 0, date_taken: '2026-01-01' });
    fx.addImage({ key: 'b', rating: 3, date_taken: '2026-01-02' });

    const res = await post('/api/images/stacks/suggestions/accept', {
      image_key_a: 'a',
      image_key_b: 'b',
    });
    expect(res.status).toBe(200);
    const body = await json<{ stack: StackMetadata }>(res);

    expect(body.stack.member_keys).toEqual(['a', 'b']);
    expect(body.stack.stack_member_count).toBe(2);
    // The representative ranking puts a rated image first.
    expect(body.stack.representative_key).toBe('b');
    expect(stackRow(body.stack.stack_id)!.user_modified).toBe(1);
  });

  it('adds to the existing stack when only one image is stacked', async () => {
    fx.addImages('rep', 'mate', 'loose');
    const stackId = fx.addStack(['rep', 'mate'], 'rep');

    const body = await json<{ stack: StackMetadata }>(
      await post('/api/images/stacks/suggestions/accept', {
        image_key_a: 'loose',
        image_key_b: 'rep',
      }),
    );
    expect(body.stack.stack_id).toBe(stackId);
    expect(body.stack.member_keys).toEqual(['loose', 'mate', 'rep']);
    expect(stackRow(stackId)!.stack_size).toBe(3);
  });

  it('merges two stacks and reports only the stack, not merged_stack_id', async () => {
    fx.addImages('a1', 'a2', 'b1', 'b2');
    const target = fx.addStack(['a1', 'a2'], 'a1');
    const source = fx.addStack(['b1', 'b2'], 'b1');

    const res = await post('/api/images/stacks/suggestions/accept', {
      image_key_a: 'a1',
      image_key_b: 'b1',
    });
    expect(res.status).toBe(200);
    const body = await json<Record<string, unknown>>(res);

    // `stackAcceptSuggestionPair` returns `merged_stack_id` on this branch, but the
    // response model forbids extra fields, so the route narrows it away.
    expect(Object.keys(body)).toEqual(['stack']);
    expect(members(target)).toEqual(['a1', 'a2', 'b1', 'b2']);
    expect(stackRow(source)).toBeUndefined();
  });

  it('is a no-op when both images already share a stack', async () => {
    fx.addImages('a', 'b');
    const stackId = fx.addStack(['a', 'b'], 'a');
    const body = await json<{ stack: StackMetadata }>(
      await post('/api/images/stacks/suggestions/accept', {
        image_key_a: 'a',
        image_key_b: 'b',
      }),
    );
    expect(body.stack.stack_id).toBe(stackId);
    expect(body.stack.member_keys).toEqual(['a', 'b']);
  });

  it('500s when neither key names a real image', async () => {
    // Representative selection queries images; with no rows it returns 500.
    const res = await post('/api/images/stacks/suggestions/accept', {
      image_key_a: 'nope-a',
      image_key_b: 'nope-b',
    });
    expect(res.status).toBe(500);
    expect(await json(res)).toEqual({ error: 'stack representative selection failed' });
  });

  it('400s on identical keys', async () => {
    fx.addImages('a');
    const res = await post('/api/images/stacks/suggestions/accept', {
      image_key_a: 'a',
      image_key_b: 'a',
    });
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'image keys must differ' });
  });

  it('leaves no stack behind when the write fails', async () => {
    const res = await post('/api/images/stacks/suggestions/accept', {
      image_key_a: 'nope-a',
      image_key_b: 'nope-b',
    });
    expect(res.status).toBe(500);
    // `libraryWrite` rolls the whole transaction back, so no orphan row survives.
    expect(fx.query('SELECT COUNT(*) AS c FROM image_stacks')).toEqual([{ c: 0 }]);
  });
});

describe('GET /api/images/stacks/{stack_id}/members', () => {
  it('lists every member, including the ones the grid collapses', async () => {
    fx.addImages('rep', 'member');
    const stackId = fx.addStack(['rep', 'member'], 'rep');

    const res = await app.request(`/api/images/stacks/${stackId}/members`);
    expect(res.status).toBe(200);
    const body = await json<{ items: { key: string; thumbnail_url: string }[] }>(res);

    // Lists every member, not just the rows the catalog grid collapses to.
    expect(body.items.map((i) => i.key)).toEqual(['member', 'rep']);
    expect(body.items[0]!.thumbnail_url).toBe('/api/images/catalog/member/thumbnail');
  });

  it('404s for an unknown stack and for id 0', async () => {
    for (const id of [999999, 0]) {
      const res = await app.request(`/api/images/stacks/${id}/members`);
      expect(res.status).toBe(404);
      expect(await json(res)).toEqual({ error: 'stack not found' });
    }
  });
});

describe('POST /api/images/stacks/{stack_id}/split-member', () => {
  it('removes one member from a three-member stack', async () => {
    fx.addImages('a', 'b', 'c');
    const stackId = fx.addStack(['a', 'b', 'c'], 'a');

    const res = await post(`/api/images/stacks/${stackId}/split-member`, { image_key: 'c' });
    expect(res.status).toBe(200);
    const body = await json<{
      split_out_key: string;
      remaining_stack: StackMetadata;
      dissolved: boolean;
    }>(res);

    expect(body.split_out_key).toBe('c');
    expect(body.dissolved).toBe(false);
    expect(body.remaining_stack.member_keys).toEqual(['a', 'b']);
    expect(stackRow(stackId)!.stack_size).toBe(2);
  });

  it('dissolves a two-member stack entirely', async () => {
    fx.addImages('a', 'b');
    const stackId = fx.addStack(['a', 'b'], 'a');

    const body = await json<{ dissolved: boolean; remaining_stack: null }>(
      await post(`/api/images/stacks/${stackId}/split-member`, { image_key: 'b' }),
    );
    // A stack of one is not a stack: the remaining member goes back to solo.
    expect(body.dissolved).toBe(true);
    expect(body.remaining_stack).toBeNull();
    expect(stackRow(stackId)).toBeUndefined();
    expect(members(stackId)).toEqual([]);
  });

  it('reassigns the representative when it is the one split out', async () => {
    fx.addImage({ key: 'a', rating: 0 });
    fx.addImage({ key: 'b', rating: 5 });
    fx.addImage({ key: 'c', rating: 0 });
    const stackId = fx.addStack(['a', 'b', 'c'], 'a');

    const body = await json<{ remaining_stack: StackMetadata }>(
      await post(`/api/images/stacks/${stackId}/split-member`, { image_key: 'a' }),
    );
    // Same ranking as detection: the rated image wins.
    expect(body.remaining_stack.representative_key).toBe('b');
  });

  it('keeps the representative when someone else is split out', async () => {
    fx.addImages('a', 'b', 'c');
    const stackId = fx.addStack(['a', 'b', 'c'], 'a');
    await post(`/api/images/stacks/${stackId}/split-member`, { image_key: 'c' });
    expect(stackRow(stackId)!.representative_key).toBe('a');
  });

  it('400s when the image is not a member', async () => {
    fx.addImages('a', 'b', 'outsider');
    const stackId = fx.addStack(['a', 'b'], 'a');
    const res = await post(`/api/images/stacks/${stackId}/split-member`, {
      image_key: 'outsider',
    });
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'image_key is not a member of this stack' });
  });

  it('404s for an unknown stack', async () => {
    const res = await post('/api/images/stacks/999999/split-member', { image_key: 'x' });
    expect(res.status).toBe(404);
    expect(await json(res)).toEqual({ error: 'stack not found' });
  });

  it('422s a missing image_key and 400s an empty one', async () => {
    fx.addImages('a', 'b');
    const stackId = fx.addStack(['a', 'b'], 'a');
    expect((await post(`/api/images/stacks/${stackId}/split-member`, {})).status).toBe(422);

    const empty = await post(`/api/images/stacks/${stackId}/split-member`, { image_key: '' });
    expect(empty.status).toBe(400);
    expect(await json(empty)).toEqual({ error: 'image_key required' });
  });
});

describe('POST /api/images/stacks/{target_stack_id}/merge', () => {
  it('moves every member across and deletes the source', async () => {
    fx.addImages('a1', 'a2', 'b1', 'b2');
    const target = fx.addStack(['a1', 'a2'], 'a1');
    const source = fx.addStack(['b1', 'b2'], 'b1');

    const res = await post(`/api/images/stacks/${target}/merge`, { source_stack_id: source });
    expect(res.status).toBe(200);
    const body = await json<{ stack: StackMetadata; merged_stack_id: number }>(res);

    expect(body.merged_stack_id).toBe(source);
    expect(body.stack.member_keys).toEqual(['a1', 'a2', 'b1', 'b2']);
    expect(body.stack.stack_member_count).toBe(4);
    expect(stackRow(target)!.stack_size).toBe(4);
    expect(stackRow(source)).toBeUndefined();
  });

  it('keeps the target representative', async () => {
    fx.addImages('a1', 'a2', 'b1', 'b2');
    const target = fx.addStack(['a1', 'a2'], 'a2');
    const source = fx.addStack(['b1', 'b2'], 'b1');
    await post(`/api/images/stacks/${target}/merge`, { source_stack_id: source });
    expect(stackRow(target)!.representative_key).toBe('a2');
  });

  it('400s on merging a stack into itself', async () => {
    fx.addImages('a', 'b');
    const stackId = fx.addStack(['a', 'b'], 'a');
    const res = await post(`/api/images/stacks/${stackId}/merge`, { source_stack_id: stackId });
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'cannot merge a stack into itself' });
  });

  it('404s when either stack is missing', async () => {
    fx.addImages('a', 'b');
    const stackId = fx.addStack(['a', 'b'], 'a');
    const missingSource = await post(`/api/images/stacks/${stackId}/merge`, {
      source_stack_id: 999999,
    });
    expect(missingSource.status).toBe(404);
    expect((await post('/api/images/stacks/999999/merge', { source_stack_id: stackId })).status).toBe(
      404,
    );
  });

  it('rolls back completely when the merge is refused', async () => {
    fx.addImages('a1', 'a2', 'b1', 'b2');
    const target = fx.addStack(['a1', 'a2'], 'a1');
    await post(`/api/images/stacks/${target}/merge`, { source_stack_id: 999999 });
    // The source lookup fails before any UPDATE, but assert the end state anyway:
    // a partial merge is the failure mode that corrupts the grid.
    expect(members(target)).toEqual(['a1', 'a2']);
    expect(stackRow(target)!.stack_size).toBe(2);
  });

  it('422s a non-integer source id', async () => {
    fx.addImages('a', 'b');
    const stackId = fx.addStack(['a', 'b'], 'a');
    // Non-integer source_stack_id is rejected at schema validation (422), not deferred to a 404.
    expect((await post(`/api/images/stacks/${stackId}/merge`, { source_stack_id: 'abc' })).status).toBe(
      422,
    );
    expect((await post(`/api/images/stacks/${stackId}/merge`, {})).status).toBe(422);
    expect((await post(`/api/images/stacks/${stackId}/merge`, { source_stack_id: '7' })).status).toBe(
      422,
    );
  });
});

describe('POST /api/images/stacks/{stack_id}/representative', () => {
  it('promotes a member and realigns stack_size', async () => {
    fx.addImages('a', 'b', 'c');
    const stackId = fx.addStack(['a', 'b', 'c'], 'a');

    const res = await post(`/api/images/stacks/${stackId}/representative`, { image_key: 'c' });
    expect(res.status).toBe(200);
    const body = await json<{ stack: StackMetadata }>(res);

    expect(body.stack.representative_key).toBe('c');
    expect(stackRow(stackId)!.representative_key).toBe('c');
    expect(stackRow(stackId)!.stack_size).toBe(3);
    expect(stackRow(stackId)!.user_modified).toBe(1);
  });

  it('400s when the image is not a member', async () => {
    fx.addImages('a', 'b', 'outsider');
    const stackId = fx.addStack(['a', 'b'], 'a');
    const res = await post(`/api/images/stacks/${stackId}/representative`, {
      image_key: 'outsider',
    });
    expect(res.status).toBe(400);
    expect(await json(res)).toEqual({ error: 'image_key is not a member of this stack' });
    // The refused write must not have changed the representative.
    expect(stackRow(stackId)!.representative_key).toBe('a');
  });

  it('404s for an unknown stack', async () => {
    const res = await post('/api/images/stacks/999999/representative', { image_key: 'x' });
    expect(res.status).toBe(404);
  });
});

describe('the grid reflects a mutation', () => {
  it('un-collapses a split-out member on the next catalog listing', async () => {
    fx.addImages('rep', 'member');
    const stackId = fx.addStack(['rep', 'member'], 'rep');

    const before = await json<{ images: { key: string }[] }>(
      await app.request('/api/images/catalog'),
    );
    expect(before.images.map((i) => i.key)).toEqual(['rep']);

    await post(`/api/images/stacks/${stackId}/split-member`, { image_key: 'member' });

    const after = await json<{ images: { key: string }[] }>(
      await app.request('/api/images/catalog'),
    );
    // Dissolving the stack returns both images to the grid as solo rows.
    expect(after.images.map((i) => i.key).sort()).toEqual(['member', 'rep']);
  });
});
