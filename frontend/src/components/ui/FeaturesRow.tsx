'use client'

const FEATURES = [
  {
    icon: '⚡',
    title: 'Results in under 2 minutes',
    desc:  'Type what you need. We handle the research. Get a complete, ready-to-use lead list faster than a Google search.',
  },
  {
    icon: '✅',
    title: 'Every email verified',
    desc:  'No bounced emails. No wasted outreach. Every contact is checked against live mail servers before it reaches you.',
  },
  {
    icon: '🎯',
    title: 'Owner-level contacts',
    desc:  'We surface decision-makers — owners, CEOs, founders — not generic info@ addresses that go nowhere.',
  },
  {
    icon: '📍',
    title: 'Any city, any niche',
    desc:  'Plumbers in Chicago. Dentists in Dubai. Solar installers in Phoenix. If it\'s on Google Maps, we can find it.',
  },
  {
    icon: '📊',
    title: 'Scored & ranked for you',
    desc:  'Leads arrive sorted by quality. Best prospects at the top. Lowest quality filtered out. No manual sorting needed.',
  },
  {
    icon: '📥',
    title: 'Download & use instantly',
    desc:  'Export to CSV or Excel. Import straight into your CRM, email tool, or outreach sequence. Zero friction.',
  },
]

export function FeaturesRow() {
  return (
    <div className="features-grid">
      {FEATURES.map(f => (
        <div key={f.title} className="feat-card">
          <div className="feat-icon">{f.icon}</div>
          <div className="feat-title">{f.title}</div>
          <div className="feat-desc">{f.desc}</div>
        </div>
      ))}
    </div>
  )
}