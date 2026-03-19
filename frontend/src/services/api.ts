import { Job } from '../types/job'
import { API_DEFAULT_URL } from '../constants/strings'

const API_URL = import.meta.env.VITE_API_URL || API_DEFAULT_URL

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  })
  
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`)
  }
  
  return response.json()
}

export const JobsAPI = {
  list: (status?: string) => 
    request<Job[]>(status ? `/jobs/?status=${status}` : '/jobs/'),
  
  get: (id: string) => 
    request<Job>(`/jobs/${id}`),
  
  create: (type: string, metadata?: Record<string, any>) =>
    request<Job>('/jobs/', {
      method: 'POST',
      body: JSON.stringify({ type, metadata }),
    }),
  
  getActive: () => 
    request<Job[]>('/jobs/active'),
  
  cancel: (id: string) => 
    request<void>(`/jobs/${id}`, { method: 'DELETE' }),
}

export const SystemAPI = {
  status: () => 
    request<{ status: string }>('/status'),
}