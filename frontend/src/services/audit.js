import { api } from './http.js'

export const listAudit = (page = 1, pageSize = 50) =>
  api.get(`/api/audit?page=${page}&page_size=${pageSize}`)