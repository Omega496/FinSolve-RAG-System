import { createContext, useContext, useState, useEffect } from 'react'
import { apiGet, apiPost } from '../api/client.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // Check auth status on mount
  useEffect(() => {
    checkAuth()
  }, [])

  async function checkAuth() {
    try {
      const response = await apiGet('/auth/me')
      if (response.ok) {
        const data = await response.json()
        setUser(data)
      }
    } catch (error) {
      // Not authenticated
    } finally {
      setLoading(false)
    }
  }

  async function login(email, password) {
    const response = await apiPost('/auth/login', { email, password })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Login failed')
    }
    const data = await response.json()
    await checkAuth()  // Refresh user state
    return data
  }

  async function logout() {
    await apiPost('/auth/logout', {})
    setUser(null)
  }

  const value = {
    user,
    loading,
    login,
    logout,
    isAuthenticated: !!user,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
