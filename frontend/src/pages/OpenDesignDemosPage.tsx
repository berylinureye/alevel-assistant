import heroStackUrl from '../assets/hero.png'

const valuePoints = [
  {
    label: 'For students',
    title: '把扣分点讲清楚',
    text: '不是只给分数，而是把 mark scheme、答案步骤和下一步订正放在同一个视野里。',
  },
  {
    label: 'For tutors',
    title: '先找依据再批改',
    text: '自动判断作业、Past Paper、答案页；能匹配 CAIE 9709 时优先对照规则。',
  },
  {
    label: 'For review',
    title: '从一次作业到练习闭环',
    text: '报告直接沉淀薄弱点、复核题和同主题练习，不让批改停在“看过了”。',
  },
]

const pipeline = [
  ['01', 'Intake', '图片 / PDF / paper code'],
  ['02', 'Resolver', '匹配题号与 mark scheme'],
  ['03', 'Grading', '多 Agent 交叉批改'],
  ['04', 'Practice', '生成订正与练习'],
]

const scoreCards = [
  ['17/25', '本次得分'],
  ['68%', '得分率'],
  ['3', '优先订正'],
]

function ArrowIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
      <path d="M5 12h14" strokeLinecap="round" />
      <path d="m13 6 6 6-6 6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function SparkIcon() {
  return (
    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden>
      <path d="M12 3l1.5 5.2L19 10l-5.5 1.8L12 17l-1.5-5.2L5 10l5.5-1.8L12 3Z" strokeLinejoin="round" />
      <path d="M19 15l.7 2.3L22 18l-2.3.7L19 21l-.7-2.3L16 18l2.3-.7L19 15Z" strokeLinejoin="round" />
    </svg>
  )
}

