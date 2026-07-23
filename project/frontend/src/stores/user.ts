import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { UserInfo, LoginRequest } from '@/types'
import { loginApi, getUserInfoApi, refreshTokenApi } from '@/api/auth'
import {
  clearSession as clearStoredSession,
  notifySessionExpired,
  readSession,
  updateSessionTokens,
  writeSession,
} from '@/shared/auth/session'
import { ROLE_HOME_ROUTES } from '@/utils/constants'

export const useUserStore = defineStore('user', () => {
  const storedSession = readSession()
  const token = ref<string>(storedSession?.accessToken || '')
  const refreshToken = ref<string>(storedSession?.refreshToken || '')
  const userInfo = ref<UserInfo | null>((storedSession?.user as UserInfo | undefined) || null)

  const isLoggedIn = computed(() => !!token.value)
  const userRole = computed(() => userInfo.value?.role || '')
  const displayName = computed(
    () => userInfo.value?.displayName || userInfo.value?.username || '未登录'
  )
  const homeRoute = computed(
    () => ROLE_HOME_ROUTES[userRole.value] || '/login'
  )

  async function login(credentials: LoginRequest): Promise<void> {
    const res = await loginApi(credentials)
    const { accessToken, refreshToken: rt, user } = res.data.data

    token.value = accessToken
    refreshToken.value = rt
    userInfo.value = user
    writeSession({ accessToken, refreshToken: rt, user })
  }

  async function fetchUserInfo(): Promise<void> {
    const res = await getUserInfoApi()
    userInfo.value = res.data.data
    writeSession({
      accessToken: token.value,
      refreshToken: refreshToken.value,
      user: res.data.data,
    })
  }

  async function refreshAccessToken(): Promise<boolean> {
    try {
      const res = await refreshTokenApi(refreshToken.value)
      const { accessToken, refreshToken: newRt } = res.data.data
      token.value = accessToken
      refreshToken.value = newRt
      updateSessionTokens(accessToken, newRt)
      return true
    } catch {
      logout()
      return false
    }
  }

  function setUserInfo(info: UserInfo) {
    userInfo.value = info
    writeSession({
      accessToken: token.value,
      refreshToken: refreshToken.value,
      user: info,
    })
  }

  function clearSession(): void {
    token.value = ''
    refreshToken.value = ''
    userInfo.value = null
  }

  function logout(): void {
    clearSession()
    clearStoredSession()
    notifySessionExpired()
  }

  return {
    token,
    refreshToken,
    userInfo,
    isLoggedIn,
    userRole,
    displayName,
    homeRoute,
    login,
    fetchUserInfo,
    refreshAccessToken,
    setUserInfo,
    clearSession,
    logout,
  }
})
