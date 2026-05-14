import { create } from 'zustand'

interface AuthStore {
  token: string | null
  scopes: string[]
  setAuth: (token: string, scopes: string[]) => void
  clearAuth: () => void
  hasScope: (scope: string) => boolean
}

const DEV_SCOPES = ['admin:run', 'incidents:read', 'incidents:write', 'corrections:write', 'aoi:manage']

function getInitialScopes(): string[] {
  const stored = localStorage.getItem('gs_scopes')
  if (stored) {
    try {
      const parsed = JSON.parse(stored)
      if (Array.isArray(parsed) && parsed.length > 0) return parsed
    } catch { /* ignore */ }
  }
  return import.meta.env.DEV ? DEV_SCOPES : []
}

export const useAuthStore = create<AuthStore>((set, get) => ({
  token: localStorage.getItem('gs_token'),
  scopes: getInitialScopes(),

  setAuth: (token, scopes) => {
    localStorage.setItem('gs_token', token)
    localStorage.setItem('gs_scopes', JSON.stringify(scopes))
    set({ token, scopes })
  },

  clearAuth: () => {
    localStorage.removeItem('gs_token')
    localStorage.removeItem('gs_scopes')
    set({ token: null, scopes: [] })
  },

  hasScope: (scope) => get().scopes.includes(scope),
}))