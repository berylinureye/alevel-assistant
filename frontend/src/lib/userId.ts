const KEY = 'anonymous_user_id'

export function getAnonymousUserId(): string {
  try {
    const existing = localStorage.getItem(KEY)
    if (existing) return existing
    const id = `u_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 10)}`
    localStorage.setItem(KEY, id)
    return id
  } catch {
    return `u_ephemeral_${Math.random().toString(36).slice(2, 10)}`
  }
}

export function newSessionId(): string {
  return `s_${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
}
