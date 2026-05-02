'use client'

const EXAMPLES = [
  'Plumbers in Chicago IL with owner email',
  'HVAC companies in Austin TX',
  'Dentists in Miami Florida',
  'Solar installers in Phoenix AZ',
  'Restaurants in Brooklyn NY',
]

interface Props {
  value:    string
  onChange: (v: string) => void
  onSubmit: () => void
  loading:  boolean
}

export function QueryInput({ value, onChange, onSubmit, loading }: Props) {
  return (
    <div id="search" className="query-card">
      <div className="query-label">Who are you looking for?</div>
      <div className="query-row">
        <input
          type="text"
          className="query-input"
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !loading && onSubmit()}
          placeholder='e.g. "Plumbers in Chicago with owner emails"'
        />
        <button
          className="btn-generate"
          onClick={onSubmit}
          disabled={loading || !value.trim()}
        >
          {loading ? '⏳ Finding leads…' : '🔍 Find Leads'}
        </button>
      </div>
      <div className="example-chips">
        <span className="example-chip-label">Try:</span>
        {EXAMPLES.map(ex => (
          <button key={ex} className="example-chip" onClick={() => onChange(ex)}>
            {ex}
          </button>
        ))}
      </div>
    </div>
  )
}