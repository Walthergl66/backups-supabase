import { api } from './http.js'

export const getDashboard = () => api.get('/api/dashboard')