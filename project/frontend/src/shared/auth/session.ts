import { STORAGE_KEYS } from '@/utils/constants'

export interface StoredSession {
  accessToken: string
  refreshToken: string
  user: unknown
}

let sessionExpiredHandler: (() => void) | undefined

export function readSession(): StoredSession | null {
  const accessToken = localStorage.getItem(STORAGE_KEYS.TOKEN)
  const refreshToken = localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN)
  const storedUser = localStorage.getItem(STORAGE_KEYS.USER_INFO)

  if (!accessToken || !refreshToken || !storedUser) {
    return null
  }

  try {
    const user = JSON.parse(storedUser) as unknown
    return { accessToken, refreshToken, user }
  } catch {
    return null
  }
}

export function writeSession(session: StoredSession): void {
  localStorage.setItem(STORAGE_KEYS.TOKEN, session.accessToken)
  localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, session.refreshToken)
  localStorage.setItem(STORAGE_KEYS.USER_INFO, JSON.stringify(session.user))
}

export function updateSessionTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(STORAGE_KEYS.TOKEN, accessToken)
  localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, refreshToken)
}

export function clearSession(): void {
  localStorage.removeItem(STORAGE_KEYS.TOKEN)
  localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN)
  localStorage.removeItem(STORAGE_KEYS.USER_INFO)
}

export function registerSessionExpiredHandler(handler: (() => void) | undefined): void {
  sessionExpiredHandler = handler
}

export function notifySessionExpired(): void {
  sessionExpiredHandler?.()
}
