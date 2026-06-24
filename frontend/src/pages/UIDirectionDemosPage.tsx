const topicRows = [
  { name: 'Logarithms', status: 'needs review', score: '3/5', tone: 'amber' },
  { name: 'Quadratics', status: 'secure', score: '4/4', tone: 'emerald' },
  { name: 'Integration', status: 'practice next', score: '2/6', tone: 'rose' },
]

const workflowSteps = ['识别上传类型', '匹配真题', '提取答案', '交叉检查', '生成反馈']

const questionRows = [
  { q: 'Q3', score: '3/5', state: '漏写条件', confidence: '中' },
  { q: 'Q5', score: '4/4', state: '完整正确', confidence: '高' },
  { q: 'Q7', score: '2/6', state: '积分上下限错误', confidence: '高' },
]

const demoMeta = [
  {
    id: 'dashboard',
    title: 'A. Study Command Center',
    category: 'Dashboard / Analytics / Tables',
    bestFor: '老师、重度刷题学生、需要快速扫弱点的人',
    verdict: '信息密度最高，最像“学习操作台”。',
  },
  {
    id: 'tutor',
    title: 'B. AI Tutor Split View',
    category: 'AI Chat / Tabs / Cards',
    bestFor: '学生追问、错题讲解、把批改转成辅导对话',
    verdict: '情绪最友好，产品差异化最强。',
  },
  {
    id: 'intake',
    title: 'C. Paper Intake Flow',
    category: 'File Uploads / Forms / Workflow',
    bestFor: '首次上传、PDF 真题、降低“我该传什么”的不确定',
    verdict: '最适合改造当前首屏上传体验。',
  },
  {
    id: 'clinic',
    title: 'D. Exam Clinic Cards',
    category: 'Cards / Tabs / Badges / Empty States',
    bestFor: '移动端结果页、错题订正、家长或老师快速复核',
    verdict: '最稳妥，落地成本低，风险小。',
  },
]

function ToneDot({ tone }: { tone: string }) {
  const classes: Record<string, string> = {
    amber: 'bg-amber-400',
    emerald: 'bg-emerald-500',
    rose: 'bg-rose-500',
    blue: 'bg-blue-500',
  }

  return <span className={`h-2.5 w-2.5 rounded-full ${classes[tone] ?? classes.blue}`} aria-hidden />
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">
      {children}
    </p>
  )
}

function DemoShell({
  id,
  title,
  category,
  children,
}: {
  id: string
  title: string
  category: string
  children: React.ReactNode
}) {
  return (
    <section id={id} className="scroll-mt-4 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div>
          <h2 className="text-base font-semibold text-slate-950">{title}</h2>
          <p className="mt-0.5 text-xs text-slate-500">{category}</p>
        </div>
        <span className="rounded-md border border-blue-200 bg-blue-50 px-2.5 py-1 text-xs font-semibold text-blue-700">
          A-Level Assistant
        </span>
      </div>
      {children}
    </section>
  )
}

