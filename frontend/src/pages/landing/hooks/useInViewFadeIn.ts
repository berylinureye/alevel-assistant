import { useEffect, useRef, useState } from 'react'

/**
 * Returns a ref to attach to an element and a boolean indicating whether
 * the element has entered the viewport at least once.
 *
 * Single observer per hook instance is fine at landing-page scale (~10 sections).
 * If we later ship dozens of elements, refactor to one shared observer module.
 */
export function useInViewFadeIn<T extends Element = HTMLDivElement>(
  options: IntersectionObserverInit = { threshold: 0.12, rootMargin: '0px 0px -40px 0px' },
) {
  const ref = useRef<T | null>(null)
  const [inView, setInView] = useState(false)

  useEffect(() => {
    const node = ref.current
    if (!node) return
    if (typeof IntersectionObserver === 'undefined') {
      setInView(true)
      return
    }
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          setInView(true)
          observer.disconnect()
          break
        }
      }
    }, options)
    observer.observe(node)
    return () => observer.disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  return { ref, inView }
}
