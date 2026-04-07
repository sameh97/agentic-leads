'use client'

export function HeroSection() {
  return (
    <section className="text-center py-16 pb-10">
      {/* Eyebrow */}
      <div className="flex items-center justify-center gap-2 mb-5 font-mono text-[12px] tracking-[2px] text-[var(--accent)] uppercase">
        <span className="w-[6px] h-[6px] rounded-full bg-[var(--accent)] animate-[pulse-dot_2s_ease-in-out_infinite]" />
        LangGraph · Waterfall Enrichment · Triple Verification
      </div>

      {/* Headline */}
      <h1 className="text-[clamp(38px,5vw,68px)] font-bold tracking-[-2px] leading-[1.04] mb-5">
        Type a sentence.<br />
        <span
          className="bg-clip-text text-transparent"
          style={{ backgroundImage: 'linear-gradient(90deg, var(--accent), var(--purple))' }}
        >
          Get verified leads.
        </span>
      </h1>

      <p className="text-[18px] text-[var(--muted)] max-w-[520px] mx-auto mb-10 leading-relaxed">
        AI parses your intent, scrapes Google Maps, enriches emails
        from 3 providers, and delivers a scored spreadsheet — in minutes.
      </p>

      {/* Stats */}
      <div className="flex justify-center gap-10 text-[13px] text-[var(--muted)]">
        {[
          { val: '~$0.015', label: 'per verified lead' },
          { val: '85%+',    label: 'email find rate' },
          { val: '6 nodes', label: 'LangGraph pipeline' },
        ].map(s => (
          <div key={s.label}>
            <strong className="block text-[26px] font-bold text-[var(--text)] leading-tight">
              {s.val}
            </strong>
            {s.label}
          </div>
        ))}
      </div>
    </section>
  )
}