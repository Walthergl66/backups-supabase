import { api } from './http.js'

export const listWebUsers = () => api.get('/api/web-users')

export const getWebUser = (id) => api.get(`/api/web-users/${id}`)

export const createWebUser = (data) => api.post('/api/web-users', data)

export const updateWebUser = (id, data) => api.put(`/api/web-users/${id}`, data)

export const deleteWebUser = (id) => api.del(`/api/web-users/${id}`)