import { api } from './http.js'

export const listAccounts = (options) => api.get('/api/accounts', options)

export const getAccount = (id, options) => api.get(`/api/accounts/${id}`, options)

export const createAccount = (data) => api.post('/api/accounts', data)

export const updateAccount = (id, data) => api.put(`/api/accounts/${id}`, data)

export const deleteAccount = (id) => api.del(`/api/accounts/${id}`)