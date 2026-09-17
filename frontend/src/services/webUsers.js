import { api } from './http.js'

export const listWebUsers = (options) => api.get('/api/web-users', options)

export const getWebUser = (id, options) => api.get(`/api/web-users/${id}`, options)

export const createWebUser = (data) => api.post('/api/web-users', data)

export const updateWebUser = (id, data) => api.put(`/api/web-users/${id}`, data)

export const deleteWebUser = (id) => api.del(`/api/web-users/${id}`)