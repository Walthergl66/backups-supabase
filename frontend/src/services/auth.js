import { api } from './http.js'

export const login = (username, password) => api.post('/api/auth/login', { username, password })

export const me = () => api.get('/api/auth/me')

export const logoutRemote = () => api.post('/api/auth/logout')