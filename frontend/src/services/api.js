import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  headers: {
    'Content-Type': 'application/json',
  },
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('mnraw_token')
  if (token) {
    config.headers.Authorization = `Token ${token}`
  }
  // Let the browser set multipart boundaries for FormData uploads.
  if (typeof FormData !== 'undefined' && config.data instanceof FormData) {
    if (config.headers && 'Content-Type' in config.headers) {
      delete config.headers['Content-Type']
    }
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail =
      error.response?.data?.detail ||
      error.response?.data?.errors ||
      error.message ||
      'Request failed'
    return Promise.reject(
      typeof detail === 'string' ? new Error(detail) : new Error(JSON.stringify(detail)),
    )
  },
)

export default api
