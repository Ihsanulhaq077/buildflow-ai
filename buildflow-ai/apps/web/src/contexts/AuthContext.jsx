import React, { createContext, useContext, useEffect, useState, useCallback } from 'react'
import { api } from '../api/client'

const AuthContext = createContext()

export function useAuth() {
  return useContext(AuthContext)
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchMe = useCallback(async () => {
    try {
      const { data } = await api.get('/users/me')
      setUser(data)
    } catch (err) {
      console.error('Failed to fetch user:', err)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    const token = localStorage.getItem('bf_token')
    if (token) {
      fetchMe()
    } else {
      setLoading(false)
    }
  }, [fetchMe])

  const login = async (email, password) => {
    try {
      const { data } = await api.post('/auth/login', { email, password })
      localStorage.setItem('bf_token', data.access_token)
      localStorage.setItem('bf_refresh_token', data.refresh_token)
      await fetchMe()
      return { success: true, data }
    } catch (err) {
      const message = err.response?.data?.detail || 'Login failed'
      setError(message)
      return { success: false, error: message }
    }
  }

  const register = async (orgData, userData) => {
    try {
      const { data } = await api.post('/auth/register-organization', {
        organization: orgData,
        user: userData,
      })
      localStorage.setItem('bf_token', data.access_token)
      localStorage.setItem('bf_refresh_token', data.refresh_token)
      await fetchMe()
      return { success: true, data }
    } catch (err) {
      const message = err.response?.data?.detail || 'Registration failed'
      setError(message)
      return { success: false, error: message }
    }
  }

  const logout = () => {
    localStorage.removeItem('bf_token')
    localStorage.removeItem('bf_refresh_token')
    setUser(null)
    window.location.href = '/login'
  }

  const value = {
    user,
    loading,
    error,
    login,
    register,
    logout,
    isAuthenticated: !!user,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}