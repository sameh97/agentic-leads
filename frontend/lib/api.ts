import type { Lead } from '@/types/lead'

export type { Lead }

export const API_BASE = process.env.NEXT_PUBLIC_API_URL || ''

export interface JobCreated {
  job_id:     string
  stream_url: string
  status_url: string
}

export interface PipelineEvent {
  node:           string
  ts:             string
  message?:       string
  count?:         number
  verified?:      number
  total?:         number
  high_quality?:  number
  business_type?: string
  location?:      string
  radius_km?:     number
  csv_url?:       string
  xlsx_url?:      string
  lead_count?:    number
  preview?:       Lead[]
  status?:        string
}

export async function startJob(query: string, maxResults = 100): Promise<JobCreated> {
  const res = await fetch(`${API_BASE}/api/leads/generate`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ query, max_results: maxResults, max_retries: 3 }),
  })
  if (!res.ok) throw new Error(`API ${res.status}`)
  return res.json()
}

export async function getJobStatus(jobId: string) {
  const res = await fetch(`${API_BASE}/api/leads/status/${jobId}`)
  if (!res.ok) throw new Error(`Status ${res.status}`)
  return res.json()
}

export function downloadUrl(jobId: string, format: 'csv' | 'xlsx') {
  return `${API_BASE}/api/leads/download/${jobId}?format=${format}`
}

export function subscribeToJob(
  jobId:   string,
  onEvent: (ev: PipelineEvent) => void,
  onDone?: (status: 'done' | 'failed') => void,
): () => void {
  const es = new EventSource(`${API_BASE}/api/leads/stream/${jobId}`)

  es.onmessage = (e) => {
    const event: PipelineEvent = JSON.parse(e.data)
    onEvent(event)
    if (event.node === 'end') {
      onDone?.(event.status as 'done' | 'failed')
      es.close()
    }
  }

  es.onerror = () => { onDone?.('failed'); es.close() }

  return () => es.close()
}