export const CATEGORY_HEX: Record<string, string> = {
  conflict: '#ef4444',
  wildfire: '#f97316',
  disaster_natural: '#06b6d4',
  mobility: '#38bdf8',
  humanitarian: '#fbbf24',
  thermal_anomaly: '#ea580c',
  other: '#64748b',
  default: '#38bdf8',
}

export function getCategoryHex(category: string): string {
  return CATEGORY_HEX[category] || CATEGORY_HEX.default
}

export function hexToRgb(hex: string): [number, number, number] {
  const r = parseInt(hex.slice(1, 3), 16)
  const g = parseInt(hex.slice(3, 5), 16)
  const b = parseInt(hex.slice(5, 7), 16)
  return [r, g, b]
}

const EVENT_TYPE_COLORS: Record<string, [number, number, number]> = {
  conflict_battle: [239, 68, 68],
  conflict_airstrike: [249, 115, 22],
  conflict_explosion: [251, 146, 60],
  conflict_atrocity: [168, 85, 247],
  conflict_criminal: [220, 38, 38],
  conflict_terror: [185, 28, 28],
  conflict_civilian_violence: [217, 70, 239],
  conflict_strategic: [59, 130, 246],
  conflict_unknown: [148, 163, 184],
  social_protest: [236, 72, 153],
  social_riot: [244, 114, 182],
  earthquake: [168, 85, 247],
  explosion_seismic: [124, 58, 237],
  quarry_blast: [139, 92, 246],
  ice_quake: [99, 102, 241],
  sonic_boom: [79, 70, 229],
  wildfire_hotspot: [249, 115, 22],
  volcanic_hotspot: [234, 88, 12],
  other_hotspot: [253, 186, 116],
  offshore_hotspot: [253, 186, 116],
  thermal_anomaly_suspected: [234, 88, 12],
  military_flight: [37, 99, 235],
}

const CATEGORY_RGB: Record<string, [number, number, number]> = {
  conflict: [239, 68, 68],
  wildfire: [249, 115, 22],
  disaster_natural: [6, 182, 212],
  mobility: [56, 189, 248],
  humanitarian: [251, 191, 36],
  thermal_anomaly: [234, 88, 12],
  other: [100, 116, 139],
}

const EVENT_TYPE_LABELS: Record<string, string> = {
  conflict_battle: 'Batalla armada',
  conflict_airstrike: 'Ataque aéreo',
  conflict_explosion: 'Explosión',
  conflict_atrocity: 'Atrocidad',
  conflict_criminal: 'Violencia criminal',
  conflict_terror: 'Terrorismo',
  conflict_civilian_violence: 'Violencia contra civiles',
  conflict_strategic: 'Movimiento estratégico',
  conflict_unknown: 'Conflicto no clasificado',
  social_protest: 'Protesta social',
  social_riot: 'Disturbio',
  earthquake: 'Terremoto',
  explosion_seismic: 'Explosión sísmica',
  quarry_blast: 'Voladura de cantera',
  ice_quake: 'Terremoto de hielo',
  sonic_boom: 'Explosión sónica',
  wildfire_hotspot: 'Incendio activo',
  volcanic_hotspot: 'Punto volcánico',
  other_hotspot: 'Punto de calor',
  offshore_hotspot: 'Foco marino',
  thermal_anomaly_suspected: 'Anomalía térmica sospechosa',
  military_flight: 'Vuelo militar',
}

export function getEventTypeColor(eventType: string): [number, number, number] {
  return EVENT_TYPE_COLORS[eventType] || [56, 189, 248]
}

export function getIncidentColor(eventType: string, category: string): [number, number, number] {
  return EVENT_TYPE_COLORS[eventType] || CATEGORY_RGB[category] || [56, 189, 248]
}

const SEVERITY_COLORS: [number, number, number][] = [
  [34, 197, 94],
  [34, 197, 94],
  [132, 204, 22],
  [132, 204, 22],
  [234, 179, 8],
  [234, 179, 8],
  [249, 115, 22],
  [249, 115, 22],
  [239, 68, 68],
  [239, 68, 68],
  [185, 28, 28],
]

export function getSeverityColor(severity: number): string {
  const idx = Math.min(Math.floor(severity), 10)
  const [r, g, b] = SEVERITY_COLORS[idx]
  return `rgb(${r},${g},${b})`
}

export function getHeadline(incident: {
  raw_payload?: { title?: string; [key: string]: unknown } | null
  event_type: string
}): string {
  if (incident.raw_payload?.title) {
    return incident.raw_payload.title
  }
  return EVENT_TYPE_LABELS[incident.event_type]
    || incident.event_type.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}
