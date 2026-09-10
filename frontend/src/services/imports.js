import { api } from './http.js'

export const fetchAvailableProjects = (pat) => api.post('/api/import/fetch', { pat })

export const createImportedProjects = (payload) => api.post('/api/import/create', payload)