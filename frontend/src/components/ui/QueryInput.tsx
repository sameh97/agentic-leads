'use client'

const EXAMPLES = [
  'HVAC companies in Austin TX with owner emails',
  'Plumbers in Chicago with verified email',
  'Dentists in Miami Florida',
  'Restaurants in Seattle WA',
  'Solar installers in Phoenix AZ',
]

interface Props {
  value:    string
  onChange: (v: string) => void
  onSubmit: () => void
  loading:  boolean
}

export function QueryInput({ value, onChange, onSubmit, loading }: Props) {
  return (
    <div className="bg-[var(--surface)] border border-[var(--border2)] rounded-2xl p-7 mb-5 shadow-[0_0_60px_rgba(0,212,255,0.04)]">
      <div className="text-[11px] font-bold tracking-[1px] uppercase text-[var(--muted)] mb-3">
        Natural language query
      </div>

      <div className="flex gap-3">
        <input
          type="text"
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !loading && onSubmit()}
          placeholder='e.g. "Find HVAC companies in Austin TX with owner emails"'
          className="
            flex-1 bg-[var(--panel)] border border-[var(--border2)] rounded-xl
            px-5 py-4 text-base text-[var(--text)] font-sans outline-none
            placeholder:text-[var(--muted)]
            focus:border-[var(--accent)] focus:shadow-[0_0_0_3px_rgba(0,212,255,0.1)]
            transition-all duration-200
          "
        />
        <button
          onClick={onSubmit}
          disabled={loading || !value.trim()}
          className="
            bg-gradient-to-br from-[var(--accent)] to-[var(--accent2)]
            text-black font-bold text-[15px] rounded-xl px-7 min-w-[160px]
            transition-all duration-150 cursor-pointer
            hover:opacity-90 active:scale-[0.98]
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        >
          {loading ? '⏳ Running…' : '⚡ Generate Leads'}
        </button>
      </div>

      {/* Example chips */}
      <div className="flex flex-wrap gap-2 mt-4">
        {EXAMPLES.map(ex => (
          <button
            key={ex}
            onClick={() => onChange(ex)}
            className="
              font-mono text-[11px] px-3 py-[5px] rounded-full
              bg-[var(--panel)] border border-[var(--border)]
              text-[var(--muted)] cursor-pointer
              hover:border-[var(--accent)] hover:text-[var(--accent)]
              hover:bg-[rgba(0,212,255,0.05)]
              transition-all duration-150
            "
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  )
}