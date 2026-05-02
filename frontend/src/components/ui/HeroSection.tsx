'use client'

const STATS = [
  { val: '2 min',   label: 'avg. delivery time'   },
  { val: '85%+',    label: 'email find rate'       },
  { val: '100%',    label: 'verified before export' },
]

const LOGOS = ['Plumbers', 'HVAC', 'Dentists', 'Lawyers', 'Contractors', 'Restaurants', 'Electricians', 'Roofers']

export function HeroSection() {
  return (
    <section className="hero">
      {/* Eyebrow */}
      <div className="hero-eyebrow">
        <span className="eyebrow-dot" />
        Trusted by 500+ sales teams &amp; agencies
      </div>

      {/* Headline */}
      <h1>
        Find any business.<br />
        <span className="hero-gradient">Get their email. Close deals.</span>
      </h1>

      {/* Sub-headline */}
      <p className="hero-sub">
        Describe who you&apos;re targeting in plain English.
        We find the businesses, verify the contacts, and hand you
        a ready-to-send spreadsheet — in under 2 minutes.
      </p>

      {/* CTA row */}
      <div className="hero-cta-row">
        <a href="#search" className="btn-hero-primary">
          Try it free → 20 leads
        </a>
        <span className="hero-cta-note">No credit card · Results in 2 min</span>
      </div>

      {/* Stats Section */}
      <div className="hero-stats">
        {STATS.map(s => (
          <div className="hero-stat" key={s.label}>
            <strong>{s.val}</strong>
            <span>{s.label}</span>
          </div>
        ))}
      </div>

      {/* Concept Update: Infinite Marquee Ticker */}
      <div className="hero-ticker-wrap">
        <div className="hero-ticker-label">Works for niche industries like:</div>
        <div className="marquee-container">
          <div className="marquee-content">
            {/* We double the array to ensure seamless looping */}
            {[...LOGOS, ...LOGOS].map((l, i) => (
              <div key={i} className="ticker-item">
                <span className="ticker-bullet">•</span>
                {l}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  )
}