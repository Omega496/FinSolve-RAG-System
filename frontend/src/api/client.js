/**
 * Base fetch wrapper — ALWAYS includes credentials: 'include'
 * 
 * This is non-negotiable per AGNNTS.md:
 * - All fetch calls include credentials: 'include'
 * - Required for httpOnly cookie auth
 * - Never use localStorage/sessionStorage for tokens
 */

const API_BASE = ''  // Same origin — Vite proxies to backend

export async function apiClient(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`

  const config = {
    ...options,
    credentials: 'include',  // ALWAYS include httpOnly cookies
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  }

  // Remove Content-Type for FormData (browser sets it automatically with boundary)
  if (options.body instanceof FormData) {
    delete config.headers['Content-Type']
  }

  try {
    const response = await fetch(url, config)

    // Handle 401 — redirect to login
    if (response.status === 401) {
      window.location.href = '/'
      throw new Error('Unauthorized')
    }

    return response
  } catch (error) {
    console.error(`API error: ${endpoint}`, error)
    throw error
  }
}

/**
 * GET request helper
 */
export async function apiGet(endpoint) {
  return apiClient(endpoint, { method: 'GET' })
}

/**
 * POST request helper
 */
export async function apiPost(endpoint, body) {
  return apiClient(endpoint, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

/**
 * SSE streaming helper for /query endpoint
 * Returns ReadableStream reader for progressive token rendering
 */
export async function apiStream(endpoint, body) {
  const url = `${API_BASE}${endpoint}`

  const response = await fetch(url, {
    method: 'POST',
    credentials: 'include',  // ALWAYS include
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    throw new Error(`Stream error: ${response.status}`)
  }

  return response.body.getReader()
}
