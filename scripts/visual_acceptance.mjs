#!/usr/bin/env node
import { mkdir, stat, writeFile, rm } from 'node:fs/promises'
import { spawn } from 'node:child_process'
import { createServer } from 'node:net'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const FRONTEND_DIR = path.join(ROOT, 'frontend')
const DEFAULT_OUT_DIR = '/private/tmp/alevel-visual-acceptance'
const DEFAULT_PATH = '/'
const VIEWPORTS = [
  { name: 'desktop', width: 1366, height: 768, mobile: false },
  { name: 'mobile', width: 390, height: 844, mobile: true },
]

function parseArgs(argv) {
  const args = {
    url: process.env.VISUAL_ACCEPTANCE_URL || '',
    path: DEFAULT_PATH,
    outDir: process.env.VISUAL_ACCEPTANCE_OUT_DIR || DEFAULT_OUT_DIR,
    chromePath: process.env.CHROME_PATH || '',
    noStartServer: false,
    serverPort: Number(process.env.VISUAL_ACCEPTANCE_SERVER_PORT || 3010),
    expectUpload: false,
    expectNav: false,
    skipContentChecks: false,
  }

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i]
    const next = argv[i + 1]
    if (arg === '--url' && next) {
      args.url = next
      i += 1
    } else if (arg === '--path' && next) {
      args.path = next
      i += 1
    } else if (arg === '--out' && next) {
      args.outDir = next
      i += 1
    } else if (arg === '--chrome' && next) {
      args.chromePath = next
      i += 1
    } else if (arg === '--server-port' && next) {
      args.serverPort = Number(next)
      i += 1
    } else if (arg === '--no-start-server') {
      args.noStartServer = true
    } else if (arg === '--expect-upload') {
      args.expectUpload = true
    } else if (arg === '--expect-nav') {
      args.expectNav = true
    } else if (arg === '--skip-content-checks') {
      args.skipContentChecks = true
    } else if (arg === '--help') {
      printHelp()
      process.exit(0)
    } else {
      throw new Error(`Unknown argument: ${arg}`)
    }
  }

  if (!Number.isInteger(args.serverPort) || args.serverPort < 1024) {
    throw new Error('--server-port must be an integer above 1023')
  }

  const normalizedPath = normalizeRoutePath(args.path)
  if (!args.skipContentChecks && normalizedPath === '/') {
    args.expectUpload = true
    args.expectNav = true
  }

  return args
}

function printHelp() {
  console.log(`Usage: node scripts/visual_acceptance.mjs [options]

Options:
  --url <url>          Base app URL. If omitted, tries 3000/3001, then starts Vite.
  --path <path>        App path to validate. Defaults to /.
  --out <dir>          Output directory. Defaults to /private/tmp/alevel-visual-acceptance.
  --chrome <path>      Chrome executable path. Defaults to CHROME_PATH or common macOS path.
  --server-port <port> Port used when auto-starting Vite. Defaults to 3010.
  --no-start-server    Fail instead of auto-starting Vite when no app URL is reachable.
  --expect-upload      Require upload-related text to be visible.
  --expect-nav         Require main navigation text to be visible.
  --skip-content-checks Disable default content checks for /.
`)
}

function normalizeRoutePath(routePath) {
  const parsed = new URL(routePath, 'http://visual.local')
  return parsed.pathname || '/'
}

function normalizeUrl(baseUrl, routePath) {
  const url = new URL(routePath, baseUrl.endsWith('/') ? baseUrl : `${baseUrl}/`)
  return url.toString()
}

async function pathExists(filePath) {
  try {
    await stat(filePath)
    return true
  } catch {
    return false
  }
}

async function resolveChromePath(explicitPath) {
  const candidates = [
    explicitPath,
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
  ].filter(Boolean)

  for (const candidate of candidates) {
    if (await pathExists(candidate)) return candidate
  }

  throw new Error(
    'Chrome executable not found. Set CHROME_PATH or pass --chrome /path/to/Chrome.',
  )
}

async function requestOk(url, timeoutMs = 1200) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(url, { signal: controller.signal })
    return res.ok
  } catch {
    return false
  } finally {
    clearTimeout(timer)
  }
}

async function waitForUrl(url, timeoutMs = 15000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    if (await requestOk(url)) return true
    await delay(250)
  }
  return false
}

async function findExistingAppUrl(routePath) {
  const bases = [
    'http://127.0.0.1:3000/',
    'http://127.0.0.1:3001/',
    'http://127.0.0.1:3002/',
  ]
  for (const base of bases) {
    if (await requestOk(normalizeUrl(base, routePath))) return base
  }
  return null
}

