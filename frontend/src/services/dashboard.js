import { api } from './http.js'

export const getDashboard = (options) => api.get('/api/dashboard', options)