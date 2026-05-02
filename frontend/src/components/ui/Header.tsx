'use client'

export function Header() {
  return (
    <header className="sticky top-0 z-50 border-b border-[var(--border)] bg-[rgba(8,12,16,0.92)] backdrop-blur-xl">
      <div className="flex items-center justify-between py-[18px]">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-[var(--accent)] to-[var(--accent2)] flex items-center justify-center text-black font-bold text-sm">
            ⚡
          </div>
          <span className="text-[20px] font-bold tracking-tight">
            Lead<span className="text-[var(--accent)]">Flow</span>
          </span>
          <span className="text-[11px] font-semibold tracking-wide px-2 py-[3px] rounded bg-[rgba(0,212,255,0.08)] text-[var(--accent)] border border-[rgba(0,212,255,0.2)]">
            BETA
          </span>
        </div>

        {/* Nav */}
        {/* <nav className="flex gap-6 text-sm text-[var(--muted)]">
          {['Pricing', 'Docs', 'API', 'GitHub'].map(l => (
            <a key={l} href="#" className="hover:text-[var(--text)] transition-colors">{l}</a>
          ))}
        </nav> */}
      </div>
    </header>
  )
}