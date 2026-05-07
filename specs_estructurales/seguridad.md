# E-SEC — Seguridad

> **Spec estructural / transversal**

## 1. Autenticación de la API

- JWT (RS256) en header `Authorization: Bearer <token>`
- Tokens con expiración máxima de 24h; refresh tokens de 30 días
- Scopes: `incidents:read`, `incidents:write`, `corrections:write`, `aoi:manage`

## 2. Secretos

- **Nunca en código fuente ni en variables de entorno de imagen Docker**
- Desarrollo: archivo `.env` (en `.gitignore`)
- Producción: Kubernetes Secrets cifrados con KMS
- Rotación de API keys de fuentes externas: mínimo anual o tras incidente

## 3. Rate limiting de la API propia

- `100 req/min` por token autenticado
- `10 req/min` para endpoints de escritura (`/corrections`)
- Respuesta `429` con header `Retry-After`

## 4. Restricciones de redistribución de datos

La API `/incidents` **nunca debe exponer**:
- Campos raw de MarineTraffic o ADS-B Exchange en formato redistribuible
- Datos ACLED en contextos comerciales sin autorización explícita
- Identificadores de aeronaves o buques individuales en endpoints públicos

## 5. Logging y auditoría

- Toda corrección humana → `corrections_audit` (append-only, nunca borrar)
- Logs de acceso a la API: retención mínima 90 días
- Datos personales en logs: prohibido (IPs anonimizadas tras 30 días)
