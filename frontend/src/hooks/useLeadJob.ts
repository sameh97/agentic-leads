'use client'

import { useState, useRef, useCallback } from 'react'
import { startJob, subscribeToJob, PipelineEvent } from '@/lib/api'
import type { Lead } from '@/types/lead'

export type JobStatus = 'idle' | 'queued' | 'running' | 'done' | 'failed'

export interface NodeState {
  id:     string
  label:  string
  icon:   string
  status: 'idle' | 'active' | 'done' | 'error'
  detail: string
}

const INITIAL_NODES: NodeState[] = [
  { id: 'parse_query',     label: 'Query Parser',   icon: '🧠', status: 'idle', detail: 'Waiting…' },
  { id: 'scrape_maps',     label: 'Maps Scraper',   icon: '🗺️',  status: 'idle', detail: 'Waiting…' },
  { id: 'enrich_websites', label: 'Email Enricher', icon: '📧', status: 'idle', detail: 'Waiting…' },
  { id: 'verify_emails',   label: 'Verifier',       icon: '✅', status: 'idle', detail: 'Waiting…' },
  { id: 'score_leads',     label: 'Lead Scorer',    icon: '⭐', status: 'idle', detail: 'Waiting…' },
  { id: 'deliver',         label: 'File Delivery',  icon: '📥', status: 'idle', detail: 'Waiting…' },
]

export function useLeadJob() {
  const [status, setStatus]     = useState<JobStatus>('idle')
  const [nodes, setNodes]       = useState<NodeState[]>(INITIAL_NODES.map(n => ({ ...n })))
  const [events, setEvents]     = useState<PipelineEvent[]>([])
  const [leads, setLeads]       = useState<Lead[]>([])
  const [leadCount, setLeadCount] = useState(0)
  const [csvUrl, setCsvUrl]     = useState('')
  const [xlsxUrl, setXlsxUrl]   = useState('')

  const unsub = useRef<(() => void) | null>(null)

  const advanceNode = useCallback((nodeId: string, detail: string, s: NodeState['status'] = 'done') => {
    setNodes(prev => {
      const next = prev.map(n => ({ ...n }))
      const idx  = next.findIndex(n => n.id === nodeId)
      if (idx !== -1) {
        next[idx].status = s
        next[idx].detail = detail
        if (s === 'done' && idx + 1 < next.length) {
          next[idx + 1].status = 'active'
        }
      }
      return next
    })
  }, [])

  const handleEvent = useCallback((ev: PipelineEvent) => {
    setEvents(prev => [...prev, ev])

    switch (ev.node) {
      case 'start':
        setStatus('running')
        setNodes(prev => {
          const n = prev.map(p => ({ ...p }))
          n[0].status = 'active'
          return n
        })
        break

      case 'parse_query':
        advanceNode('parse_query', `${ev.business_type} · ${ev.location}`)
        break

      case 'scrape_maps':
        advanceNode('scrape_maps', `${ev.count ?? 0} businesses`)
        break

      case 'enrich_websites':
        advanceNode('enrich_websites', `${ev.count ?? 0} with email`)
        break

      case 'verify_emails':
        advanceNode('verify_emails', `${ev.verified ?? 0}/${ev.total ?? 0} valid`)
        break

      case 'score_leads':
        advanceNode('score_leads', `${ev.high_quality ?? 0} high-quality`)
        if (ev.preview?.length) setLeads(ev.preview as Lead[])
        break

      case 'deliver':
        advanceNode('deliver', 'Files ready')
        if (ev.csv_url)  setCsvUrl(ev.csv_url)
        if (ev.xlsx_url) setXlsxUrl(ev.xlsx_url)
        break

      case 'done':
        setStatus('done')
        setLeadCount(ev.lead_count ?? 0)
        if (ev.lead_count) setLeadCount(ev.lead_count)
        break

      case 'fail':
        setStatus('failed')
        setNodes(prev => {
          const n = prev.map(p => ({ ...p }))
          const active = n.find(x => x.status === 'active')
          if (active) { active.status = 'error'; active.detail = 'Failed' }
          return n
        })
        break
    }
  }, [advanceNode])

  const run = useCallback(async (query: string) => {
    if (!query.trim()) return
    unsub.current?.()

    // Reset all state
    setStatus('queued')
    setNodes(INITIAL_NODES.map(n => ({ ...n })))
    setEvents([])
    setLeads([])
    setLeadCount(0)
    setCsvUrl('')
    setXlsxUrl('')

    try {
      const job = await startJob(query)
      unsub.current = subscribeToJob(
        job.job_id,
        handleEvent,
        (finalStatus) => setStatus(finalStatus === 'done' ? 'done' : 'failed'),
      )
    } catch (err) {
      console.error('Job start failed:', err)
      // Fall through to demo mode
      runDemo(handleEvent, setStatus, setLeads, setLeadCount)
    }
  }, [handleEvent])

  return { status, nodes, events, leads, leadCount, csvUrl, xlsxUrl, run }
}

// ── Demo mode when backend is not reachable ─────────────────────────────────

