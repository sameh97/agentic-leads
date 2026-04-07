'use client'

import type { Lead } from '@/types/lead'

interface Props { leads: Lead[] }

export function LeadFooter({ leads }: Props) {
  const high = leads.filter(l => l.score >= 70).length
  const mid  = leads.filter(l => l.score >= 40 && l.score < 70).length
  const low  = leads.filter(l => l.score < 40).length
  const verified  = leads.filter(l => l.email_verified).length
  const catchall  = leads.filter(l => l.email_catchall).length

  return (
    <div className="flex items-center gap-6 px-5 py-3 border-t border-[var(--border)] bg-[var(--panel)] text-[12px] text-[var(--muted)] flex-wrap">
      <StatDot color="#00e676" count={high}     label="high (≥70)" />
      <StatDot color="#ffb300" count={mid}      label="medium (40–69)" />
      <StatDot color="#ff5252" count={low}      label="low (<40)" />
      <div className="w-px h-4 bg-[var(--border)] mx-1" />
      <StatDot color="#00d4ff" count={verified}  label="verified email" />
      <StatDot color="#ffb300" count={catchall}  label="catch-all" />
      <div className="ml-auto font-mono text-[11px]">
        {leads.length} total leads
      </div>
    </div>
  )
}

function StatDot({ color, count, label }: { color: string; count: number; label: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: color }} />
      <span className="font-bold font-mono" style={{ color: 'var(--text)' }}>{count}</span>
      <span>{label}</span>
    </div>
  )
}