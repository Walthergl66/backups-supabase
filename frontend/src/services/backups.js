import { api } from './http.js'

export const listBackups = () => api.get('/api/backups')