# Sistema de Desarrollo por Especificaciones (SDD)
## Metodología aplicada en GEO SENTINEL

---

## 1. Visión general

GEO SENTINEL se desarrolla siguiendo un sistema de **Specification-Driven Development (SDD)**: antes de escribir cualquier línea de código, cada funcionalidad queda completamente definida en archivos Markdown estructurados. La IA de desarrollo lee esas especificaciones como contexto obligatorio y las usa como fuente de verdad durante la implementación.

El objetivo es eliminar la ambigüedad que produce código inconsistente cuando se le pide a una IA que implemente algo sin contexto suficiente. En lugar de describir lo que queremos en el prompt, lo describimos en specs permanentes y el prompt solo señala qué leer.

---

## 2. Herramientas y roles

| Herramienta | Rol en el flujo |
|-------------|-----------------|
| **Claude (claude.ai)** | Generación y revisión de especificaciones, detección de errores de diseño, generación de prompts optimizados para implementación |
| **Minimax M2.7** | Implementación de código a partir de los prompts y specs |
| **Vibe Coding** | Correcciones menores y puntuales sobre archivos concretos |

### Por qué esta separación

Claude es especialmente bueno razonando sobre arquitectura, detectando inconsistencias entre componentes y generando documentación técnica precisa. Minimax M1 es el agente de implementación: recibe contexto completo y produce código. Vibe Coding actúa como bisturí para correcciones quirúrgicas sin necesidad de recontextualizar todo el sistema.

---

## 3. Estructura del repositorio de especificaciones

```
proyecto/
│
├── AGENTS.md                          ← punto de entrada obligatorio para la IA
│
├── specs_estructurales/               ← reglas globales del sistema
│   ├── arquitectura.md
│   ├── arquitectura-frontend.md
│   ├── modelo-datos.md
│   ├── fuentes-datos.md
│   ├── seguridad.md
│   ├── estandares-codigo.md
│   ├── infraestructura.md
│   └── monitorizacion.md
│
└── specs_funcionales/                 ← comportamiento concreto por componente
    ├── ingesta/
    │   ├── usgs.md
    │   ├── firms.md
    │   ├── gdelt.md
    │   ├── acled.md
    │   ├── adsb.md
    │   ├── marinetraffic.md
    │   ├── aisstream.md
    │   ├── military-flights.md
    │   └── liveuamap.md
    ├── normalizacion/
    │   ├── modelo-canonico.md
    │   ├── actores.md
    │   ├── escala-severidad.md
    │   └── modelo-confianza.md
    ├── procesamiento/
    │   ├── validacion-quarantine.md
    │   ├── deduplicacion.md
    │   ├── clustering.md
    │   ├── ciclo-vida-incidente.md
    │   └── aoi.md
    ├── api/
    │   ├── incidents.md
    │   ├── aoi.md
    │   └── corrections.md
    └── ui/
        ├── dashboard.md
        ├── mapa-incidentes.md
        ├── tiempo-real.md
        ├── autenticacion-ui.md
        ├── correcciones-ui.md
        ├── aoi-ui.md
        └── refresh-controls.md
```

---

## 4. El archivo AGENTS.md

Es el único archivo que la IA lee en **cada prompt sin excepción**. Está diseñado para ser lo más corto posible (objetivo: < 150 líneas) porque se consume en cada interacción y su longitud impacta directamente en el coste de tokens.

Contiene exclusivamente:

**Regla obligatoria de lectura previa**: directiva explícita que indica que ninguna línea de código puede escribirse sin haber leído las specs correspondientes.

**Tabla de enrutamiento Tarea → Spec**: índice completo que mapea cada tipo de tarea al conjunto exacto de archivos que deben leerse. Organizada en dos bloques (estructurales y funcionales) y subdividida por capa (ingesta, normalización, procesamiento, API, UI).

**Combinaciones de contexto**: tabla que indica qué specs cargar simultáneamente para tareas complejas que tocan varias capas. Por ejemplo, implementar un ingestor requiere leer arquitectura + fuentes + estándares + la spec funcional + normalización + deduplicación + validación, todo junto.

**Decisiones de diseño**: lista numerada de decisiones ya tomadas y no negociables. Evita que la IA las contradiga en implementaciones locales. Ejemplo: `D4 — DBSCAN usa métrica mixta normalizada, no distancia euclidiana directa`.

**Convenciones de naming**: tabla de patrones de nomenclatura para archivos, clases, funciones y tests en backend y frontend.

**Restricciones de licencia**: recordatorio de qué datos no pueden redistribuirse en la API pública.

---

## 5. Tipos de especificaciones

### 5.1 Specs estructurales `[E-*]`

Definen las reglas inmutables del sistema. Son transversales: aplican a todos los componentes y tienen prioridad sobre cualquier decisión local en una spec funcional.

Responden a la pregunta: *¿cómo debe hacerse esto en este proyecto?*

Cubren:
- Arquitectura general y flujo de datos entre capas
- Modelo de datos canónico con DDL SQL completo
- Inventario de fuentes externas con URLs corregidas y contratos de API
- Seguridad: autenticación, scopes, restricciones de redistribución
- Estándares de código: linting, tipos, naming, tests mínimos
- Infraestructura: Docker, Kubernetes, variables de entorno, retry/backoff
- Monitorización: métricas obligatorias, SLAs de latencia por fuente

Cambiar una spec estructural requiere revisar todos los componentes que la referencian.

### 5.2 Specs funcionales `[F-*]`

