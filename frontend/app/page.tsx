'use client'

import { useState } from 'react'
import { Header }          from '@/components/ui/Header'
import { HeroSection }     from '@/components/ui/HeroSection'
import { QueryInput }      from '@/components/ui/QueryInput'
import { PipelinePanel }   from '@/components/pipeline/PipelinePanel'
import { ResultsPanel }    from '@/components/leads/ResultsPanel'
import { FeaturesRow }     from '@/components/ui/FeaturesRow'
import { useLeadJob }      from '@/hooks/useLeadJob'

export default function HomePage() {
  const [query, setQuery] = useState('')
  const { status, nodes, events, leads, leadCount, csvUrl, xlsxUrl, run } = useLeadJob()
  const hasJob = status !== 'idle'

  return (
    <div className="relative z-10 max-w-[1100px] mx-auto px-6">
      <Header />

      <HeroSection />

      <QueryInput
        value={query}
        onChange={setQuery}
        onSubmit={() => run(query)}
        loading={status === 'running' || status === 'queued'}
      />

      {hasJob && (
        <div
          className="grid gap-5 mb-12 animate-slide-up"
          style={{ gridTemplateColumns: '280px 1fr' }}
        >
          <PipelinePanel nodes={nodes} events={events} />
          <ResultsPanel
            status={status}
            leads={leads}
            leadCount={leadCount}
            csvUrl={csvUrl}
            xlsxUrl={xlsxUrl}
            query={query}
          />
        </div>
      )}

      {!hasJob && <FeaturesRow />}
    </div>
  )
}