import { api } from './http.js'

export const listAccounts = () => api.get('/api/accounts')

export const getAccount = (id) => api.get(`/api/accounts/${id}`)

export const createAccount = (data) => api.post('/api/accounts', data)

export const updateAccount = (id, data) => api.put(`/api/accounts/${id}`, data)

export const deleteAccount = (id) => api.del(`/api/accounts/${id}`)