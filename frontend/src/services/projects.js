import { api } from './http.js'

export const listProjects = (estado = 'activos', options) => api.get(`/api/projects?estado=${estado}`, options)

export const listActiveProjects = (options) => api.get('/api/projects/active', options)

export const getProject = (id, options) => api.get(`/api/projects/${id}`, options)

export const createProject = (data) => api.post('/api/projects', data)

export const updateProject = (id, data) => api.put(`/api/projects/${id}`, data)

export const deleteProject = (id) => api.del(`/api/projects/${id}`)

export const restoreProject = (id, slug) => api.post(`/api/projects/${id}/restore`, { slug })

export const getProjectHistory = (id, options) => api.get(`/api/projects/${id}/history`, options)