async function startViteServer(serverPort, routePath) {
  const baseUrl = `http://127.0.0.1:${serverPort}/`
  const child = spawn(
    'npm',
    ['run', 'dev', '--', '--host', '127.0.0.1', '--port', String(serverPort), '--strictPort'],
    {
      cwd: FRONTEND_DIR,
      env: { ...process.env, BROWSER: 'none' },
      stdio: ['ignore', 'pipe', 'pipe'],
    },
  )

  let logTail = ''
  const collect = (chunk) => {
    logTail = `${logTail}${chunk.toString()}`
    if (logTail.length > 4000) logTail = logTail.slice(-4000)
  }
  child.stdout.on('data', collect)
  child.stderr.on('data', collect)

  const url = normalizeUrl(baseUrl, routePath)
  const ready = await waitForUrl(url, 20000)
  if (!ready) {
    child.kill('SIGTERM')
    throw new Error(`Vite dev server did not become ready at ${url}.\n${logTail}`)
  }

  return { baseUrl, child }
}

function stopChild(child) {
  if (!child || child.killed) return
  child.kill('SIGTERM')
}

async function getFreePort() {
  return new Promise((resolve, reject) => {
    const server = createServer()
    server.once('error', reject)
    server.listen(0, '127.0.0.1', () => {
      const address = server.address()
      const port = typeof address === 'object' && address ? address.port : null
      server.close(() => {
        if (port) resolve(port)
        else reject(new Error('Could not allocate a local port'))
      })
    })
  })
}

async function delay(ms) {
  return new Promise((resolve) => {
    setTimeout(resolve, ms)
  })
}

class CdpClient {
  constructor(wsUrl) {
    this.wsUrl = wsUrl
    this.nextId = 1
    this.pending = new Map()
    this.listeners = new Map()
  }

  async connect() {
    this.ws = new WebSocket(this.wsUrl)
    await new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Timed out connecting to Chrome')), 5000)
      this.ws.addEventListener('open', () => {
        clearTimeout(timer)
        resolve()
      }, { once: true })
      this.ws.addEventListener('error', (event) => {
        clearTimeout(timer)
        reject(new Error(`Chrome WebSocket error: ${event.message || 'unknown'}`))
      }, { once: true })
    })

    this.ws.addEventListener('message', (event) => {
      const message = JSON.parse(event.data)
      if (message.id && this.pending.has(message.id)) {
        const { resolve, reject } = this.pending.get(message.id)
        this.pending.delete(message.id)
        if (message.error) reject(new Error(message.error.message || 'Chrome command failed'))
        else resolve(message.result ?? {})
        return
      }

      if (message.method && this.listeners.has(message.method)) {
        for (const listener of this.listeners.get(message.method)) {
          listener(message.params ?? {})
        }
      }
    })
  }

  send(method, params = {}) {
    const id = this.nextId
    this.nextId += 1
    this.ws.send(JSON.stringify({ id, method, params }))
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
      setTimeout(() => {
        if (!this.pending.has(id)) return
        this.pending.delete(id)
        reject(new Error(`Timed out running Chrome command ${method}`))
      }, 10000)
    })
  }

  once(method, timeoutMs = 10000) {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        cleanup()
        reject(new Error(`Timed out waiting for ${method}`))
      }, timeoutMs)
      const cleanup = () => {
        clearTimeout(timer)
        const listeners = this.listeners.get(method) ?? []
        this.listeners.set(method, listeners.filter((listener) => listener !== onEvent))
      }
      const onEvent = (params) => {
        cleanup()
        resolve(params)
      }
      const listeners = this.listeners.get(method) ?? []
      listeners.push(onEvent)
      this.listeners.set(method, listeners)
    })
  }

  close() {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) this.ws.close()
  }
}

