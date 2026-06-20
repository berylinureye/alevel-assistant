import { useCallback, useRef, useState } from 'react'

interface Rect {
  x: number
  y: number
  w: number
  h: number
}

interface Props {
  imageUrl: string
  onConfirm: (file: File) => void
  onCancel: () => void
}

type Corner = 'nw' | 'ne' | 'sw' | 'se'
type DragKind = 'move' | Corner

const HANDLE = 44
const MIN_SIZE = 30

export function ImageCropper({ imageUrl, onConfirm, onCancel }: Props) {
  const imgRef = useRef<HTMLImageElement>(null)
  const [ready, setReady] = useState(false)
  const [crop, setCrop] = useState<Rect>({ x: 0, y: 0, w: 0, h: 0 })
  const dragRef = useRef<{ kind: DragKind; sx: number; sy: number; start: Rect } | null>(null)

  /* ---- initialise crop to full image ---- */
  const initCrop = useCallback(() => {
    const img = imgRef.current
    if (!img) return
    setCrop({ x: 0, y: 0, w: img.clientWidth, h: img.clientHeight })
    setReady(true)
  }, [])

  /* ---- clamp helper ---- */
  const clamp = useCallback((c: Rect): Rect => {
    const img = imgRef.current
    if (!img) return c
    const mw = img.clientWidth
    const mh = img.clientHeight
    let { x, y, w, h } = c
    w = Math.max(MIN_SIZE, Math.min(w, mw))
    h = Math.max(MIN_SIZE, Math.min(h, mh))
    x = Math.max(0, Math.min(x, mw - w))
    y = Math.max(0, Math.min(y, mh - h))
    return { x, y, w, h }
  }, [])

  /* ---- pointer handlers ---- */
  const onDown = useCallback(
    (e: React.PointerEvent, kind: DragKind) => {
      e.preventDefault()
      e.stopPropagation()
      ;(e.target as HTMLElement).setPointerCapture(e.pointerId)
      dragRef.current = { kind, sx: e.clientX, sy: e.clientY, start: { ...crop } }
    },
    [crop],
  )

  const onMove = useCallback(
    (e: React.PointerEvent) => {
      const d = dragRef.current
      if (!d) return
      e.preventDefault()
      const dx = e.clientX - d.sx
      const dy = e.clientY - d.sy
      const s = d.start

      let next: Rect
      if (d.kind === 'move') {
        next = { ...s, x: s.x + dx, y: s.y + dy }
      } else {
        let { x, y, w, h } = s
        const isLeft = d.kind === 'nw' || d.kind === 'sw'
        const isTop = d.kind === 'nw' || d.kind === 'ne'
        if (isLeft) {
          x = s.x + dx
          w = s.w - dx
        } else {
          w = s.w + dx
        }
        if (isTop) {
          y = s.y + dy
          h = s.h - dy
        } else {
          h = s.h + dy
        }
        next = { x, y, w, h }
      }
      setCrop(clamp(next))
    },
    [clamp],
  )

  const onUp = useCallback(() => {
    dragRef.current = null
  }, [])

  /* ---- crop & export ---- */
  const handleConfirm = useCallback(async () => {
    const img = imgRef.current
    if (!img) return
    const rx = img.naturalWidth / img.clientWidth
    const ry = img.naturalHeight / img.clientHeight

    const canvas = document.createElement('canvas')
    const sw = crop.w * rx
    const sh = crop.h * ry
    canvas.width = sw
    canvas.height = sh
    canvas.getContext('2d')!.drawImage(img, crop.x * rx, crop.y * ry, sw, sh, 0, 0, sw, sh)

    const blob: Blob = await new Promise((r) =>
      canvas.toBlob((b) => r(b!), 'image/jpeg', 0.92),
    )
    onConfirm(new File([blob], `photo_${Date.now()}.jpg`, { type: 'image/jpeg' }))
  }, [crop, onConfirm])

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-black">
      {/* toolbar */}
      <div className="flex shrink-0 items-center justify-between px-4 py-3">
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-white/30 px-4 py-2.5 text-sm text-white active:bg-white/10"
        >
          取消
        </button>
        <span className="text-sm font-medium text-white">裁剪照片</span>
        <button
          type="button"
          onClick={handleConfirm}
          className="rounded-md bg-blue-600 px-4 py-2.5 text-sm font-medium text-white active:bg-blue-700"
        >
          确认裁剪
        </button>
      </div>

      {/* image + crop overlay */}
      <div
        className="relative flex flex-1 items-center justify-center overflow-hidden px-4 pb-6"
        onPointerMove={onMove}
        onPointerUp={onUp}
        onPointerCancel={onUp}
        style={{ touchAction: 'none' }}
      >
        <div className="relative inline-block">
          <img
            ref={imgRef}
            src={imageUrl}
            onLoad={initCrop}
            className="block max-h-[75vh] max-w-full select-none object-contain"
            draggable={false}
          />

          {ready && (
            <div
              className="absolute border-2 border-white"
              style={{
                left: crop.x,
                top: crop.y,
                width: crop.w,
                height: crop.h,
                boxShadow: '0 0 0 9999px rgba(0,0,0,0.55)',
                cursor: 'move',
              }}
              onPointerDown={(e) => onDown(e, 'move')}
            >
              {/* rule-of-thirds grid */}
              <div className="pointer-events-none absolute inset-0">
                <div className="absolute left-1/3 top-0 h-full w-px bg-white/25" />
                <div className="absolute left-2/3 top-0 h-full w-px bg-white/25" />
                <div className="absolute left-0 top-1/3 h-px w-full bg-white/25" />
                <div className="absolute left-0 top-2/3 h-px w-full bg-white/25" />
              </div>

              {/* corner handles */}
              {(['nw', 'ne', 'sw', 'se'] as const).map((c) => {
                const isL = c.includes('w')
                const isT = c.includes('n')
                return (
                  <div
                    key={c}
                    className="absolute z-10 rounded-sm bg-white shadow-md"
                    style={{
                      width: HANDLE,
                      height: HANDLE,
                      ...(isL ? { left: -HANDLE / 2 } : { right: -HANDLE / 2 }),
                      ...(isT ? { top: -HANDLE / 2 } : { bottom: -HANDLE / 2 }),
                      cursor: c === 'nw' || c === 'se' ? 'nwse-resize' : 'nesw-resize',
                    }}
                    onPointerDown={(e) => onDown(e, c)}
                  />
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* hint */}
      <p className="shrink-0 pb-4 text-center text-xs text-white/50">
        拖动白色方块调整裁剪区域，或直接点击「确认裁剪」保留完整照片
      </p>
    </div>
  )
}
