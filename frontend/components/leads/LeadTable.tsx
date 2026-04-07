'use client'

import type { Lead } from '@/types/lead'
import clsx from 'clsx'

interface Props {
  leads: Lead[]
}

function ScorePill({ score }: { score: number }) {
  return (
    <span className={clsx(
      'inline-flex items-center justify-center font-mono text-[12px] font-bold px-2 py-[3px] rounded-md min-w-[42px]',
      score >= 70 && 'bg-[rgba(0,230,118,0.12)] text-[#00e676]',
      score >= 40 && score < 70 && 'bg-[rgba(255,179,0,0.12)] text-[#ffb300]',
      score < 40  && 'bg-[rgba(255,82,82,0.12)]  text-[#ff5252]',
    )}>
      {score}
    </span>
  )
}

function VerifyBadge({ lead }: { lead: Lead }) {
  const cls = lead.email_verified
    ? 'bg-[rgba(0,230,118,0.1)] text-[#00e676]'
    : lead.email_catchall
    ? 'bg-[rgba(255,179,0,0.1)] text-[#ffb300]'
    : 'bg-[rgba(107,124,143,0.15)] text-[#6b7c8f]'

  const label = lead.email_verified
    ? '✓ valid'
    : lead.email_catchall
    ? '~ catch-all'
    : lead.email_status || 'unknown'

  return (
    <span className={clsx('inline-flex items-center gap-1 text-[10px] font-bold font-mono px-2 py-[2px] rounded', cls)}>
      {label}
    </span>
  )
}

function Stars({ rating }: { rating: number }) {
  const full  = Math.round(rating)
  const empty = 5 - full
  return (
    <span className="text-[11px] tracking-tight">
      <span className="text-[#ffb300]">{'★'.repeat(full)}</span>
      <span className="text-[var(--border2)]">{'★'.repeat(empty)}</span>
    </span>
  )
}

const COLS = [
  { key: 'score',   label: 'Score',    w: '70px'  },
  { key: 'name',    label: 'Business', w: 'auto'  },
  { key: 'email',   label: 'Email',    w: '220px' },
  { key: 'status',  label: 'Status',   w: '110px' },
  { key: 'rating',  label: 'Rating',   w: '130px' },
  { key: 'phone',   label: 'Phone',    w: '140px' },
]

export function LeadTable({ leads }: Props) {
  return (
    <div className="overflow-x-auto w-full animate-fade-in">
      <table className="w-full border-collapse text-[13px]">
        <thead>
          <tr>
            {COLS.map(c => (
              <th
                key={c.key}
                style={{ width: c.w }}
                className="bg-[var(--panel)] px-4 py-[10px] text-left text-[10px] font-bold tracking-[1px] uppercase text-[var(--muted)] border-b border-[var(--border)] whitespace-nowrap"
              >
                {c.label}
              </th>
            ))}
          </tr>
        </thead>

        <tbody>
          {leads.map((lead, i) => (
            <tr
              key={i}
              className="border-b border-[rgba(30,42,54,0.5)] hover:bg-[rgba(255,255,255,0.015)] transition-colors group"
            >
              {/* Score */}
              <td className="px-4 py-[11px]">
                <ScorePill score={lead.score} />
              </td>

              {/* Business name + address */}
              <td className="px-4 py-[11px]">
                <div className="font-semibold text-[var(--text)] leading-tight">
                  {lead.name}
                </div>
                <div className="text-[11px] text-[var(--muted)] mt-[2px] truncate max-w-[200px]">
                  {lead.address
                    ? lead.address.split(',').slice(-2).join(',').trim()
                    : '—'}
                </div>
                {lead.owner_name && (
                  <div className="text-[10px] font-mono text-[#b388ff] mt-[2px]">
                    {lead.owner_name}
                    {lead.owner_position ? ` · ${lead.owner_position}` : ''}
                  </div>
                )}
              </td>

              {/* Email */}
              <td className="px-4 py-[11px]">
                <span className="font-mono text-[12px] text-[var(--accent)] truncate block max-w-[200px]">
                  {lead.primary_email || '—'}
                </span>
              </td>

              {/* Verification status */}
              <td className="px-4 py-[11px]">
                <VerifyBadge lead={lead} />
              </td>

              {/* Rating + reviews */}
              <td className="px-4 py-[11px]">
                {lead.rating ? (
                  <div className="flex items-center gap-1.5">
                    <Stars rating={lead.rating} />
                    <span className="text-[11px] font-mono text-[var(--muted)]">
                      {lead.review_count ? `(${lead.review_count})` : ''}
                    </span>
                  </div>
                ) : '—'}
              </td>

              {/* Phone */}
              <td className="px-4 py-[11px]">
                <span className="font-mono text-[11px] text-[var(--muted)]">
                  {lead.phone || '—'}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}