async function waitForChromeTarget(port, targetUrl, timeoutMs = 10000) {
  const started = Date.now()
  while (Date.now() - started < timeoutMs) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/list`)
      const targets = await res.json()
      const page = targets.find((target) => {
        return target.type === 'page' && target.webSocketDebuggerUrl
          && (target.url === targetUrl || target.url.startsWith(targetUrl))
      }) ?? targets.find((target) => target.type === 'page' && target.webSocketDebuggerUrl)
      if (page) return page
    } catch {
      // Chrome is still starting.
    }
    await delay(200)
  }
  throw new Error(`Chrome debugging target did not become available on port ${port}`)
}

async function captureViewport({ chromePath, url, outDir, viewport, checks }) {
  const remotePort = await getFreePort()
  const profileDir = path.join(outDir, `.chrome-${viewport.name}-${process.pid}-${remotePort}`)
  const screenshotPath = path.join(outDir, `first-screen-${viewport.name}.png`)
  const chrome = spawn(chromePath, [
    '--headless=new',
    '--disable-gpu',
    '--disable-dev-shm-usage',
    '--no-first-run',
    '--no-default-browser-check',
    `--remote-debugging-port=${remotePort}`,
    `--user-data-dir=${profileDir}`,
    `--window-size=${viewport.width},${viewport.height}`,
    url,
  ], {
    stdio: ['ignore', 'pipe', 'pipe'],
  })

  let chromeLog = ''
  chrome.stderr.on('data', (chunk) => {
    chromeLog = `${chromeLog}${chunk.toString()}`
    if (chromeLog.length > 4000) chromeLog = chromeLog.slice(-4000)
  })

  let client
  try {
    const target = await waitForChromeTarget(remotePort, url)
    client = new CdpClient(target.webSocketDebuggerUrl)
    await client.connect()
    await client.send('Page.enable')
    await client.send('Runtime.enable')
    await client.send('Emulation.setDeviceMetricsOverride', {
      width: viewport.width,
      height: viewport.height,
      deviceScaleFactor: 1,
      mobile: viewport.mobile,
    })

    const loadEvent = client.once('Page.loadEventFired', 15000).catch(() => null)
    await client.send('Page.navigate', { url })
    await loadEvent
    await waitForReactRoot(client)
    await client.send('Runtime.evaluate', {
      expression: 'document.fonts ? document.fonts.ready.then(() => true) : true',
      awaitPromise: true,
      returnByValue: true,
    }).catch(() => null)
    await delay(400)

    const metrics = await evaluateMetrics(client)
    const screenshot = await client.send('Page.captureScreenshot', {
      format: 'png',
      captureBeyondViewport: false,
      fromSurface: true,
    })
    await writeFile(screenshotPath, Buffer.from(screenshot.data, 'base64'))

    const failures = evaluateFailures(metrics, checks)

    return {
      name: viewport.name,
      url,
      viewport: { width: viewport.width, height: viewport.height },
      screenshotPath,
      metrics,
      checks,
      failures,
      passed: failures.length === 0,
    }
  } catch (error) {
    throw new Error(`${viewport.name} capture failed: ${error.message}\n${chromeLog}`)
  } finally {
    client?.close()
    chrome.kill('SIGTERM')
    await rm(profileDir, { recursive: true, force: true }).catch(() => null)
  }
}

function evaluateFailures(metrics, checks) {
  const failures = []
  if (metrics.horizontalOverflow) {
    failures.push('horizontalOverflow')
  }
  if (checks.expectUpload && !metrics.uploadTextVisible) {
    failures.push('uploadTextVisible')
  }
  if (checks.expectNav && !metrics.navTextVisible) {
    failures.push('navTextVisible')
  }
  return failures
}

async function waitForReactRoot(client) {
  const started = Date.now()
  while (Date.now() - started < 10000) {
    const result = await client.send('Runtime.evaluate', {
      expression: 'Boolean(document.querySelector("#root")?.children.length)',
      returnByValue: true,
    })
    if (result.result?.value === true) return
    await delay(150)
  }
  throw new Error('React root did not render within 10s')
}

async function evaluateMetrics(client) {
  const expression = `(() => {
    const doc = document.documentElement;
    const body = document.body;
    const scrollWidth = Math.max(doc.scrollWidth, body ? body.scrollWidth : 0);
    const clientWidth = doc.clientWidth;
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const text = document.body ? document.body.innerText : '';
    const uploadTextVisible = /上传作业|上传|拍照|选择图片|选择文件|PDF|真题卷|Past Paper/.test(text);
    const navTextVisible = /作业批改|历史记录|总结|刷题/.test(text);
    return {
      viewportWidth,
      viewportHeight,
      clientWidth,
      scrollWidth,
      bodyScrollWidth: body ? body.scrollWidth : 0,
      horizontalOverflow: scrollWidth > clientWidth + 1,
      uploadTextVisible,
      navTextVisible,
      title: document.title || null,
    };
  })()`
  const result = await client.send('Runtime.evaluate', {
    expression,
    returnByValue: true,
  })
  return result.result?.value
}

async function main() {
  const args = parseArgs(process.argv.slice(2))
  const chromePath = await resolveChromePath(args.chromePath)
  await mkdir(args.outDir, { recursive: true })

  let viteServer = null
  let baseUrl = args.url
  if (!baseUrl) {
    baseUrl = await findExistingAppUrl(args.path)
  }

  if (!baseUrl) {
    if (args.noStartServer) {
      throw new Error('No reachable dev server found. Start Vite or pass --url.')
    }
    viteServer = await startViteServer(args.serverPort, args.path)
    baseUrl = viteServer.baseUrl
  }

  const url = normalizeUrl(baseUrl, args.path)
  if (!(await waitForUrl(url, 8000))) {
    throw new Error(`App URL is not reachable: ${url}`)
  }

  try {
    const results = []
    const checks = {
      expectUpload: args.expectUpload,
      expectNav: args.expectNav,
    }
    for (const viewport of VIEWPORTS) {
      results.push(await captureViewport({ chromePath, url, outDir: args.outDir, viewport, checks }))
    }

    const report = {
      status: results.every((item) => item.passed) ? 'passed' : 'failed',
      url,
      outDir: args.outDir,
      checks,
      checkedAt: new Date().toISOString(),
      results,
    }
    const reportPath = path.join(args.outDir, 'visual-acceptance-report.json')
    await writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`)
    console.log(JSON.stringify({ ...report, reportPath }, null, 2))

    if (report.status !== 'passed') {
      process.exitCode = 1
    }
  } finally {
    stopChild(viteServer?.child)
  }
}

main().catch((error) => {
  console.error(error.stack || error.message)
  process.exit(1)
})
