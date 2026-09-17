import { api } from './http.js'

export const listUsers = (options) => api.get('/api/users', options)

export const getUser = (id, options) => api.get(`/api/users/${id}`, options)

export const createUser = (data) => api.post('/api/users', data)

export const updateUser = (id, data) => api.put(`/api/users/${id}`, data)

export const deleteUser = (id) => api.del(`/api/users/${id}`)

export const saveUserPermissions = (id, permissions) => api.post(`/api/users/${id}/permissions`, { permissions })