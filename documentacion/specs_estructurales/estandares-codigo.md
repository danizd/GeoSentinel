# E-STD — Estándares de Código

> **Spec estructural / transversal** — Obligatoria SIEMPRE.

## 1. Python

- Versión: 3.12+
- Formatter: `ruff format` (línea máx. 100 chars)
- Linter: `ruff check` con reglas `E,W,F,I,UP,B,SIM`
- Type checking: `mypy --strict` en módulos nuevos
- Docstrings: Google style en funciones públicas

## 2. Convenciones de naming

| Elemento | Convención | Ejemplo |
|----------|-----------|---------|
| Tabla SQL | `snake_case` plural | `events_canonical` |
| Campo SQL | `snake_case` | `event_time` |
| Clase Python | `PascalCase` | `FirmsIngestor` |
| Función/método | `snake_case` | `normalize_event_time` |
| Constante | `UPPER_SNAKE_CASE` | `MAX_RETRY_ATTEMPTS` |
| Variable de entorno | `UPPER_SNAKE_CASE` | `FIRMS_MAP_KEY` |

## 3. Tests

- Framework: `pytest`
- Coverage mínimo: 80% en módulos de normalización y clustering
- Tests obligatorios por componente: ver §5.5 de `AGENTS.md`
- Fixtures con datos reales anonimizados en `tests/fixtures/`

## 4. Migraciones de BD

- Herramienta: `alembic`
- Una migración = un cambio atómico
- Nunca DROP en migraciones automáticas; siempre revisión manual

## 5. Gestión de dependencias

- `uv` para gestión de entorno y dependencias
- `pyproject.toml` como fuente de verdad
- Dependencias de producción y desarrollo separadas
