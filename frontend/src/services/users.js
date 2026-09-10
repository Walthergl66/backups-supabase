import { api } from './http.js'

export const listUsers = () => api.get('/api/users')

export const getUser = (id) => api.get(`/api/users/${id}`)

export const createUser = (data) => api.post('/api/users', data)

export const updateUser = (id, data) => api.put(`/api/users/${id}`, data)

export const deleteUser = (id) => api.del(`/api/users/${id}`)

export const saveUserPermissions = (id, permissions) => api.post(`/api/users/${id}/permissions`, { permissions })