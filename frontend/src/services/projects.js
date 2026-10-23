import { api } from './http.js'

export const listProjects = (estado = 'activos', provider = '') => {
  const params = new URLSearchParams({ estado })
  if (provider) params.set('provider', provider)
  return api.get(`/api/projects?${params.toString()}`)
}

export const listActiveProjects = () => api.get('/api/projects/active')

export const getProject = (id) => api.get(`/api/projects/${id}`)

export const createProject = (data) => api.post('/api/projects', data)

export const updateProject = (id, data) => api.put(`/api/projects/${id}`, data)

export const deleteProject = (id) => api.del(`/api/projects/${id}`)

export const restoreProject = (id, slug) => api.post(`/api/projects/${id}/restore`, { slug })

export const getProjectHistory = (id) => api.get(`/api/projects/${id}/history`)

export const testProjectConnection = (connection, provider = 'postgres') =>
  api.post('/api/projects/test-connection', { connection, provider })
