import { describe, it, expect, vi, beforeEach } from 'vitest'
import { JobsAPI } from '../api'

const fetchMock = vi.fn()
globalThis.fetch = fetchMock

describe('JobsAPI', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })
  
  it('should list all jobs', async () => {
    const mockJobs = [{ id: '1', type: 'test', status: 'pending' }]
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: async () => mockJobs,
    })
    
    const jobs = await JobsAPI.list()
    
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/jobs/'),
      expect.objectContaining({ headers: { 'Content-Type': 'application/json' } })
    )
    expect(jobs).toEqual(mockJobs)
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