function ProductPreview() {
  return (
    <section className="relative min-w-0 border border-white/10 bg-white/[0.045] p-3 shadow-[0_24px_90px_rgba(0,0,0,0.36)] backdrop-blur">
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <div>
          <p className="text-[11px] font-medium uppercase text-cyan-200">Live workbench preview</p>
          <h2 className="mt-1 text-base font-semibold text-white">A-Level Maths 9709 · Paper 12</h2>
        </div>
        <span className="border border-emerald-300/25 bg-emerald-300/10 px-2 py-1 text-xs font-medium text-emerald-200">
          ready
        </span>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-[0.92fr_1.08fr]">
        <div className="min-w-0 border border-white/10 bg-[#050816] p-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] uppercase text-slate-500">Upload</p>
              <p className="mt-1 text-sm font-semibold text-white">作业图片已识别</p>
            </div>
            <span className="bg-cyan-300 px-2 py-1 text-xs font-semibold text-slate-950">PDF</span>
          </div>
          <div className="mt-4 overflow-hidden border border-white/10 bg-slate-950">
            <img src={heroStackUrl} alt="" className="h-36 w-full object-contain p-4 opacity-90" />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <div className="border border-white/10 bg-white/[0.04] px-3 py-2">
              <p className="text-slate-500">Paper</p>
              <p className="mt-1 font-semibold text-slate-100">9709/12</p>
            </div>
            <div className="border border-white/10 bg-white/[0.04] px-3 py-2">
              <p className="text-slate-500">Questions</p>
              <p className="mt-1 font-semibold text-slate-100">Q3, Q5, Q7</p>
            </div>
          </div>
        </div>

        <div className="min-w-0 space-y-3">
          <div className="grid grid-cols-3 gap-2">
            {scoreCards.map(([value, label]) => (
              <div key={label} className="border border-white/10 bg-white/[0.055] p-3">
                <p className="text-xl font-semibold text-white">{value}</p>
                <p className="mt-1 text-xs text-slate-400">{label}</p>
              </div>
            ))}
          </div>

          <div className="border border-white/10 bg-white/[0.04] p-3">
            <div className="flex items-center justify-between gap-3">
              <p className="text-sm font-semibold text-white">Agent workflow</p>
              <span className="text-xs text-slate-500">4 steps</span>
            </div>
            <div className="mt-3 space-y-2">
              {pipeline.map(([step, title, text], index) => (
                <div key={step} className="grid grid-cols-[2rem_minmax(0,1fr)] gap-3">
                  <span className={`flex h-8 w-8 items-center justify-center border text-xs font-semibold ${index < 3 ? 'border-cyan-200/40 bg-cyan-200/10 text-cyan-100' : 'border-white/10 bg-white/[0.04] text-slate-400'}`}>
                    {step}
                  </span>
                  <div className="min-w-0 border-b border-white/8 pb-2 last:border-b-0 last:pb-0">
                    <p className="text-sm font-semibold text-slate-100">{title}</p>
                    <p className="mt-0.5 truncate text-xs text-slate-500">{text}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="border border-amber-200/20 bg-amber-200/[0.08] p-3">
            <p className="text-xs font-medium uppercase text-amber-200">Priority correction</p>
            <p className="mt-2 text-sm font-semibold text-white">Q7 · Integration bounds</p>
            <p className="mt-1 text-xs leading-5 text-slate-400">
              方法分已拿到，主要失分来自上下限方向。下一步推荐 3 道同类题。
            </p>
          </div>
        </div>
      </div>
    </section>
  )
}

export function OpenDesignDemosPage() {
  return (
    <main className="min-h-screen overflow-hidden bg-[#010120] text-white">
      <div className="pointer-events-none fixed inset-0 bg-[linear-gradient(rgba(255,255,255,0.035)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.035)_1px,transparent_1px)] bg-[size:48px_48px]" aria-hidden />
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_top,rgba(125,211,252,0.16),transparent_42%),linear-gradient(180deg,rgba(1,1,32,0)_0%,rgba(1,1,32,0.82)_100%)]" aria-hidden />

      <div className="relative z-10 mx-auto flex min-h-screen w-full max-w-7xl flex-col px-4 pb-24 pt-5 sm:px-6 lg:px-8">
        <header className="flex items-center justify-between gap-4 border-b border-white/10 pb-4">
          <div className="flex min-w-0 items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center border border-cyan-200/25 bg-cyan-200/10 text-cyan-100">
              <SparkIcon />
            </span>
            <div className="min-w-0">
              <p className="text-sm font-semibold text-white">A-Level Assistant</p>
              <p className="text-xs text-slate-500">Open Design × 21st.dev cover demo</p>
            </div>
          </div>
          <a
            href="/"
            className="hidden border border-white/10 bg-white/[0.04] px-3 py-2 text-sm font-medium text-slate-300 transition hover:border-white/20 hover:bg-white/[0.07] hover:text-white sm:inline-flex"
          >
            返回当前产品
          </a>
        </header>

        <section className="grid flex-1 gap-8 py-8 lg:grid-cols-[minmax(0,0.88fr)_minmax(440px,1fr)] lg:items-center lg:py-10">
          <div className="min-w-0">
            <div className="inline-flex items-center gap-2 border border-white/10 bg-white/[0.045] px-3 py-1.5 text-xs font-medium text-slate-300">
              <span className="h-1.5 w-1.5 bg-emerald-300 shadow-[0_0_18px_rgba(110,231,183,0.7)]" aria-hidden />
              built for A-Level maths correction
            </div>
            <h1 className="mt-6 max-w-4xl text-5xl font-medium tracking-normal text-white sm:text-6xl lg:text-7xl">
              A-Level Assistant
            </h1>
            <p className="mt-4 text-3xl font-medium tracking-normal text-slate-100 sm:text-4xl">
              先找依据，再批改作业。
            </p>
            <p className="mt-6 max-w-2xl text-base leading-8 text-slate-300 sm:text-lg">
              面向 A-Level 数学学生、老师与助教的批改入口。上传作业或真题 PDF 后，系统先识别材料、匹配 mark scheme，再进入逐题批改和练习建议。
            </p>

            <div className="mt-8 grid gap-3 sm:grid-cols-3">
              {valuePoints.map((point) => (
                <article
                  key={point.title}
                  className="group min-w-0 border border-white/10 bg-white/[0.04] p-4 transition duration-200 hover:-translate-y-0.5 hover:border-cyan-200/45 hover:bg-white/[0.065] hover:shadow-[0_0_32px_rgba(34,211,238,0.12)]"
                >
                  <p className="text-xs font-medium text-cyan-200">{point.label}</p>
                  <h2 className="mt-3 text-sm font-semibold text-white">{point.title}</h2>
                  <p className="mt-2 text-sm leading-6 text-slate-400">{point.text}</p>
                </article>
              ))}
            </div>
          </div>

          <ProductPreview />
        </section>

        <footer className="border-t border-white/10 pt-4">
          <p className="text-xs leading-5 text-slate-500">
            Demo only · shadcn-like sharp components, Linear-style dark product surface, Together AI-style research atmosphere.
          </p>
        </footer>
      </div>

      <button
        type="button"
        className="fixed bottom-4 right-4 z-20 inline-flex min-h-12 items-center justify-center gap-2 border border-amber-200/70 bg-amber-300 px-4 text-sm font-semibold text-slate-950 shadow-[0_0_34px_rgba(252,211,77,0.28)] transition hover:-translate-y-0.5 hover:bg-amber-200 focus:outline-none focus:ring-2 focus:ring-amber-200 focus:ring-offset-2 focus:ring-offset-[#010120] sm:bottom-5 sm:right-5"
      >
        开始批改作业
        <ArrowIcon />
      </button>
    </main>
  )
}
