import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1'

const client = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor: attach JWT
client.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('bf_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor: handle 401 and refresh
let isRefreshing = false
let failedQueue = []

function processQueue(error, token = null) {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else {
      prom.resolve(token)
    }
  })
}

client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const { response } = error
    const originalRequest = error.config

    if (response?.status === 401 && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      try {
        const refreshToken = localStorage.getItem('bf_refresh_token')
        const { data } = await axios.post(
          `${API_BASE}/auth/refresh`,
          { refresh_token: refreshToken }
        )

        localStorage.setItem('bf_token', data.access_token)
        localStorage.setItem('bf_refresh_token', data.refresh_token)

        client.defaults.headers.common.Authorization = `Bearer ${data.access_token}`
        processQueue(null, data.access_token)
        originalRequest.headers.Authorization = `Bearer ${data.access_token}`

        return client(originalRequest)
      } catch (err) {
        processQueue(err, null)
        localStorage.removeItem('bf_token')
        localStorage.removeItem('bf_refresh_token')
        window.location.href = '/login'
        return Promise.reject(err)
      } finally {
        isRefreshing = false
      }
    }

    return Promise.reject(error)
  }
)

export default client

export const api = {
  get: (url, params) => client.get(url, { params }),
  post: (url, data) => client.post(url, data),
  put: (url, data) => client.put(url, data),
  patch: (url, data) => client.patch(url, data),
  delete: (url) => client.delete(url),
}