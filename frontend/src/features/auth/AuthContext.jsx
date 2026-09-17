import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { clearToken, getToken, setToken } from '../../services/http.js'
import * as authService from '../../services/auth.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(Boolean(getToken()))

  useEffect(() => {
    if (!getToken()) return
    authService
      .me()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setLoading(false))
  }, [])

  const login = async (username, password, code) => {
    const data = await authService.login(username, password, code)
    setToken(data.access_token)
    setUser(data.user)
    return data.user
  }

  const logout = async () => {
    try {
      // Primero se revoca la sesión en el servidor (con el Bearer del access
      // token en el header), para que el JWT entre en la blacklist.
      await authService.logoutRemote()
    } catch {
      // Si falla la red o el servidor, se cierra la sesión local igualmente.
    } finally {
      clearToken()
      setUser(null)
    }
  }

  const value = useMemo(() => ({ user, loading, login, logout }), [user, loading])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}