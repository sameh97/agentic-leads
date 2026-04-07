'use client'

import type { NodeState } from '@/hooks/useLeadJob'
import type { PipelineEvent } from '@/lib/api'
import clsx from 'clsx'

interface Props {
  nodes:  NodeState[]
  events: PipelineEvent[]
}

export function PipelinePanel({ nodes, events }: Props) {
  return (
    <div className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-5 sticky top-[72px]">
      <div className="text-[11px] font-bold tracking-[1.5px] uppercase text-[var(--muted)] mb-4">
        Pipeline Status
      </div>

      <div className="flex flex-col">
        {nodes.map((node, i) => (
          <div key={node.id} className={clsx('flex gap-3 py-3', i < nodes.length - 1 && 'border-b border-[var(--border)]')}>
            {/* Indicator */}
            <div
              className={clsx(
                'w-7 h-7 rounded-full flex items-center justify-center flex-shrink-0 text-[11px] font-bold font-mono border transition-all duration-300',
                node.status === 'idle'   && 'border-[var(--border2)] text-[var(--muted)] bg-[var(--panel)]',
                node.status === 'active' && 'border-[var(--accent)] text-[var(--accent)] bg-[rgba(0,212,255,0.08)] animate-[spin-ring_1.2s_ease-in-out_infinite]',
                node.status === 'done'   && 'border-[var(--green)]  text-[var(--green)]  bg-[rgba(0,230,118,0.08)]',
                node.status === 'error'  && 'border-[var(--red)]    text-[var(--red)]    bg-[rgba(255,82,82,0.08)]',
              )}
            >
              {node.status === 'done'  ? '✓' :
               node.status === 'error' ? '✗' :
               node.status === 'active'? '◉' : i + 1}
            </div>

            {/* Text */}
            <div className="flex-1 min-w-0">
              <div className={clsx(
                'text-[13px] font-semibold mb-[2px] transition-colors',
                node.status === 'active' && 'text-[var(--accent)]',
                node.status === 'done'   && 'text-[var(--text)]',
                node.status === 'error'  && 'text-[var(--red)]',
                node.status === 'idle'   && 'text-[var(--muted)]',
              )}>
                {node.icon} {node.label}
              </div>
              <div className="text-[11px] font-mono text-[var(--muted)] truncate">
                {node.detail}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Event log */}
      {events.length > 0 && (
        <div className="mt-4 border-t border-[var(--border)] pt-4">
          <div className="text-[10px] font-bold tracking-[1.5px] uppercase text-[var(--muted)] mb-3">
            Event Log
          </div>
          <div className="flex flex-col gap-[5px] max-h-48 overflow-y-auto">
            {events.filter(e => e.message).slice(-12).map((ev, i) => (
              <div key={i} className="flex gap-2 text-[10px] font-mono">
                <span className="text-[var(--border2)] flex-shrink-0">
                  {new Date(ev.ts).toLocaleTimeString('en-US', { hour12: false })}
                </span>
                <span className="text-[var(--accent)] flex-shrink-0 min-w-[80px]">
                  {ev.node}
                </span>
                <span className="text-[var(--muted)] truncate">{ev.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}