function runDemo(
  handleEvent: (ev: PipelineEvent) => void,
  setStatus: (s: JobStatus) => void,
  setLeads: (l: Lead[]) => void,
  setLeadCount: (n: number) => void,
) {
  const DEMO: Lead[] = [
    { name: 'Sunrise HVAC Services',   primary_email: 'owner@sunrisehvac.com',    email_verified: true,  email_catchall: false, email_status: 'valid',     rating: 4.8, review_count: 142, score: 92, phone: '+1-512-555-0101', address: '2201 S Lamar Blvd, Austin, TX', website: 'sunrisehvac.com',    owner_name: 'Mike Torres',  owner_position: 'Owner', category: 'HVAC', source: 'demo' },
    { name: 'Hill Country HVAC',       primary_email: 'founder@hillcountryhvac.com', email_verified: true,  email_catchall: false, email_status: 'valid',     rating: 4.9, review_count: 312, score: 96, phone: '+1-512-555-0278', address: '8802 Research Blvd, Austin, TX', website: 'hillcountryhvac.com', owner_name: 'Lisa Garza',   owner_position: 'Founder', category: 'HVAC', source: 'demo' },
    { name: 'Capital HVAC & Cooling',  primary_email: 'ceo@capitalhvac.com',      email_verified: true,  email_catchall: false, email_status: 'valid',     rating: 4.6, review_count: 203, score: 86, phone: '+1-737-555-0034', address: '6301 W Parmer Ln, Austin, TX',   website: 'capitalhvac.com',   owner_name: 'James Powell', owner_position: 'CEO', category: 'HVAC', source: 'demo' },
    { name: 'Metro Climate Control',   primary_email: 'ceo@metroclimatectrl.com', email_verified: true,  email_catchall: false, email_status: 'valid',     rating: 4.5, review_count: 98,  score: 82, phone: '+1-512-555-0142', address: '4518 N Lamar Blvd, Austin, TX',  website: 'metroclimatectrl.com', owner_name: 'Sarah Kim',   owner_position: 'CEO', category: 'HVAC', source: 'demo' },
    { name: 'Lone Star Climate Pros',  primary_email: 'owner@lonestarclimate.com', email_verified: true,  email_catchall: false, email_status: 'valid',     rating: 4.7, review_count: 178, score: 86, phone: '+1-737-555-0089', address: '2814 Exposition Blvd, Austin, TX', website: 'lonestarclimate.com', owner_name: 'Robert Chen', owner_position: 'Owner', category: 'HVAC', source: 'demo' },
    { name: 'Austin Air Pro',          primary_email: 'info@austinairpro.com',     email_verified: false, email_catchall: true,  email_status: 'catch-all', rating: 4.5, review_count: 67,  score: 68, phone: '+1-512-555-0189', address: '1902 E Cesar Chavez, Austin, TX', website: 'austinairpro.com',  owner_name: '',             owner_position: '', category: 'HVAC', source: 'demo' },
    { name: 'Bluebonnet Air Services', primary_email: 'hello@bluebonnetair.com',  email_verified: false, email_catchall: true,  email_status: 'catch-all', rating: 4.0, review_count: 21,  score: 52, phone: '+1-512-555-0312', address: '5201 Airport Blvd, Austin, TX',   website: 'bluebonnetair.com', owner_name: '',             owner_position: '', category: 'HVAC', source: 'demo' },
    { name: 'Texas Comfort Systems',   primary_email: 'contact@txcomfort.com',    email_verified: false, email_catchall: false, email_status: 'unknown',   rating: 4.1, review_count: 34,  score: 38, phone: '',                address: '3344 Oak Springs Dr, Austin, TX', website: 'txcomfort.com',    owner_name: '',             owner_position: '', category: 'HVAC', source: 'demo' },
  ]

  const steps: PipelineEvent[] = [
    { node: 'start',           ts: now(), message: '[DEMO MODE] Simulating pipeline — connect backend for live data' },
    { node: 'parse_query',     ts: now(), business_type: 'HVAC company', location: 'Austin, TX', radius_km: 25, message: 'Query parsed' },
    { node: 'scrape_maps',     ts: now(), count: 48, message: 'Scraped 48 businesses' },
    { node: 'enrich_websites', ts: now(), count: 31, message: 'Found emails for 31 businesses' },
    { node: 'verify_emails',   ts: now(), verified: 28, total: 31, message: '28/31 emails verified' },
    { node: 'score_leads',     ts: now(), high_quality: 5, preview: DEMO, message: 'Leads scored' },
    { node: 'deliver',         ts: now(), csv_url: '#', xlsx_url: '#', message: 'Files ready' },
    { node: 'done',            ts: now(), lead_count: DEMO.length, message: `${DEMO.length} verified leads ready!` },
  ]

  const delays = [300, 900, 2500, 4200, 6000, 6800, 7200, 7600]
  steps.forEach((ev, i) => {
    setTimeout(() => {
      handleEvent(ev)
      if (ev.node === 'done') {
        setLeads(DEMO)
        setLeadCount(DEMO.length)
        setStatus('done')
      }
    }, delays[i])
  })
}

function now() { return new Date().toISOString() }