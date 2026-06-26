type Tone = 'emerald' | 'amber' | 'rose' | 'slate'

interface PrototypeMeta {
  id: string
  name: string
  pattern: string
  source: string
  bestFor: string
  difference: string
}

const prototypes: PrototypeMeta[] = [
  {
    id: 'wizard',
    name: '01 · Intake Wizard',
    pattern: '向导式上传 / File Upload + Forms + Stepper',
    source: 'File Uploads, Forms, Dialogs, Tabs',
    bestFor: '第一次使用、PDF/真题上传、降低学生不知道传什么的焦虑',
    difference: '先问意图，再传文件，再确认真题匹配，结果页是下一步。',
  },
  {
    id: 'workspace',
    name: '02 · Split Workspace',
    pattern: '三栏学习工作台 / Sidebar + Tabs + Panels',
    source: 'Sidebars, Tabs, Cards, AI Chat',
    bestFor: '桌面端认真订正，边看题边看批改边追问',
    difference: '左侧导航，中间题目和结果，右侧 AI 老师常驻。',
  },
  {
    id: 'chat',
    name: '03 · Chat-first Tutor',
    pattern: '对话优先 / AI Chat + Inline Result Cards',
    source: 'AI Chats, File Uploads, Cards',
    bestFor: '把“拍照批改”包装成跟老师发消息，适合学生高频使用',
    difference: '上传、批改、错因、追问都发生在聊天流里。',
  },
  {
    id: 'report',
    name: '04 · Report Dashboard',
    pattern: '报告优先 / Dashboard + Tables + Drilldown',
    source: 'Dashboard, Tables, Dashboard Widgets',
    bestFor: '老师、家长、阶段性复盘、看正确率和薄弱点',
    difference: '首屏不是上传，而是本次表现、薄弱点和可筛选题目表。',
  },
  {
    id: 'cards',
    name: '05 · Correction Board',
    pattern: '错题卡片流 / Cards + Badges + Action Feed',
    source: 'Cards, Badges, Empty States, Buttons',
    bestFor: '移动端订正、把错题变成一张张可完成任务',
    difference: '每道题是一张行动卡，按“先订正/待复核/已掌握”推进。',
  },
  {
    id: 'paper',
    name: '06 · Paper Desk',
    pattern: 'PDF 真题桌面 / Document Viewer + Mark Scheme Rail',
    source: 'File Uploads, Tables, Sidebars, Cards',
    bestFor: 'Past Paper、PDF、大文件、mark scheme-grounded 批改',
    difference: '核心不是聊天，而是纸面、页缩略图和评分规则对齐。',
  },
]

const questions = [
  { q: 'Q3', score: '3/5', label: '漏写条件限制', tone: 'amber' as Tone },
  { q: 'Q5', score: '4/4', label: '完整正确', tone: 'emerald' as Tone },
  { q: 'Q7', score: '2/6', label: '积分上下限错误', tone: 'rose' as Tone },
]

const workflow = ['识别上传类型', '匹配真题', '提取答案', '交叉检查', '生成反馈']
const topics = ['Integration', 'Logarithms', 'Quadratics']

function cx(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(' ')
}

function dot(tone: Tone) {
  return {
    emerald: 'bg-emerald-500',
    amber: 'bg-amber-400',
    rose: 'bg-rose-500',
    slate: 'bg-slate-400',
  }[tone]
}

function Label({ children }: { children: React.ReactNode }) {
  return <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-slate-500">{children}</p>
}

function Panel({ children, className }: { children: React.ReactNode; className?: string }) {
  return <section className={cx('rounded-lg border border-slate-200 bg-white p-4 shadow-sm', className)}>{children}</section>
}

function MiniUpload({ compact = false }: { compact?: boolean }) {
  return (
    <div className={cx('rounded-lg border border-dashed border-blue-300 bg-blue-50/70 p-4 text-center', compact ? 'min-h-[118px]' : 'min-h-[168px]')}>
      <div className="mx-auto flex h-11 w-11 items-center justify-center rounded-lg bg-blue-600 text-xl font-semibold text-white">+</div>
      <p className="mt-3 text-sm font-semibold text-slate-950">拍照上传作业 / 选择 PDF</p>
      <p className="mx-auto mt-1 max-w-md text-xs leading-5 text-slate-600">自动判断真题、普通作业或答案页，能匹配就按 mark scheme 批改。</p>
    </div>
  )
}

