const STORAGE_KEY = 'alevel-ta-profile-v1'

export interface UserProfile {
  phone: string
  name: string
  grade: string
  registeredAt: number
}

export function loadProfile(): UserProfile | null {
  if (typeof localStorage === 'undefined') return null
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) return null
  try {
    const data = JSON.parse(raw)
    if (data && typeof data.phone === 'string') return data as UserProfile
  } catch {
    return null
  }
  return null
}

export function saveProfile(profile: Omit<UserProfile, 'registeredAt'>): UserProfile {
  const entry: UserProfile = { ...profile, registeredAt: Date.now() }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(entry))
  return entry
}

export function clearProfile(): void {
  localStorage.removeItem(STORAGE_KEY)
}

export function isValidChinaPhone(p: string): boolean {
  return /^1[3-9]\d{9}$/.test(p.trim())
}
