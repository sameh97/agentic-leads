import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'LeadFlow — Prompt to Verified Leads',
  description: 'Type a sentence. Get verified sales leads. Powered by LangGraph.',
  icons: { icon: '/favicon.ico' },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  )
}