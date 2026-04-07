'use client'

const FEATURES = [
  {
    icon: '🧠',
    title: 'LangGraph Orchestration',
    desc:  '6-node stateful pipeline with automatic retry loops. If enrichment fails, the graph re-routes — never a dead end.',
  },
  {
    icon: '🔍',
    title: '3-Provider Waterfall',
    desc:  'Website scrape → Hunter.io → Apollo.io. Only charges paid APIs when free scraping comes up empty.',
  },
  {
    icon: '✅',
    title: 'Triple Verification',
    desc:  'Syntax regex, DNS MX lookup, then SMTP handshake via ZeroBounce. Catch-all domains flagged separately.',
  },
  {
    icon: '⭐',
    title: 'Lead Scoring',
    desc:  'Every lead scored 0-100 on rating, reviews, email quality, and contact seniority. Sorted before delivery.',
  },
  {
    icon: '📥',
    title: 'CSV + XLSX Export',
    desc:  'Color-coded spreadsheet (green/amber/red by score) and a clean CSV, both downloadable instantly.',
  },
  {
    icon: '📡',
    title: 'Live SSE Streaming',
    desc:  'FastAPI server-sent events stream node-by-node progress to the UI in real time — no polling needed.',
  },
]

export function FeaturesRow() {
  return (
    <div className="grid grid-cols-3 gap-4 pb-16">
      {FEATURES.map(f => (
        <div
          key={f.title}
          className="bg-[var(--surface)] border border-[var(--border)] rounded-2xl p-6 hover:border-[var(--border2)] transition-colors"
        >
          <div className="w-10 h-10 rounded-xl bg-[var(--panel)] border border-[var(--border2)] flex items-center justify-center text-xl mb-4">
            {f.icon}
          </div>
          <div className="font-semibold text-[15px] mb-2">{f.title}</div>
          <div className="text-[13px] text-[var(--muted)] leading-relaxed">{f.desc}</div>
        </div>
      ))}
    </div>
  )
}