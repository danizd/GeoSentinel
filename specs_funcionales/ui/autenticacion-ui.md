# F-UI-AUTH — Autenticación UI

> Cargar junto con: `E-ARCH-FRONT` + `E-SEC`

## 1. Flujo de autenticación

```
Usuario accede → ¿token válido en authStore?
  SÍ → Dashboard
  NO → Login page → POST /v1/auth/login → guardar JWT → Dashboard
```

## 2. Login page

Ruta: `/login`
Estética: centrado, fondo oscuro, panel glassmorphism, sin sidebar ni topbar.

```
┌─────────────────────────────┐
│                             │
│     GEO SENTINEL            │
│     TACTICAL C2             │
│                             │
│  EMAIL ________________     │
│  PASSWORD ______________    │
│                             │
│  [  AUTHENTICATE  ]         │
│                             │
└─────────────────────────────┘
```

Sin registro público. El acceso es por invitación (gestión de usuarios en backend).

## 3. Zustand authStore

```typescript
interface AuthStore {
  token: string | null
  scopes: string[]       // ['incidents:read', 'corrections:write', ...]
  setAuth: (token: string, scopes: string[]) => void
  clearAuth: () => void
  hasScope: (scope: string) => boolean
}
```

- Token persistido en `localStorage` (única excepción a la regla de no localStorage — ver nota)
- Al iniciar la app → verificar expiración del token antes de usarlo
- Si token expirado → `clearAuth()` → redirect a `/login`

> **Nota**: El token JWT se guarda en localStorage por simplicidad en esta versión.
> En versiones futuras evaluar httpOnly cookies para mayor seguridad (ver `E-SEC`).

## 4. Protección de rutas

```typescript
// pages/ProtectedRoute.tsx
function ProtectedRoute({ children }: { children: ReactNode }) {
  const { token } = useAuthStore()
  if (!token) return <Navigate to="/login" replace />
  return children
}
```

## 5. Control de visibilidad por scope

Los botones de corrección y gestión de AOI solo se renderizan si el usuario tiene el scope necesario:

```typescript
function CorrectionButtons({ incidentId }: { incidentId: string }) {
  const { hasScope } = useAuthStore()
  if (!hasScope('corrections:write')) return null
  return <CorrectionsPanel incidentId={incidentId} />
}
```

**Nunca** confiar solo en ocultar el botón — el backend siempre valida el scope en `E-SEC`.

## 6. Expiración de sesión

- Token expirando en < 5 min → banner: "Sesión expirando — [RENOVAR]"
- Token expirado durante uso → interceptor en el cliente API → redirect a `/login`
- Al hacer login de nuevo → volver a la URL original que estaba visitando

## 7. Interceptor de API

```typescript
// api/client.ts — axios o fetch wrapper
function apiClient(url: string, options: RequestInit = {}) {
  const { token } = useAuthStore.getState()
  const response = await fetch(`${VITE_API_BASE_URL}${url}`, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options.headers,
    }
  })
  if (response.status === 401) {
    useAuthStore.getState().clearAuth()
    window.location.href = '/login'
  }
  return response
}
```
