import { api } from './http.js'

export const totpSetup = () => api.post('/api/auth/totp/setup')

export const totpConfirm = (code) => api.post('/api/auth/totp/confirm', { code })

export const totpDisable = (code) => api.post('/api/auth/totp/disable', { code })