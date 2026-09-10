import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { api, clearToken, getToken, setToken } from './api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(getToken()))

  useEffect(() => {
    if (!getToken()) return
    api
      .get('/api/auth/me')
      .then((u) => setUser(u))
      .catch(() => clearToken())
      .finally(() => setLoading(false))
  }, [])

  const login = async (username, password) => {
    const data = await api.post('/api/auth/login', { username, password })
    setToken(data.access_token)
    setUser(data.user)
    return data.user
  }

  const logout = () => {
    clearToken()
    setUser(null)
  }

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}