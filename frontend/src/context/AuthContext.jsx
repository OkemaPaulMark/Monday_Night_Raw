import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { authApi } from '../services/endpoints'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [token, setToken] = useState(() => localStorage.getItem('mnraw_token'))
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    async function boot() {
      if (!token) {
        setLoading(false)
        return
      }
      try {
        const me = await authApi.me()
        if (!cancelled) setUser(me)
      } catch {
        localStorage.removeItem('mnraw_token')
        if (!cancelled) {
          setToken(null)
          setUser(null)
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    boot()
    return () => {
      cancelled = true
    }
  }, [token])

  const value = useMemo(
    () => ({
      user,
      token,
      loading,
      isAdmin: Boolean(user?.is_app_admin || user?.role === 'ADMIN'),
      async login(username, password) {
        const data = await authApi.login(username, password)
        localStorage.setItem('mnraw_token', data.token)
        setToken(data.token)
        setUser(data.user)
        return data.user
      },
      async register(payload) {
        const data = await authApi.register(payload)
        localStorage.setItem('mnraw_token', data.token)
        setToken(data.token)
        setUser(data.user)
        return data.user
      },
      async logout() {
        try {
          await authApi.logout()
        } catch {
          /* ignore */
        }
        localStorage.removeItem('mnraw_token')
        setToken(null)
        setUser(null)
      },
    }),
    [user, token, loading],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