Definen el comportamiento concreto de cada componente. Responden a la pregunta: *¿qué debe hacer exactamente este módulo?*

Referencian las specs estructurales pero no las repiten. Contienen:
- Contrato de entrada y salida
- Tabla de mapeo de campos (fuente → modelo canónico)
- Lógica de negocio específica (claves de deduplicación, reglas de anomalía, máquinas de estado)
- Casos de error y cómo tratarlos
- Tests obligatorios por componente
- Restricciones de seguridad aplicables

Son la fuente de verdad para los tests de integración y unitarios del componente que describen.

---

## 6. Flujo de trabajo completo

### Fase A — Diseño con Claude

Antes de implementar cualquier funcionalidad nueva:

1. **Definir la funcionalidad** en lenguaje natural con Claude, describiendo qué debe hacer y qué fuentes o componentes involucra.

2. **Claude revisa la coherencia** con las specs existentes: detecta conflictos, dependencias no declaradas, inconsistencias con el modelo de datos o con decisiones de diseño ya tomadas.

3. **Claude genera la spec** en formato Markdown siguiendo las convenciones del proyecto. Si es una fuente de datos nueva, actualiza también `fuentes-datos.md` con el bloque correspondiente. Si introduce un nuevo scope de autenticación, señala que debe actualizarse `seguridad.md`.

4. **Revisión manual** de la spec antes de incorporarla al repositorio. La spec es un contrato — los errores en ella se propagan a la implementación.

5. **Actualización de AGENTS.md**: añadir la nueva spec a la tabla de enrutamiento y, si aplica, a la tabla de combinaciones de contexto.

### Fase B — Implementación con Minimax M2.7

Con las specs listas y el AGENTS.md actualizado:

1. **Claude genera el prompt de implementación** optimizado. El prompt nunca describe la funcionalidad en prosa — solo indica qué archivos de spec leer y divide el trabajo en partes secuenciales con criterios de aceptación claros.

2. **El prompt tiene estructura fija**:
   - Lista de specs a leer (obligatoria, siempre primera)
   - División en partes numeradas (máximo 3 por prompt)
   - Cada parte con: qué implementar, en qué archivo, qué comportamiento exacto
   - Tests obligatorios al final
   - Restricciones críticas recordadas explícitamente (seguridad, naming, UTC)

3. **Minimax M1 implementa parte por parte**. No se avanza a la siguiente parte sin confirmar que la anterior funciona.

4. **Verificación** tras cada parte: ejecutar tests, comprobar en BD que los datos son correctos, revisar que no hay API keys hardcodeadas, que los timestamps son UTC.

### Fase C — Correcciones con Vibe Coding

Para correcciones menores y puntuales (no nuevas funcionalidades):

1. Identificar el problema con precisión: archivo concreto, línea o función afectada, comportamiento actual vs comportamiento esperado.

2. Indicar a Vibe Coding exactamente qué cambiar y dónde, sin recontextualizar todo el sistema. Ejemplo: *"En `components/map/LayerControls.tsx` el botón TRACKS está hardcodeado como desactivado. Cambiar para que active la capa `'military-flights-layer'` de Deck.gl."*

3. Vibe Coding no necesita leer las specs — la instrucción es suficientemente precisa. Si la corrección afecta a más de un archivo o implica una decisión de diseño, volver a la Fase A.

---

## 7. Reglas operativas

### Lo que nunca se hace en un solo prompt

- Implementar más de tres componentes a la vez
- Pedir "implementa todo el sistema" o "implementa esta feature completa"
- Escribir código antes de tener las specs en el repositorio
- Modificar una spec estructural sin revisar los componentes que la referencian

### Lo que siempre se hace antes de implementar

- Verificar que la spec nueva no contradice ninguna decisión de diseño de AGENTS.md
- Comprobar que las URLs de APIs externas son correctas (varias estaban mal en el documento original del proyecto)
- Asegurarse de que el AGENTS.md tiene la entrada de enrutamiento para la nueva spec

### Lo que siempre se hace después de implementar

- Ejecutar los tests definidos en la spec funcional
- Comprobar que no hay datos sensibles hardcodeados (API keys, credenciales)
- Verificar que los timestamps son TIMESTAMPTZ UTC en BD
- Commit por fase, no acumulado

---

## 8. Por qué funciona este sistema

**Contexto consistente**: la IA siempre trabaja con las mismas definiciones. No hay deriva entre lo que se implementó en la Fase 3 y lo que se implementa en la Fase 7 porque ambas leen el mismo modelo canónico.

**Errores detectados antes de codificar**: Claude puede detectar inconsistencias entre specs (URL malformada, campo que no existe en el modelo, scope no declarado) antes de que Minimax M1 produzca código basado en esas inconsistencias.

**Prompts pequeños y enfocados**: la ventana de contexto de la IA de implementación no se satura. Cada prompt carga solo las specs relevantes para la tarea concreta. Cuando el contexto es demasiado grande, la IA empieza a inventar detalles que no están en las specs.

**Trazabilidad**: cada decisión de diseño está documentada en AGENTS.md con su número (D1, D2... D19). Si algo falla en producción, se puede rastrear a qué decisión de diseño responde y si fue implementada correctamente.

**Separación de responsabilidades entre herramientas**: Claude razona sobre diseño y genera especificaciones y prompts. Minimax M1 implementa sin tomar decisiones de arquitectura. Vibe Coding corrige sin necesitar contexto global. Cada herramienta hace lo que mejor sabe hacer.