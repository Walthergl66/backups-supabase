import { api } from './http.js'

export const listAudit = (limit = 200) => api.get(`/api/audit?limit=${limit}`)