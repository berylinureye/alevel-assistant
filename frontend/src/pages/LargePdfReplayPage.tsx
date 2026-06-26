import { useState } from 'react'
import { LargePdfMode, type LargePdfAnalyzeContext } from '../components/largePdf/LargePdfMode'
import { largePdfReplayFixture } from '../fixtures/largePdfReplay'

export function LargePdfReplayPage() {
  const [lastSelection, setLastSelection] = useState<LargePdfAnalyzeContext | null>(null)

  return (
    <main className="min-h-screen bg-[radial-gradient(circle_at_top_left,#eff6ff_0,#f8fafc_34%,#f6f7f9_100%)] px-4 py-8 text-slate-950">
      <div className="mx-auto max-w-6xl space-y-4">
        <LargePdfMode
          session={largePdfReplayFixture}
          uploadIntent="past_paper"
          initialPaperCode="9709/11/M/J/22"
          initialQuestionNumbers="3, 4, 7"
          maxSelectedPages={24}
          onBack={() => setLastSelection(null)}
          onAnalyzeSelectedPages={setLastSelection}
        />

        {lastSelection ? (
          <div className="rounded-lg border border-slate-200 bg-white/90 px-4 py-3 text-sm text-slate-600">
            已选择 {lastSelection.selectedPages.length} 页：{lastSelection.selectedPages.join(', ')}
          </div>
        ) : null}
      </div>
    </main>
  )
}
