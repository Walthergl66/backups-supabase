import { api } from './http.js'

export const login = (username, password, code) => {
  const body = { username, password }
  if (code) body.code = code
  return api.post('/api/auth/login', body)
}

export const me = () => api.get('/api/auth/me')

export const logoutRemote = () => api.post('/api/auth/logout')