import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  clearSession,
  notifySessionExpired,
  readSession,
  registerSessionExpiredHandler,
  updateSessionTokens,
  writeSession,
} from './session'

describe('session', () => {
  afterEach(() => {
    clearSession()
    registerSessionExpiredHandler(undefined)
  })

  it('persists and clears the complete authenticated session', () => {
    const session = {
      accessToken: 'access-token',
      refreshToken: 'refresh-token',
      user: { id: 'user-1', username: 'teacher' },
    }

    writeSession(session)
    expect(readSession()).toEqual(session)

    clearSession()
    expect(readSession()).toBeNull()
  })

  it('notifies the application when a session expires', () => {
    const onExpired = vi.fn()

    registerSessionExpiredHandler(onExpired)
    notifySessionExpired()

    expect(onExpired).toHaveBeenCalledOnce()
  })

  it('updates tokens without discarding the authenticated user', () => {
    writeSession({
      accessToken: 'old-access',
      refreshToken: 'old-refresh',
      user: { id: 'user-1', username: 'teacher' },
    })

    updateSessionTokens('new-access', 'new-refresh')

    expect(readSession()).toEqual({
      accessToken: 'new-access',
      refreshToken: 'new-refresh',
      user: { id: 'user-1', username: 'teacher' },
    })
  })
})
