import { useEffect } from 'react'
import { Nav } from './components/Nav'
import { Hero } from './components/Hero'
import { HowItWorks } from './components/HowItWorks'
import { Features } from './components/Features'
import { Demo } from './components/Demo'
import { Comparison } from './components/Comparison'
import { FAQ } from './components/FAQ'
import { FinalCTA } from './components/FinalCTA'
import { Footer } from './components/Footer'

export default function LandingPage() {
  // Update the document title for /landing context (keep tab clean on navigation).
  useEffect(() => {
    const prev = document.title
    document.title = 'A-Level 作业助手 · 按 CAIE mark scheme 批改'
    return () => {
      document.title = prev
    }
  }, [])

  return (
    <div className="min-h-screen bg-white text-[color:var(--color-ink-900)] antialiased">
      <Nav />
      <main>
        <Hero />
        <HowItWorks />
        <Features />
        <Demo />
        <Comparison />
        <FAQ />
        <FinalCTA />
      </main>
      <Footer />
    </div>
  )
}
