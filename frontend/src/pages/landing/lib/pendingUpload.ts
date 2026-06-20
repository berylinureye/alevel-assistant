/**
 * Module-level handoff store for files picked on the landing page.
 *
 * Flow:
 *   1. Landing CTA opens <input type="file">, user picks files.
 *   2. Landing calls stashPendingUpload(files) then navigate('/').
 *   3. App.tsx mounts, calls consumePendingUpload() inside a useEffect.
 *   4. If non-empty, it forwards the files to UploadForm via initialFiles prop.
 *
 * Why module state (not sessionStorage): File objects aren't serializable.
 * Why not Context: the landing page and the main App live under different
 * routes, not under a shared provider.
 */

let store: File[] = []

export function stashPendingUpload(files: File[] | FileList | null): void {
  if (!files || files.length === 0) {
    store = []
    return
  }
  store = Array.from(files)
}

export function consumePendingUpload(): File[] {
  const out = store
  store = []
  return out
}

export function hasPendingUpload(): boolean {
  return store.length > 0
}