function DashboardDemo() {
  return (
    <DemoShell id="dashboard" title="A. Study Command Center" category="21st: Dashboard / Analytics / Tables">
      <div className="grid min-h-[560px] bg-slate-50 lg:grid-cols-[184px_minmax(0,1fr)]">
        <aside className="border-b border-slate-200 bg-slate-950 p-4 text-white lg:border-b-0 lg:border-r">
          <p className="text-sm font-semibold">A-Level Assistant</p>
          <nav className="mt-6 grid grid-cols-2 gap-2 text-xs text-slate-300 lg:grid-cols-1">
            {['批改', '真题库', '弱点', '练习', '学生档案'].map((item, index) => (
              <span
                key={item}
                className={`rounded-md px-3 py-2 ${index === 0 ? 'bg-white text-slate-950' : 'bg-white/5'}`}
              >
                {item}
              </span>
            ))}
          </nav>
        </aside>

        <div className="space-y-4 p-4">
          <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <SectionLabel>本次表现</SectionLabel>
              <div className="mt-3 grid gap-3 sm:grid-cols-4">
                {[
                  ['68%', '得分率'],
                  ['7', '已批改题目'],
                  ['3', '需要订正'],
                  ['1', '老师复核'],
                ].map(([value, label]) => (
                  <div key={label} className="rounded-md border border-slate-200 bg-slate-50 p-3">
                    <p className="text-2xl font-semibold text-slate-950">{value}</p>
                    <p className="mt-1 text-xs text-slate-500">{label}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-lg border border-blue-200 bg-blue-50 p-4">
              <SectionLabel>下一步</SectionLabel>
              <p className="mt-3 text-sm font-semibold text-slate-950">今晚优先练 Integration</p>
              <p className="mt-2 text-sm leading-6 text-slate-600">先复盘上下限，再做 3 道 exam-style。</p>
            </div>
          </div>

          <div className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(280px,0.9fr)]">
            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <div className="flex items-center justify-between gap-3">
                <SectionLabel>主要问题</SectionLabel>
                <span className="text-xs text-slate-500">CAIE 9709 / Paper 12</span>
              </div>
              <div className="mt-4 space-y-3">
                {topicRows.map((topic) => (
                  <div key={topic.name} className="grid grid-cols-[minmax(0,1fr)_80px] items-center gap-3">
                    <div className="min-w-0">
                      <div className="mb-1 flex items-center gap-2">
                        <ToneDot tone={topic.tone} />
                        <p className="truncate text-sm font-semibold text-slate-900">{topic.name}</p>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className={`h-full rounded-full ${
                            topic.tone === 'emerald'
                              ? 'w-4/5 bg-emerald-500'
                              : topic.tone === 'amber'
                                ? 'w-3/5 bg-amber-400'
                                : 'w-2/5 bg-rose-500'
                          }`}
                        />
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm font-semibold text-slate-950">{topic.score}</p>
                      <p className="text-[11px] text-slate-500">{topic.status}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-4">
              <SectionLabel>批改队列</SectionLabel>
              <div className="mt-4 overflow-hidden rounded-md border border-slate-200">
                {questionRows.map((row) => (
                  <div key={row.q} className="grid grid-cols-[44px_1fr_48px] gap-2 border-b border-slate-100 px-3 py-3 text-sm last:border-b-0">
                    <span className="font-semibold text-slate-950">{row.q}</span>
                    <span className="min-w-0 truncate text-slate-600">{row.state}</span>
                    <span className="text-right font-medium text-slate-950">{row.score}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <SectionLabel>推荐练习</SectionLabel>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              {['基础巩固 · 12 分钟', '同主题真题 · 18 分钟', '混合小测 · 25 分钟'].map((item) => (
                <button key={item} type="button" className="rounded-md border border-slate-200 bg-white px-3 py-3 text-left text-sm font-medium text-slate-800 hover:border-blue-300 hover:bg-blue-50">
                  {item}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </DemoShell>
  )
}

function TutorDemo() {
  return (
    <DemoShell id="tutor" title="B. AI Tutor Split View" category="21st: AI Chat / Tabs / Cards">
      <div className="grid min-h-[560px] gap-0 bg-stone-50 lg:grid-cols-[minmax(0,0.95fr)_minmax(360px,1.05fr)]">
        <div className="border-b border-slate-200 p-4 lg:border-b-0 lg:border-r">
          <SectionLabel>题目诊断</SectionLabel>
          <div className="mt-4 rounded-lg border border-slate-200 bg-white p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xl font-semibold text-slate-950">Q7</span>
              <span className="rounded-md bg-rose-50 px-2 py-1 text-xs font-semibold text-rose-700 ring-1 ring-rose-200">2 / 6</span>
              <span className="rounded-md bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-700 ring-1 ring-amber-200">AI 置信度：高</span>
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-600">
              你用了正确的积分方法，但把阴影区域的上下限写反，导致面积符号和最终答案都偏了。
            </p>
          </div>

          <div className="mt-4 rounded-lg border border-slate-200 bg-white p-4">
            <SectionLabel>Mark Scheme 对齐</SectionLabel>
            <ol className="mt-4 space-y-3">
              {['M1 建立正确积分表达式', 'A1 写出正确上下限', 'B1 最终面积取正值'].map((item, index) => (
                <li key={item} className="flex gap-3 text-sm">
                  <span className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[11px] font-bold ${index === 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                    {index === 0 ? '✓' : '!'}
                  </span>
                  <span className="text-slate-700">{item}</span>
                </li>
              ))}
            </ol>
          </div>
        </div>

        <div className="flex min-h-[560px] flex-col bg-white">
          <div className="border-b border-slate-200 px-4 py-3">
            <SectionLabel>AI 老师对话</SectionLabel>
            <h3 className="mt-1 text-lg font-semibold text-slate-950">把“哪里错了”讲到会为止</h3>
          </div>
          <div className="flex-1 space-y-3 p-4">
            <div className="max-w-[82%] rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
              为什么我明明积分式写对了，还是只拿 2 分？
            </div>
            <div className="ml-auto max-w-[88%] rounded-lg bg-blue-600 px-3 py-2 text-sm leading-6 text-white">
              方法分拿到了，但 A1 要求上下限和区域方向一致。你这里从右边界积分到左边界，所以面积变成负值。
            </div>
            <div className="ml-auto max-w-[88%] rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-sm leading-6 text-slate-700">
              可以这样修正：先画交点，再按左到右写区间，最后对“上函数减下函数”做检查。
            </div>
          </div>
          <div className="border-t border-slate-200 p-4">
            <div className="flex flex-wrap gap-2">
              {['换一种方法讲', '给我一道同类题', '只看扣分点'].map((item) => (
                <button key={item} type="button" className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:border-blue-300 hover:bg-blue-50">
                  {item}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </DemoShell>
  )
}

function IntakeDemo() {
  return (
    <DemoShell id="intake" title="C. Paper Intake Flow" category="21st: File Uploads / Forms / Workflow">
      <div className="grid min-h-[560px] gap-4 bg-[#f7f8fb] p-4 lg:grid-cols-[minmax(0,1.15fr)_340px]">
        <div className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <SectionLabel>上传作业</SectionLabel>
              <h3 className="mt-1 text-xl font-semibold text-slate-950">拍照或上传 PDF，先判断批改路径</h3>
            </div>
            <span className="rounded-md bg-emerald-50 px-2.5 py-1 text-xs font-semibold text-emerald-700 ring-1 ring-emerald-200">无需封面也可开始</span>
          </div>

          <div className="mt-5 rounded-lg border border-dashed border-blue-300 bg-blue-50/60 p-5">
            <div className="flex min-h-[180px] flex-col items-center justify-center text-center">
              <span className="flex h-12 w-12 items-center justify-center rounded-lg bg-white text-xl font-semibold text-blue-700 shadow-sm">+</span>
              <p className="mt-3 text-base font-semibold text-slate-950">拖入整页图片、PDF 或直接打开相机</p>
              <p className="mt-1 max-w-md text-sm leading-6 text-slate-600">如果是 Past Paper，附上 cover page 或 paper code 会更快匹配 mark scheme。</p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                <button type="button" className="rounded-md bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700">拍照上传</button>
                <button type="button" className="rounded-md border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">选择 PDF</button>
              </div>
            </div>
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-3">
            {['不确定，帮我识别', 'Past Paper / 真题卷', '老师布置的作业'].map((item, index) => (
              <button key={item} type="button" className={`rounded-md border px-3 py-3 text-left text-sm ${index === 0 ? 'border-blue-300 bg-blue-50 text-blue-800' : 'border-slate-200 bg-white text-slate-700'}`}>
                <span className="font-semibold">{item}</span>
                <span className="mt-1 block text-xs text-slate-500">{index === 0 ? '默认推荐' : '可手动指定'}</span>
              </button>
            ))}
          </div>
        </div>

        <aside className="space-y-4">
          <div className="rounded-lg border border-slate-200 bg-white p-4">
            <SectionLabel>处理流程</SectionLabel>
            <ol className="mt-4 space-y-3">
              {workflowSteps.map((step, index) => (
                <li key={step} className="grid grid-cols-[28px_1fr] gap-3">
                  <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${index < 2 ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-500'}`}>
                    {index + 1}
                  </span>
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{step}</p>
                    <p className="text-xs text-slate-500">{index < 2 ? '自动进行中' : '上传后继续'}</p>
                  </div>
                </li>
              ))}
            </ol>
          </div>

          <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
            <SectionLabel>匹配提示</SectionLabel>
            <p className="mt-2 text-sm leading-6 text-slate-700">
              如果只能看到答案页，系统会让学生补题目页、输入 paper code，或回退开放批改。
            </p>
          </div>
        </aside>
      </div>
    </DemoShell>
  )
}

function ClinicDemo() {
  return (
    <DemoShell id="clinic" title="D. Exam Clinic Cards" category="21st: Cards / Tabs / Badges / Empty States">
      <div className="min-h-[560px] bg-[#fbfaf7] p-4">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,0.95fr)_minmax(320px,1.05fr)]">
          <aside className="rounded-lg border border-slate-200 bg-white p-4">
            <SectionLabel>本次诊断</SectionLabel>
            <h3 className="mt-2 text-xl font-semibold text-slate-950">不是“错题列表”，是今晚的订正处方</h3>
            <div className="mt-4 grid grid-cols-2 gap-3">
              {[
                ['17/25', '总分'],
                ['2', '重点错因'],
                ['1', '需复核'],
                ['3', '推荐练习'],
              ].map(([value, label]) => (
                <div key={label} className="rounded-md border border-slate-200 bg-slate-50 p-3">
                  <p className="text-xl font-semibold text-slate-950">{value}</p>
                  <p className="mt-1 text-xs text-slate-500">{label}</p>
                </div>
              ))}
            </div>
            <div className="mt-4 rounded-md border border-blue-200 bg-blue-50 p-3">
              <p className="text-sm font-semibold text-slate-950">下一步</p>
              <p className="mt-1 text-sm leading-6 text-slate-600">先订正 Q7，再做一道 Integration 同主题真题。</p>
            </div>
          </aside>

          <div className="space-y-3">
            <div className="flex gap-2 overflow-x-auto rounded-lg border border-slate-200 bg-white p-1">
              {['全部 7', '需要订正 3', '老师复核 1', '已掌握 3'].map((tab, index) => (
                <button key={tab} type="button" className={`whitespace-nowrap rounded-md px-3 py-2 text-sm font-semibold ${index === 1 ? 'bg-slate-950 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>
                  {tab}
                </button>
              ))}
            </div>

            {questionRows.map((row, index) => (
              <article key={row.q} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-lg font-semibold text-slate-950">{row.q}</h3>
                      <span className={`rounded-md px-2 py-1 text-xs font-semibold ring-1 ${index === 1 ? 'bg-emerald-50 text-emerald-700 ring-emerald-200' : 'bg-rose-50 text-rose-700 ring-rose-200'}`}>
                        {row.score}
                      </span>
                      <span className="rounded-md bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-600 ring-1 ring-slate-200">AI 置信度：{row.confidence}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{row.state}</p>
                  </div>
                  <button type="button" className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:border-blue-300 hover:bg-blue-50">
                    看订正
                  </button>
                </div>
              </article>
            ))}
          </div>
        </div>
      </div>
    </DemoShell>
  )
}

function ReflectionPanel() {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <SectionLabel>Reflection 审核机制</SectionLabel>
          <h2 className="mt-1 text-lg font-semibold text-slate-950">我按 6 个维度给每版做了初筛</h2>
        </div>
        <span className="rounded-md bg-slate-950 px-3 py-1.5 text-xs font-semibold text-white">推荐组合：C + D，第二阶段补 B</span>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {demoMeta.map((demo) => (
          <div key={demo.id} className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <p className="text-sm font-semibold text-slate-950">{demo.title}</p>
            <p className="mt-1 text-xs text-blue-700">{demo.category}</p>
            <p className="mt-3 text-xs leading-5 text-slate-600">{demo.bestFor}</p>
            <p className="mt-3 text-sm leading-6 text-slate-800">{demo.verdict}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-slate-700">
        审核结论：当前产品最需要先提升“上传信心”和“结果可扫读性”。C 能解决首屏转化和 PDF/真题输入困惑，D 能低风险提升结果页质感；B 是下一步差异化，适合在追问功能更成熟后放大。
      </div>
    </section>
  )
}

function DemoNav() {
  return (
    <nav className="rounded-lg border border-slate-200 bg-white p-2 shadow-sm" aria-label="Demo directions">
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
        {demoMeta.map((demo) => (
          <a
            key={demo.id}
            href={`#${demo.id}`}
            className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-800 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-800"
          >
            <span className="block">{demo.title.replace(/^([A-D])\. /, '$1 · ')}</span>
            <span className="mt-0.5 block text-xs font-medium text-slate-500">{demo.category}</span>
          </a>
        ))}
      </div>
    </nav>
  )
}

export function UIDirectionDemosPage() {
  return (
    <main className="min-h-screen bg-slate-100 px-4 py-6 text-slate-950">
      <div className="mx-auto max-w-7xl space-y-5">
        <header className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
          <SectionLabel>21st.dev x A-Level Assistant</SectionLabel>
          <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-slate-950">UI 方向 Demo 对比</h1>
              <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">
                这页只做设计比较，不改正式产品页面。四个方向分别借鉴 21st.dev 的 Dashboard、AI Chat、File Uploads、Cards/Tabs 分类，并套入同一组 A-Level 批改内容。
              </p>
            </div>
            <a
              href="/"
              className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
            >
              返回当前产品
            </a>
          </div>
        </header>

        <DemoNav />
        <DashboardDemo />
        <TutorDemo />
        <IntakeDemo />
        <ClinicDemo />
        <ReflectionPanel />
      </div>
    </main>
  )
}