function WorkflowList() {
  return (
    <ol className="space-y-3">
      {workflow.map((step, index) => (
        <li key={step} className="grid grid-cols-[28px_minmax(0,1fr)] gap-3">
          <span className={cx('flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold', index < 3 ? 'bg-blue-600 text-white' : 'bg-slate-100 text-slate-500')}>
            {index + 1}
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-900">{step}</p>
            <p className="text-xs text-slate-500">{index < 3 ? '已完成' : '等待中'}</p>
          </div>
        </li>
      ))}
    </ol>
  )
}

function QuestionList({ table = false }: { table?: boolean }) {
  if (table) {
    return (
      <div className="overflow-hidden rounded-md border border-slate-200">
        <div className="grid grid-cols-[58px_minmax(0,1fr)_70px_76px] bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-500">
          <span>题号</span><span>诊断</span><span>得分</span><span>状态</span>
        </div>
        {questions.map((item) => (
          <div key={item.q} className="grid grid-cols-[58px_minmax(0,1fr)_70px_76px] border-t border-slate-100 px-3 py-3 text-sm">
            <span className="font-semibold text-slate-950">{item.q}</span>
            <span className="min-w-0 truncate text-slate-600">{item.label}</span>
            <span className="font-semibold text-slate-950">{item.score}</span>
            <span className="text-slate-500">AI 高</span>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-2">
      {questions.map((item) => (
        <article key={item.q} className="rounded-md border border-slate-200 bg-slate-50 px-3 py-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <span className={cx('h-2.5 w-2.5 shrink-0 rounded-full', dot(item.tone))} />
              <p className="font-semibold text-slate-950">{item.q}</p>
              <p className="min-w-0 truncate text-sm text-slate-600">{item.label}</p>
            </div>
            <span className="shrink-0 text-sm font-semibold text-slate-950">{item.score}</span>
          </div>
        </article>
      ))}
    </div>
  )
}

function ChatBubble({ side = 'left', children }: { side?: 'left' | 'right'; children: React.ReactNode }) {
  return (
    <div className={cx('max-w-[88%] rounded-lg px-3 py-2 text-sm leading-6', side === 'right' ? 'ml-auto bg-blue-600 text-white' : 'border border-slate-200 bg-slate-50 text-slate-700')}>
      {children}
    </div>
  )
}

function StatsRow() {
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
      {[
        ['68%', '得分率'],
        ['17/25', '总分'],
        ['3', '需订正'],
        ['1', '老师复核'],
      ].map(([value, label]) => (
        <div key={label} className="rounded-md border border-slate-200 bg-slate-50 p-3">
          <p className="text-xl font-semibold text-slate-950">{value}</p>
          <p className="mt-1 text-xs text-slate-500">{label}</p>
        </div>
      ))}
    </div>
  )
}

function PrototypeHeader({ meta }: { meta: PrototypeMeta }) {
  return (
    <div className="border-b border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Label>{meta.pattern}</Label>
          <h2 className="mt-1 text-xl font-semibold tracking-tight text-slate-950">{meta.name}</h2>
          <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-600">{meta.bestFor}</p>
        </div>
        <div className="max-w-md rounded-lg border border-slate-200 bg-slate-50 px-3 py-2">
          <p className="text-sm font-semibold text-slate-950">结构差异</p>
          <p className="mt-1 text-xs leading-5 text-slate-600">{meta.difference}</p>
        </div>
      </div>
    </div>
  )
}

function UploadWizardPrototype() {
  return (
    <PrototypeFrame meta={prototypes[0]} bg="bg-[#f4f7fb]">
      <div className="grid gap-4 p-4 lg:grid-cols-[260px_minmax(0,1fr)_320px]">
        <Panel>
          <Label>步骤</Label>
          <ol className="mt-4 space-y-2">
            {['选择上传类型', '添加图片/PDF', '确认真题匹配', '开始批改'].map((step, index) => (
              <li key={step} className={cx('rounded-md border px-3 py-3 text-sm font-semibold', index === 1 ? 'border-blue-300 bg-blue-50 text-blue-800' : 'border-slate-200 bg-slate-50 text-slate-600')}>
                {index + 1}. {step}
              </li>
            ))}
          </ol>
        </Panel>
        <Panel>
          <Label>当前步骤 · 添加文件</Label>
          <div className="mt-4"><MiniUpload /></div>
          <div className="mt-4 grid gap-2 md:grid-cols-3">
            {['不确定，帮我识别', 'Past Paper / 真题卷', '老师布置的作业'].map((item, index) => (
              <button key={item} type="button" className={cx('rounded-md border px-3 py-3 text-left text-sm font-semibold', index === 0 ? 'border-blue-300 bg-blue-50 text-blue-800' : 'border-slate-200 bg-white text-slate-700')}>
                {item}
              </button>
            ))}
          </div>
        </Panel>
        <Panel>
          <Label>上传后会发生</Label>
          <div className="mt-4"><WorkflowList /></div>
          <div className="mt-4 rounded-md border border-blue-200 bg-blue-50 p-3 text-sm leading-6 text-slate-700">
            适合把新用户带过第一步：先完成上传，再自然进入结果和追问。
          </div>
        </Panel>
      </div>
    </PrototypeFrame>
  )
}

function SplitWorkspacePrototype() {
  return (
    <PrototypeFrame meta={prototypes[1]} bg="bg-slate-100">
      <div className="grid min-h-[620px] lg:grid-cols-[190px_minmax(0,1fr)_340px]">
        <aside className="border-b border-slate-200 bg-slate-950 p-4 text-white lg:border-b-0 lg:border-r">
          <p className="text-sm font-semibold">A-Level Assistant</p>
          <nav className="mt-6 grid grid-cols-2 gap-2 text-xs lg:grid-cols-1">
            {['上传', '批改', '错题', '追问', '练习'].map((item, index) => (
              <span key={item} className={cx('rounded-md px-3 py-2', index === 1 ? 'bg-white text-slate-950' : 'bg-white/10 text-slate-300')}>
                {item}
              </span>
            ))}
          </nav>
        </aside>
        <main className="space-y-4 p-4">
          <Panel>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <Label>题目工作区</Label>
                <h3 className="mt-1 text-lg font-semibold text-slate-950">Q7 · Integration</h3>
              </div>
              <button type="button" className="rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white">重新上传</button>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
              <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                <Label>原始作业预览</Label>
                <div className="mt-4 flex h-52 items-center justify-center rounded-md border border-dashed border-slate-300 bg-white text-sm text-slate-500">
                  手写题目 / 答案图片区域
                </div>
              </div>
              <div>
                <Label>诊断结果</Label>
                <div className="mt-4"><QuestionList /></div>
              </div>
            </div>
          </Panel>
          <Panel>
            <Label>本次表现</Label>
            <div className="mt-4"><StatsRow /></div>
          </Panel>
        </main>
        <aside className="border-t border-slate-200 bg-white p-4 lg:border-l lg:border-t-0">
          <Label>AI 老师常驻</Label>
          <div className="mt-4 space-y-3">
            <ChatBubble>为什么我积分式写对了还扣分？</ChatBubble>
            <ChatBubble side="right">你的方法对，但上下限方向反了。看中间图像，先从左交点到右交点。</ChatBubble>
          </div>
          <div className="mt-4 grid gap-2">
            {['换一种讲法', '生成同类题', '只看 mark scheme'].map((item) => (
              <button key={item} type="button" className="rounded-md border border-slate-200 bg-white px-3 py-2 text-left text-sm font-semibold text-slate-700">{item}</button>
            ))}
          </div>
        </aside>
      </div>
    </PrototypeFrame>
  )
}

function ChatFirstPrototype() {
  return (
    <PrototypeFrame meta={prototypes[2]} bg="bg-[#f7f9fb]">
      <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_330px]">
        <Panel className="min-h-[600px]">
          <div className="flex items-center justify-between border-b border-slate-100 pb-3">
            <div>
              <Label>AI 老师对话</Label>
              <h3 className="mt-1 text-lg font-semibold text-slate-950">像发消息一样拍照批改</h3>
            </div>
            <span className="rounded-md border border-blue-200 bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700">5 AI 校对</span>
          </div>
          <div className="mt-4 space-y-4">
            <ChatBubble>我这页作业帮我按 A-Level 标准批一下。</ChatBubble>
            <div className="max-w-[88%] rounded-lg border border-slate-200 bg-white p-3"><MiniUpload compact /></div>
            <ChatBubble side="right">识别到 7 道题，其中 3 道需要订正。我先给你看最影响得分的 Q7。</ChatBubble>
            <div className="ml-auto max-w-[92%] rounded-lg border border-blue-200 bg-blue-50 p-3">
              <p className="text-sm font-semibold text-slate-950">Q7 · 2/6 · 积分上下限错误</p>
              <p className="mt-1 text-sm leading-6 text-slate-700">方法分拿到了，但 A1 要求上下限和区域方向一致。</p>
              <div className="mt-3 flex flex-wrap gap-2">
                {['继续解释', '出同类题', '看完整报告'].map((item) => <button key={item} className="rounded-md bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 ring-1 ring-slate-200">{item}</button>)}
              </div>
            </div>
          </div>
        </Panel>
        <div className="space-y-4">
          <Panel><Label>批改进度</Label><div className="mt-4"><WorkflowList /></div></Panel>
          <Panel><Label>快速报告</Label><div className="mt-4"><StatsRow /></div></Panel>
        </div>
      </div>
    </PrototypeFrame>
  )
}

function ReportDashboardPrototype() {
  return (
    <PrototypeFrame meta={prototypes[3]} bg="bg-[#f3f6f8]">
      <div className="space-y-4 p-4">
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_300px]">
          <Panel><Label>表现总览</Label><div className="mt-4"><StatsRow /></div></Panel>
          <Panel>
            <Label>下一步</Label>
            <p className="mt-3 text-lg font-semibold text-slate-950">今晚先修 Integration</p>
            <p className="mt-1 text-sm leading-6 text-slate-600">预计 18 分钟，先看上下限，再做 3 道同主题题。</p>
          </Panel>
        </div>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.1fr)_minmax(300px,0.9fr)]">
          <Panel>
            <div className="flex items-center justify-between gap-3">
              <Label>题目表格</Label>
              <button type="button" className="rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700">筛选需订正</button>
            </div>
            <div className="mt-4"><QuestionList table /></div>
          </Panel>
          <Panel>
            <Label>薄弱点矩阵</Label>
            <div className="mt-4 space-y-4">
              {topics.map((topic, index) => (
                <div key={topic} className="grid grid-cols-[100px_1fr_50px] items-center gap-3 text-sm">
                  <span className="font-semibold text-slate-950">{topic}</span>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                    <div className={cx('h-full rounded-full', index === 0 ? 'w-2/5 bg-rose-500' : index === 1 ? 'w-3/5 bg-amber-400' : 'w-4/5 bg-emerald-500')} />
                  </div>
                  <span className="text-right text-slate-500">{index === 0 ? '弱' : index === 1 ? '中' : '稳'}</span>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      </div>
    </PrototypeFrame>
  )
}

function CardBoardPrototype() {
  return (
    <PrototypeFrame meta={prototypes[4]} bg="bg-[#f7f8fa]">
      <div className="grid gap-4 p-4 lg:grid-cols-[300px_minmax(0,1fr)]">
        <Panel>
          <Label>快速开始</Label>
          <div className="mt-4"><MiniUpload compact /></div>
          <button type="button" className="mt-4 w-full rounded-md bg-blue-600 px-3 py-2 text-sm font-semibold text-white">拍下一页作业</button>
          <div className="mt-4"><StatsRow /></div>
        </Panel>
        <div className="grid gap-4 md:grid-cols-3">
          {[
            { title: '先订正', items: [questions[0], questions[2]] },
            { title: '老师复核', items: [{ q: 'Q9', score: '?/5', label: '图表题识别不确定', tone: 'amber' as Tone }] },
            { title: '已掌握', items: [questions[1]] },
          ].map((column) => (
            <Panel key={column.title}>
              <div className="flex items-center justify-between">
                <Label>{column.title}</Label>
                <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-600">{column.items.length}</span>
              </div>
              <div className="mt-4 space-y-3">
                {column.items.map((item) => (
                  <article key={item.q} className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-slate-950">{item.q}</span>
                      <span className="text-sm font-semibold text-slate-950">{item.score}</span>
                    </div>
                    <p className="mt-2 text-sm leading-6 text-slate-600">{item.label}</p>
                    <button type="button" className="mt-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-1.5 text-xs font-semibold text-slate-700">开始订正</button>
                  </article>
                ))}
              </div>
            </Panel>
          ))}
        </div>
      </div>
    </PrototypeFrame>
  )
}

function PaperDeskPrototype() {
  return (
    <PrototypeFrame meta={prototypes[5]} bg="bg-[#f8f7f3]">
      <div className="grid min-h-[620px] gap-4 p-4 lg:grid-cols-[180px_minmax(0,1fr)_340px]">
        <Panel>
          <Label>PDF 页</Label>
          <div className="mt-4 grid grid-cols-3 gap-2 lg:grid-cols-1">
            {[1, 2, 3, 4, 5].map((page, index) => (
              <button key={page} type="button" className={cx('rounded-md border p-3 text-left text-xs font-semibold', index === 2 ? 'border-blue-300 bg-blue-50 text-blue-800' : 'border-slate-200 bg-white text-slate-600')}>
                Page {page}
              </button>
            ))}
          </div>
        </Panel>
        <Panel>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <Label>真题页面</Label>
              <h3 className="mt-1 text-lg font-semibold text-slate-950">9709/12/M/J/24 · Q7</h3>
            </div>
            <span className="rounded-md border border-emerald-200 bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700">Mark scheme matched</span>
          </div>
          <div className="mt-4 flex h-80 items-center justify-center rounded-lg border border-dashed border-slate-300 bg-white text-sm text-slate-500">
            PDF / 作业页面大预览
          </div>
          <div className="mt-4"><QuestionList /></div>
        </Panel>
        <div className="space-y-4">
          <Panel>
            <Label>Mark scheme 对齐</Label>
            <ol className="mt-4 space-y-3 text-sm text-slate-700">
              {['M1 建立正确积分表达式', 'A1 上下限方向正确', 'B1 面积取正值'].map((item, index) => (
                <li key={item} className="flex gap-2"><span className={cx('mt-1 h-2.5 w-2.5 rounded-full', index === 0 ? 'bg-emerald-500' : 'bg-rose-500')} />{item}</li>
              ))}
            </ol>
          </Panel>
          <Panel>
            <Label>追问</Label>
            <div className="mt-4 space-y-3">
              <ChatBubble>为什么这一步不给 A1？</ChatBubble>
              <ChatBubble side="right">A1 看的是上下限和区域方向，不是只看积分式形状。</ChatBubble>
            </div>
          </Panel>
        </div>
      </div>
    </PrototypeFrame>
  )
}

function PrototypeFrame({ meta, bg, children }: { meta: PrototypeMeta; bg: string; children: React.ReactNode }) {
  return (
    <section id={meta.id} className={cx('scroll-mt-4 overflow-hidden rounded-xl border border-slate-200 shadow-sm', bg)}>
      <PrototypeHeader meta={meta} />
      {children}
    </section>
  )
}

function ResearchPanel() {
  return (
    <Panel>
      <Label>这次参考的 21st.dev 分类</Label>
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {[
          ['AI Chats', '聊天流、输入框、内联结果卡、追问按钮'],
          ['File Uploads / Forms', '拖拽上传、步骤确认、上传意图选择'],
          ['Dashboard / Tables', '正确率报告、题目表格、弱点矩阵'],
          ['Cards / Badges', '错题卡片、状态标签、行动入口'],
          ['Tabs / Sidebars', '工作台导航、多面板切换、常驻 AI 栏'],
          ['Dialogs / Modals', '真题匹配确认、低置信度复核提示'],
        ].map(([title, text]) => (
          <div key={title} className="rounded-md border border-slate-200 bg-slate-50 p-3">
            <p className="text-sm font-semibold text-slate-950">{title}</p>
            <p className="mt-2 text-sm leading-6 text-slate-600">{text}</p>
          </div>
        ))}
      </div>
    </Panel>
  )
}

function PrototypeNav() {
  return (
    <nav className="rounded-lg border border-slate-200 bg-white p-2 shadow-sm" aria-label="UI prototypes">
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
        {prototypes.map((prototype) => (
          <a key={prototype.id} href={`#${prototype.id}`} className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm font-semibold text-slate-900 hover:border-blue-300 hover:bg-blue-50">
            <span className="block">{prototype.name}</span>
            <span className="mt-0.5 block text-xs font-medium text-slate-500">{prototype.pattern}</span>
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
          <Label>21st.dev x A-Level Assistant</Label>
          <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
            <div>
              <h1 className="text-2xl font-semibold tracking-tight text-slate-950">6 套真正不同的 UI 原型</h1>
              <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-600">
                这次不是换颜色。每套都用大众接受的浅色基础风格，但信息架构、主操作、组件组合和交互节奏不同。你可以比较哪一种更适合作为产品主线。
              </p>
            </div>
            <a href="/" className="rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50">
              返回当前产品
            </a>
          </div>
        </header>

        <PrototypeNav />
        <ResearchPanel />
        <UploadWizardPrototype />
        <SplitWorkspacePrototype />
        <ChatFirstPrototype />
        <ReportDashboardPrototype />
        <CardBoardPrototype />
        <PaperDeskPrototype />
      </div>
    </main>
  )
}
