'use client'

import type { Lead } from '@/types/lead'
import type { JobStatus } from '@/hooks/useLeadJob'
import { LeadTable }  from './LeadTable'
import { LeadFooter } from './LeadFooter'

interface Props {
  status:    JobStatus
  leads:     Lead[]
  leadCount: number
  csvUrl:    string
  xlsxUrl:   string
  query:     string
}

export function ResultsPanel({ status, leads, leadCount, csvUrl, xlsxUrl, query }: Props) {
  const isDone    = status === 'done'
  const isFailed  = status === 'failed'
  const isRunning = status === 'running' || status === 'queued'

  const title = isDone
    ? `${leadCount} Verified Leads`
    : isFailed
    ? 'Pipeline Failed'
    : 'Running pipeline…'

  const meta = isDone
    ? `"${query}" · ${new Date().toLocaleTimeString()}`
    : isFailed
    ? 'Check your API keys and try a different query'
    : 'Processing your request…'

  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl overflow-hidden min-h-[400px] flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-[var(--border)] bg-[var(--panel)]">
        <div>
          <div className={`text-[15px] font-semibold ${isFailed ? 'text-[var(--red)]' : ''}`}>
            {title}
          </div>
          <div className="text-[12px] font-mono text-[var(--muted)] mt-[2px]">{meta}</div>
        </div>

        {isDone && (csvUrl || xlsxUrl) && (
          <div className="flex gap-2">
            {csvUrl && (
              <a
                href={csvUrl}
                download
                className="flex items-center gap-1.5 bg-[var(--panel)] border border-[var(--border2)] text-[var(--text)] rounded-lg px-3 py-[7px] text-[13px] font-semibold no-underline hover:border-[var(--accent)] hover:text-[var(--accent)] transition-all"
              >
                ⬇ CSV
              </a>
            )}
            {xlsxUrl && (
              <a
                href={xlsxUrl}
                download
                className="flex items-center gap-1.5 bg-[var(--panel)] border border-[rgba(0,230,118,0.3)] text-[var(--green)] rounded-lg px-3 py-[7px] text-[13px] font-semibold no-underline hover:border-[var(--green)] transition-all"
              >
                ⬇ XLSX
              </a>
            )}
          </div>
        )}
      </div>

      {/* Body */}
      <div className="flex-1">
        {leads.length > 0 ? (
          <LeadTable leads={leads} />
        ) : (
          <EmptyState status={status} />
        )}
      </div>

      {/* Footer */}
      {leads.length > 0 && <LeadFooter leads={leads} />}
    </div>
  )
}

function EmptyState({ status }: { status: JobStatus }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-20 text-[var(--muted)] text-center px-8">
      <div className="text-[48px] opacity-20">
        {status === 'failed' ? '⚠️' : '🔍'}
      </div>
      <div className="text-[15px] font-semibold text-[var(--muted)]">
        {status === 'failed'
          ? 'Pipeline encountered an error'
          : status === 'running' || status === 'queued'
          ? 'Leads will appear here as the pipeline runs…'
          : 'No leads yet'}
      </div>
      <div className="text-[13px]">
        {status === 'failed'
          ? 'Make sure OPENAI_API_KEY is set in your .env file'
          : 'Results will populate after the enrichment and scoring steps complete'}
      </div>
    </div>
  )
}