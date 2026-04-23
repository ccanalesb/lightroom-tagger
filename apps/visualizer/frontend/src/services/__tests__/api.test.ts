import { describe, it, expect, vi, beforeEach } from 'vitest'
import { deleteMatching } from '../../data/cache'
import { query } from '../../data/query'
import { JobsAPI, ImagesAPI, MatchingAPI, DescriptionsAPI } from '../api'

const fetchMock = vi.fn()
globalThis.fetch = fetchMock

function catchThrown(fn: () => void): unknown {
  try {
    fn()
    return undefined
  } catch (e) {
    return e
  }
}

describe('JobsAPI', () => {
  beforeEach(() => {
    deleteMatching(() => true)
    vi.clearAllMocks()
  })

  it('should list all jobs (paginated envelope)', async () => {
    const envelope = {
      total: 1,
      data: [{ id: '1', type: 'test', status: 'pending' }],
      pagination: { offset: 0, limit: 50, current_page: 1, total_pages: 1, has_more: false },
    }
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => envelope,
    })

    const result = await JobsAPI.list()

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/jobs/'),
      expect.objectContaining({ headers: { 'Content-Type': 'application/json' } })
    )
    expect(result).toEqual(envelope)
    expect(result.data).toHaveLength(1)
    expect(result.total).toBe(1)
  })

  it('list() forwards status, limit, and offset as query params', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        total: 0,
        data: [],
        pagination: { offset: 100, limit: 25, current_page: 5, total_pages: 0, has_more: false },
      }),
    })
    await JobsAPI.list({ status: 'pending', limit: 25, offset: 100 })
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('status=pending')
    expect(url).toContain('limit=25')
    expect(url).toContain('offset=100')
  })

  it('get(id) without options calls /jobs/<id> with no query string', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 'abc', logs: [], logs_total: 0 }),
    })
    await JobsAPI.get('abc')
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toMatch(/\/jobs\/abc$/)
  })

  it('get(id, { logs_limit: 20 }) appends ?logs_limit=20', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 'abc', logs: [], logs_total: 0 }),
    })
    await JobsAPI.get('abc', { logs_limit: 20 })
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('logs_limit=20')
  })

  it('get(id, { logs_limit: 0 }) still appends ?logs_limit=0 (expand path)', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ id: 'abc', logs: [], logs_total: 0 }),
    })
    await JobsAPI.get('abc', { logs_limit: 0 })
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('logs_limit=0')
  })

  it('should get job by id', async () => {
    const mockJob = { id: '123', type: 'test', status: 'running' }
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => mockJob,
    })

    const job = await JobsAPI.get('123')

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/jobs/123'),
      expect.any(Object)
    )
    expect(job).toEqual(mockJob)
  })

  it('should create job', async () => {
    const mockJob = { id: '456', type: 'analyze', status: 'pending' }
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => mockJob,
    })

    const job = await JobsAPI.create('analyze', { test: true })

    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/jobs/'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ type: 'analyze', metadata: { test: true } }),
      })
    )
    expect(job).toEqual(mockJob)
  })

  it('should throw on error', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 404,
      statusText: 'Not Found',
    })

    await expect(JobsAPI.get('nonexistent')).rejects.toThrow('404 Not Found')
  })
})

describe('ImagesAPI.getImageDetail', () => {
  beforeEach(() => {
    deleteMatching(() => true)
    vi.clearAllMocks()
  })

  it('calls /images/<type>/<key> with no query when score_perspective omitted', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ image_type: 'catalog', key: 'abc' }),
    })
    await ImagesAPI.getImageDetail('catalog', 'abc')
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toMatch(/\/images\/catalog\/abc$/)
    expect(url).not.toContain('?')
  })

  it('URL-encodes the image_key and appends score_perspective when provided', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ image_type: 'catalog', key: 'a/b c' }),
    })
    await ImagesAPI.getImageDetail('catalog', 'a/b c', { score_perspective: 'street' })
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toContain('/images/catalog/a%2Fb%20c')
    expect(url).toContain('score_perspective=street')
  })

  it('uses /images/instagram/<key> for instagram image_type', async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ image_type: 'instagram', key: 'ig1' }),
    })
    await ImagesAPI.getImageDetail('instagram', 'ig1')
    const url = fetchMock.mock.calls[0][0] as string
    expect(url).toMatch(/\/images\/instagram\/ig1$/)
  })
})

describe('mutation invalidation (cache)', () => {
  beforeEach(() => {
    deleteMatching(() => true)
    vi.clearAllMocks()
  })

  it('MatchingAPI.validate clears matching.groups query so list refetches', async () => {
    const listPayload = {
      total: 0,
      total_groups: 0,
      match_groups: [] as unknown[],
      matches: [] as unknown[],
    }
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => listPayload,
    })
    const listFetcher = () => MatchingAPI.list(100, 0, { sort_by_date: 'newest' })
    const p1 = catchThrown(() => query(['matching.groups', 'newest'], listFetcher)) as Promise<unknown>
    await p1
    expect(query(['matching.groups', 'newest'], listFetcher)).toEqual(listPayload)
    expect(fetchMock).toHaveBeenCalledTimes(1)

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ validated: true }),
    })
    await MatchingAPI.validate('ck', 'ik')

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => listPayload,
    })
    const p2 = catchThrown(() => query(['matching.groups', 'newest'], listFetcher)) as Promise<unknown>
    await p2
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('MatchingAPI.reject clears matching.groups query so list refetches', async () => {
    const listPayload = {
      total: 0,
      total_groups: 0,
      match_groups: [] as unknown[],
      matches: [] as unknown[],
    }
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => listPayload,
    })
    const listFetcher = () => MatchingAPI.list(50, 0, { sort_by_date: 'oldest' })
    const p1 = catchThrown(() => query(['matching.groups', 'oldest'], listFetcher)) as Promise<unknown>
    await p1
    expect(fetchMock).toHaveBeenCalledTimes(1)

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ rejected: true }),
    })
    await MatchingAPI.reject('c1', 'i1')

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => listPayload,
    })
    const p2 = catchThrown(() => query(['matching.groups', 'oldest'], listFetcher)) as Promise<unknown>
    await p2
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('DescriptionsAPI.generate clears descriptions query for that image key', async () => {
    const imageKey = 'img-42'
    const getPayload = { description: { summary: 'x' } }
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => getPayload,
    })
    const fetcher = () => DescriptionsAPI.get(imageKey)
    const p1 = catchThrown(() => query(['descriptions', imageKey], fetcher)) as Promise<unknown>
    await p1
    expect(fetchMock).toHaveBeenCalledTimes(1)

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => ({ generated: true, description: null }),
    })
    await DescriptionsAPI.generate(imageKey, 'catalog')

    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => getPayload,
    })
    const p2 = catchThrown(() => query(['descriptions', imageKey], fetcher)) as Promise<unknown>
    await p2
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })
})
