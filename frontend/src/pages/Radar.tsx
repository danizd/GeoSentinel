import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Map, { NavigationControl, Source, Layer, type MapRef } from 'react-map-gl'
import 'mapbox-gl/dist/mapbox-gl.css'
import { AnimatePresence, motion } from 'framer-motion'
import { Link } from 'react-router-dom'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, ArrowLeft, ChevronDown, ExternalLink, Loader2, RefreshCw, X } from 'lucide-react'
import {
  CR360_COUNTRIES,
  RADAR_POLL_MS,
  RADAR_TITLE,
  cr360IconUrl,
  cr360MediaUrl,
  fetchCr360Event,
  fetchCr360Events,
  fetchCr360Regions,
  fetchCr360Roads,
} from '../api/cr360'
import type {
  Cr360EventDetail,
  Cr360EventFeature,
  Cr360RegionFeature,
  Cr360RoadFeature,
} from '../types/cr360'

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || ''
const MAP_STYLE = 'mapbox://styles/mapbox/satellite-streets-v12'

const DEFAULT_VIEWPORT = {
  longitude: 20,
  latitude: 50,
  zoom: 3.4,
  pitch: 0,
  bearing: 0,
}

const COUNTRY_META: Record<string, { flag: string; name: string; color: string }> = {
  ESP: { flag: '🇪🇸', name: 'España', color: '#c60b1e' },
  RUS: { flag: '🇷🇺', name: 'Rusia', color: '#3b82f6' },
  UKR: { flag: '🇺🇦', name: 'Ucrania', color: '#eab308' },
}

const SEVERITY_META: Record<string, { color: string; label: string }> = {
  CRITICAL: { color: '#ef4444', label: 'CRÍTICA' },
  HIGH: { color: '#f97316', label: 'ALTA' },
  MEDIUM: { color: '#eab308', label: 'MEDIA' },
  LOW: { color: '#22c55e', label: 'BAJA' },
}

function countryMeta(code: string): { flag: string; name: string; color: string } {
  return COUNTRY_META[code] || { flag: '🏳️', name: code, color: '#64748b' }
}

const OWNER_LABELS: Record<string, string> = {
  CONFLICT: 'Conflicto',
  CRIMINAL_GROUP: 'Grupo criminal',
  FORCE: 'Fuerza',
}

/** Título con valor real: descarta popupTitle genéricos tipo "Región 12345". */
function regionTitle(p: Cr360RegionFeature['properties']): string {
  const t = p.popupTitle?.trim()
  if (t && !/^regi[oó]n\s+\d+$/i.test(t)) return t
  if (p.criminalGroupName) return p.criminalGroupName
  if (p.forceName) return p.forceName
  if (p.conflictName) return p.conflictName
  return `Región ${p.id}`
}

/** Área aproximada en km² calculada de la geometría (proyección equirectangular). */
function regionAreaKm2(feature: Cr360RegionFeature): number | null {
  const polys = feature.geometry.type === 'MultiPolygon'
    ? feature.geometry.coordinates
    : [feature.geometry.coordinates]
  const R = 6371
  let area = 0
  for (const poly of polys) {
    for (const ring of poly) {
      if (ring.length < 4) continue
      let sum = 0
      for (let i = 0; i < ring.length - 1; i++) {
        const [lon1, lat1] = ring[i]
        const [lon2, lat2] = ring[i + 1]
        sum += (lon2 - lon1) * (Math.PI / 180) * ((lat1 + lat2) * (Math.PI / 180))
      }
      area += Math.abs(sum) / 2 * R * R
    }
  }
  return area > 0 ? area : null
}

function fmtArea(km2: number): string {
  if (km2 >= 1000) return `≈ ${Math.round(km2 / 100) / 10} mil km²`
  return `≈ ${Math.round(km2)} km²`
}

function fmtDate(iso: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (isNaN(date.getTime())) return '—'
  return date.toLocaleString('es-ES', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }) + ' UTC'
}

/** Días transcurridos desde la fecha del evento (granularidad día, sin desvíos de TZ). */
function eventAgeDays(iso: string | null): number | null {
  if (!iso) return null
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso)
  if (!m) return null
  const day = Date.UTC(+m[1], +m[2] - 1, +m[3])
  const now = new Date()
  const today = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate())
  return Math.round((today - day) / 86400000)
}

/** Línea de fecha para tooltip: "Hoy · 25 ago 2026", "Ayer · 24 ago 2026", "22 ago 2026 · hace 3 días". */
function eventDateLine(iso: string | null): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso || '')
  if (!m) return '—'
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3]))
  const dateStr = d.toLocaleDateString('es-ES', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
  const age = eventAgeDays(iso)
  if (age === 0) return `Hoy · ${dateStr}`
  if (age === 1) return `Ayer · ${dateStr}`
  if (age !== null && age > 1) return `${dateStr} · hace ${age} días`
  return dateStr
}

/** Factor de escala visual por antigüedad (1 = hoy → 0.78 a los 3 días; lineal). */
function ageFactor(age: number): number {
  if (age <= 0) return 1
  if (age >= 3) return 0.78
  return 1 - (age / 3) * 0.22
}

/** Opacidad por antigüedad (1 = hoy → 0.5 a los 3 días; lineal). */
function ageAlpha(age: number): number {
  if (age <= 0) return 1
  if (age >= 3) return 0.5
  return 1 - (age / 3) * 0.5
}

/** Id de imagen en Mapbox para un icono de CR360 (solo caracteres seguros). */
function iconImageId(publicId: string): string {
  return 'cr360-icon-' + publicId.replace(/[^a-zA-Z0-9]/g, '-')
}

/** Convierte un enlace de post de Telegram en su URL de embebido oficial (?embed=1). */
function telegramEmbedUrl(url: string): string {
  const sep = url.includes('?') ? '&' : '?'
  return url + sep + 'embed=1'
}

/** Imagen de icono con ocultado silencioso si no resuelve. */
function IconImg({ url, className }: { url: string | null; className: string }) {
  const [hidden, setHidden] = useState(false)
  if (!url || hidden) return null
  return <img src={url} alt="" className={className} loading="lazy" onError={() => setHidden(true)} />
}

/** Panel modal acoplado al borde izquierdo de la pantalla. */
function LeftPanel({ onClose, children }: { onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="absolute left-0 top-0 bottom-0 z-40 w-full sm:w-[400px] pointer-events-none">
      <motion.div
        initial={{ opacity: 0, x: -24 }}
        animate={{ opacity: 1, x: 0 }}
        exit={{ opacity: 0, x: -24 }}
        transition={{ duration: 0.18 }}
        className="pointer-events-auto h-full panel-glass overflow-y-auto p-4 font-mono text-xs shadow-2xl"
      >
        <div className="flex items-start justify-between gap-3 mb-3">
          <div className="min-w-0 flex-1">{children}</div>
          <button onClick={onClose} className="shrink-0 text-text-secondary hover:text-white text-lg leading-none">
            <X size={18} />
          </button>
        </div>
      </motion.div>
    </div>
  )
}

interface HoverState {
  x: number
  y: number
  kind: 'event' | 'road' | 'region'
  id: number
}

function EventTooltip({ hover, events }: { hover: HoverState; events: Cr360EventFeature[] }) {
  const feature = events.find(f => f.properties.id === hover.id)
  if (!feature) return null
  const meta = countryMeta(feature.properties.countryCode)
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.12 }}
      className="absolute z-50 pointer-events-none panel-glass p-2.5 font-mono text-xs shadow-xl"
      style={{ left: hover.x + 16, top: hover.y - 10, maxWidth: 300, background: 'rgba(5, 10, 18, 0.92)' }}
    >
      <div className="flex items-start gap-2">
        <IconImg url={cr360IconUrl(feature.properties.iconPublicId)} className="w-5 h-5 object-contain shrink-0 mt-0.5" />
        <span className="text-text-primary font-bold text-xs leading-tight">{feature.properties.title}</span>
      </div>
      <div className="text-text-secondary mt-1">{meta.name}</div>
      <div className="text-text-secondary mt-0.5">{eventDateLine(feature.properties.date)}</div>
    </motion.div>
  )
}

function RoadTooltip({ hover, roads }: { hover: HoverState; roads: Cr360RoadFeature[] }) {
  const feature = roads.find(f => f.properties.id === hover.id)
  if (!feature) return null
  const sev = SEVERITY_META[feature.properties.severity || ''] || { color: '#94a3b8', label: feature.properties.severity || '—' }
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.12 }}
      className="absolute z-50 pointer-events-none panel-glass p-2.5 font-mono text-xs shadow-xl"
      style={{ left: hover.x + 16, top: hover.y - 10, maxWidth: 300, background: 'rgba(5, 10, 18, 0.92)' }}
    >
      <div className="flex items-center gap-2">
        <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ backgroundColor: sev.color }} />
        <span className="text-text-primary font-bold text-xs leading-tight">
          {feature.properties.roadName || feature.properties.popupTitle || `Carretera ${feature.properties.id}`}
        </span>
      </div>
      <div className="text-text-secondary mt-1">
        Severidad: <span style={{ color: sev.color }}>{sev.label}</span>
      </div>
    </motion.div>
  )
}

function RegionTooltip({ hover, regions }: { hover: HoverState; regions: Cr360RegionFeature[] }) {
  const feature = regions.find(f => f.properties.id === hover.id)
  if (!feature) return null
  const p = feature.properties
  const meta = countryMeta(p.countryCode)
  const owner = OWNER_LABELS[p.ownerType || ''] || p.ownerType || 'Región'
  const title = regionTitle(p)
  const secondary = title === p.conflictName ? owner : (p.conflictName || owner)
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.12 }}
      className="absolute z-50 pointer-events-none panel-glass p-2.5 font-mono text-xs shadow-xl"
      style={{ left: hover.x + 16, top: hover.y - 10, maxWidth: 300, background: 'rgba(5, 10, 18, 0.92)' }}
    >
      <div className="flex items-start gap-2">
        <span className="text-base leading-none mt-0.5">{meta.flag}</span>
        <span className="text-text-primary font-bold text-xs leading-tight">{title}</span>
      </div>
      <div className="text-text-secondary mt-1">{secondary}</div>
    </motion.div>
  )
}

function SeverityBadge({ severity }: { severity: string | null }) {
  const sev = SEVERITY_META[severity || ''] || { color: '#94a3b8', label: severity || '—' }
  return (
    <span
      className="px-1.5 py-0.5 rounded text-[10px] font-bold"
      style={{ backgroundColor: `${sev.color}22`, color: sev.color, border: `1px solid ${sev.color}66` }}
    >
      {sev.label}
    </span>
  )
}

function MediaImage({ publicId, caption }: { publicId: string; caption: string | null }) {
  const url = cr360MediaUrl(publicId)
  const [hidden, setHidden] = useState(false)
  if (!url || hidden) return null
  return (
    <img
      src={url}
      alt={caption || 'Imagen del evento'}
      loading="lazy"
      onError={() => setHidden(true)}
      className="w-full rounded border border-border-glow object-cover max-h-64"
    />
  )
}

function ExternalLinks({ detail }: { detail: Cr360EventDetail }) {
  // Telegram se muestra embebido (previsualización del post), no como chip.
  const links: Array<{ label: string; url: string | null }> = [
    { label: 'X', url: detail.urlX },
    { label: 'YouTube', url: detail.urlYoutube },
    { label: 'TikTok', url: detail.urlTiktok },
    { label: 'Instagram', url: detail.urlInstagram },
    { label: detail.sourceName || 'Fuente', url: detail.source },
  ]
  const present = links.filter(l => l.url)
  if (!present.length) return null
  return (
    <div className="flex flex-wrap gap-1.5">
      {present.map(l => (
        <a
          key={l.label}
          href={l.url!}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-1 px-2 py-1 rounded text-[11px] bg-accent-blue/10 text-accent-blue border border-accent-blue/20 hover:bg-accent-blue hover:text-white transition-colors"
        >
          {l.label}
          <ExternalLink size={10} />
        </a>
      ))}
    </div>
  )
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-3 py-0.5">
      <span className="text-text-secondary shrink-0">{label}</span>
      <span className="text-text-primary text-right">{children}</span>
    </div>
  )
}

function EventModal({ eventId, onClose }: { eventId: number; onClose: () => void }) {
  const { data: detail, isLoading } = useQuery({
    queryKey: ['cr360-event', eventId],
    queryFn: () => fetchCr360Event(eventId),
    enabled: true,
  })

  const meta = detail ? countryMeta(detail.countryCode) : null

  return (
    <LeftPanel onClose={onClose}>
      <div className="flex items-start gap-3">
        {detail && (
          <IconImg url={cr360IconUrl(detail.icon?.publicId ?? null)} className="w-9 h-9 object-contain shrink-0 mt-0.5" />
        )}
        <div className="min-w-0">
          {detail && meta && (
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-lg leading-none">{meta.flag}</span>
              <span className="text-text-secondary text-[11px] uppercase tracking-wider">{meta.name}</span>
            </div>
          )}
          <h2 className="text-text-primary font-bold text-sm leading-tight">
            {detail ? detail.translatedTitle || detail.title : 'Cargando evento…'}
          </h2>
        </div>
      </div>

      {isLoading && !detail && (
        <div className="flex items-center gap-2 text-text-secondary py-6 justify-center">
          <Loader2 size={16} className="animate-spin" />
          <span>Cargando detalle…</span>
        </div>
      )}

      {detail && (
        <div className="space-y-2">
            {detail.translatedDescription || detail.description ? (
              <p className="text-text-primary/90 leading-relaxed border-l-2 border-accent-blue pl-2">
                {detail.translatedDescription || detail.description}
              </p>
            ) : null}

            {detail.urlTelegram && (
              <div className="border-t border-border-glow pt-1.5">
                <div className="text-text-primary uppercase tracking-wider text-[9px] mb-1">Post de Telegram</div>
                <iframe
                  src={telegramEmbedUrl(detail.urlTelegram)}
                  title="Previsualización del post de Telegram"
                  className="w-full h-[380px] rounded border border-border-glow bg-white/5"
                  loading="lazy"
                  referrerPolicy="no-referrer"
                />
              </div>
            )}

            <div className="border-t border-border-glow pt-1.5 space-y-0.5">
              <Row label="Fecha">{detail.date ? eventDateLine(detail.date) : fmtDate(detail.createdAt)}</Row>
              <Row label="Status">
                <span className="text-accent-green">{detail.status || '—'}</span>
              </Row>
              {detail.confidence !== null && <Row label="Confianza">{detail.confidence} / 10</Row>}
              {detail.entityType && <Row label="Tipo">{detail.entityType}</Row>}
              {detail.icon?.name && <Row label="Icono">{detail.icon.name}</Row>}
            </div>

            {(detail.force || detail.criminalGroup) && (
              <div className="border-t border-border-glow pt-1.5 space-y-0.5">
                {detail.force?.name && (
                  <Row label="Fuerza">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: detail.force.color || '#94a3b8' }} />
                      {detail.force.name}
                      {detail.force.type ? ` · ${detail.force.type}` : ''}
                    </span>
                  </Row>
                )}
                {detail.criminalGroup?.name && (
                  <Row label="Grupo">
                    <span className="inline-flex items-center gap-1.5">
                      <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: detail.criminalGroup.color || '#94a3b8' }} />
                      {detail.criminalGroup.name}
                    </span>
                  </Row>
                )}
              </div>
            )}

            {detail.media.some(m => m.type === 'image') && (
              <div className="border-t border-border-glow pt-1.5 space-y-2">
                {detail.media.filter(m => m.type === 'image').map(m => (
                  <MediaImage key={m.id} publicId={m.publicId} caption={m.caption} />
                ))}
              </div>
            )}

            <div className="border-t border-border-glow pt-1.5 space-y-0.5">
              <Row label="Lat">{detail.lat.toFixed(4)}°</Row>
              <Row label="Lon">{detail.lng.toFixed(4)}°</Row>
              {detail.tags.length > 0 && (
                <div className="flex justify-between gap-3 py-0.5">
                  <span className="text-text-secondary shrink-0">Tags</span>
                  <span className="text-text-primary text-right">{detail.tags.join(', ')}</span>
                </div>
              )}
            </div>

            <div className="border-t border-border-glow pt-1.5">
              <ExternalLinks detail={detail} />
            </div>
          </div>
        )}
    </LeftPanel>
  )
}

function RoadModal({ road, onClose }: { road: Cr360RoadFeature; onClose: () => void }) {
  const p = road.properties
  const meta = countryMeta(p.countryCode)
  return (
    <LeftPanel onClose={onClose}>
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-lg leading-none">{meta.flag}</span>
        <span className="text-text-secondary text-[11px] uppercase tracking-wider">{meta.name}</span>
        <SeverityBadge severity={p.severity} />
      </div>
      <h2 className="text-text-primary font-bold text-sm leading-tight mb-3">
        {p.roadName || p.popupTitle || `Carretera ${p.id}`}
      </h2>

      <div className="space-y-0.5">
        {p.threatType && <Row label="Amenaza">{p.threatType}</Row>}
        {p.conflictName && <Row label="Conflicto">{p.conflictName}</Row>}
        {p.criminalGroupName && <Row label="Grupo">{p.criminalGroupName}</Row>}
        {p.regionId != null && <Row label="Región">{p.regionId}</Row>}
        <Row label="Trazado">{road.geometry.coordinates.length} puntos</Row>
        {p.sourceName && <Row label="Fuente">{p.sourceName}</Row>}
      </div>

      {p.popupContent && (
        <p className="mt-2 text-text-primary/90 leading-relaxed border-l-2 border-accent-amber pl-2">{p.popupContent}</p>
      )}
    </LeftPanel>
  )
}

function RegionModal({ region, onClose }: { region: Cr360RegionFeature; onClose: () => void }) {
  const p = region.properties
  const meta = countryMeta(p.countryCode)
  const ownerLabel = OWNER_LABELS[p.ownerType || ''] || p.ownerType || null
  const title = regionTitle(p)
  const area = regionAreaKm2(region)
  return (
    <LeftPanel onClose={onClose}>
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-lg leading-none">{meta.flag}</span>
        <span className="text-text-secondary text-[11px] uppercase tracking-wider">{meta.name}</span>
        {ownerLabel && (
          <span className="px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider" style={{ backgroundColor: '#38bdf822', color: '#38bdf8', border: '1px solid #38bdf866' }}>
            {ownerLabel}
          </span>
        )}
      </div>
      <h2 className="text-text-primary font-bold text-sm leading-tight mb-3">
        {title}
      </h2>

      <div className="space-y-0.5">
        {p.conflictName && p.conflictName !== title && <Row label="Conflicto">{p.conflictName}</Row>}
        {p.criminalGroupName && p.criminalGroupName !== title && <Row label="Grupo">{p.criminalGroupName}</Row>}
        {p.forceName && p.forceName !== title && (
          <Row label="Fuerza">
            <span className="inline-flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-full inline-block" style={{ backgroundColor: p.forceColor || '#94a3b8' }} />
              {p.forceName}
              {p.forceAcronym ? ` · ${p.forceAcronym}` : ''}
            </span>
          </Row>
        )}
        {p.parentGroupName && <Row label="Grupo padre">{p.parentGroupName}</Row>}
        <Row label="Fecha">{p.regionDate ? fmtDate(p.regionDate) : '—'}</Row>
        {area !== null && <Row label="Área">{fmtArea(area)}</Row>}
      </div>

      {p.popupContent && (
        <p className="mt-2 text-text-primary/90 leading-relaxed border-l-2 border-accent-blue pl-2">{p.popupContent}</p>
      )}
    </LeftPanel>
  )
}

const ROAD_COLOR_NAMES: Record<string, string> = {
  '#ff0000': 'roja',
  '#fe0101': 'roja',
  '#fb0000': 'roja',
  '#f1c40f': 'amarilla',
  '#fae500': 'amarilla',
  '#fff700': 'amarilla',
  '#2196f3': 'azul',
  '#4caf50': 'verde',
  '#ff6f00': 'naranja',
  '#ee00ff': 'magenta',
  '#000000': 'negro',
}

function Legend({ events, roads }: { events: Cr360EventFeature[]; roads: Cr360RoadFeature[] }) {
  const [open, setOpen] = useState(true)
  const roadColors = useMemo(() => {
    // Agrupa por color canónico (los tonos de rojo/amarillo se unifican).
    const counts: Record<string, { label: string; color: string; count: number }> = {}
    for (const f of roads) {
      const hex = (f.properties.strokeColor || '#ef4444').toLowerCase()
      const label = ROAD_COLOR_NAMES[hex] || hex
      const entry = counts[label] || { label, color: hex, count: 0 }
      entry.count += 1
      counts[label] = entry
    }
    return Object.values(counts).sort((a, b) => b.count - a.count).slice(0, 5)
  }, [roads])
  const topIcons = useMemo(() => {
    const counts: Record<string, { pid: string; name: string; count: number }> = {}
    for (const f of events) {
      const pid = f.properties.iconPublicId
      if (!pid) continue
      counts[pid] = counts[pid] || { pid, name: f.properties.iconName || 'Evento', count: 0 }
      counts[pid].count += 1
    }
    return Object.values(counts).sort((a, b) => b.count - a.count).slice(0, 6)
  }, [events])

  return (
    <div className="absolute bottom-4 right-4 z-40 w-60 max-h-[70vh] overflow-y-auto panel-glass p-3 font-mono text-[10px] shadow-xl">
      <div className="flex items-center justify-between mb-2">
        <span className="text-accent-blue font-bold text-xs uppercase tracking-wider">Leyenda</span>
        <button onClick={() => setOpen(!open)} className="text-text-secondary hover:text-white transition-colors">
          <ChevronDown size={14} className={`transition-transform ${open ? 'rotate-180' : ''}`} />
        </button>
      </div>
      {open && (
        <div className="space-y-2.5 text-text-secondary">
          <div>
            <div className="text-text-primary uppercase tracking-wider text-[9px] mb-1">Frontera</div>
            <div className="flex items-center gap-2">
              <span className="h-0.5 w-6 shrink-0 bg-[#22d3ee] shadow-[0_0_4px_#22d3ee]" />
              Frontera nacional (Ucrania)
            </div>
          </div>
          <div>
            <div className="text-text-primary uppercase tracking-wider text-[9px] mb-1">Carreteras</div>
            {roadColors.length > 0 ? roadColors.map(rc => (
              <div key={rc.label} className="flex items-center gap-2">
                <span className="h-0.5 w-6 shrink-0" style={{ backgroundColor: rc.color }} />
                {rc.label} · {rc.count}
              </div>
            )) : (
              <div className="flex items-center gap-2">
                <span className="h-0.5 w-6 shrink-0 bg-[#ef4444]" />
                Carretera comprometida
              </div>
            )}
          </div>
          <div>
            <div className="text-text-primary uppercase tracking-wider text-[9px] mb-1">Regiones</div>
            <div className="flex items-center gap-2">
              <span className="w-3.5 h-3.5 shrink-0 rounded-sm border-2 border-[#38bdf8] bg-[#38bdf8]/30" />
              Región (control / conflicto)
            </div>
          </div>
          <div>
            <div className="text-text-primary uppercase tracking-wider text-[9px] mb-1">Eventos</div>
            <div className="flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 shrink-0 rounded-full border border-white bg-[#c60b1e]" />
              <span className="w-2.5 h-2.5 shrink-0 rounded-full border border-white bg-[#3b82f6]" />
              <span className="w-2.5 h-2.5 shrink-0 rounded-full border border-white bg-[#eab308]" />
              <span>Punto por país (ESP · RUS · UKR)</span>
            </div>
            {topIcons.length > 0 && (
              <div className="mt-1.5 space-y-0.5 border-t border-border-glow pt-1.5">
                <div className="text-text-primary uppercase tracking-wider text-[9px] mb-1">Tipos más frecuentes</div>
                {topIcons.map(ic => (
                  <div key={ic.pid} className="flex items-center gap-1.5">
                    <IconImg url={cr360IconUrl(ic.pid)} className="w-4 h-4 object-contain shrink-0" />
                    <span className="truncate">{ic.name}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export function Radar() {
  const mapRef = useRef<MapRef | null>(null)
  const queryClient = useQueryClient()
  const [hover, setHover] = useState<HoverState | null>(null)
  const [selectedEventId, setSelectedEventId] = useState<number | null>(null)
  const [selectedRoad, setSelectedRoad] = useState<Cr360RoadFeature | null>(null)
  const [selectedRegion, setSelectedRegion] = useState<Cr360RegionFeature | null>(null)
  const [mapReady, setMapReady] = useState(false)
  const [loadedIcons, setLoadedIcons] = useState<Set<string>>(new Set())

  const { data, isFetching: eventsFetching, isLoading: eventsLoading } = useQuery({
    queryKey: ['cr360-events'],
    queryFn: fetchCr360Events,
    refetchInterval: RADAR_POLL_MS,
    refetchOnWindowFocus: true,
  })

  const { data: roads, isFetching: roadsFetching, isLoading: roadsLoading } = useQuery({
    queryKey: ['cr360-roads'],
    queryFn: fetchCr360Roads,
    refetchInterval: RADAR_POLL_MS,
    refetchOnWindowFocus: true,
  })

  const { data: regions, isFetching: regionsFetching, isLoading: regionsLoading } = useQuery({
    queryKey: ['cr360-regions'],
    queryFn: fetchCr360Regions,
    refetchInterval: RADAR_POLL_MS,
    refetchOnWindowFocus: true,
  })

  const events = useMemo(() => data?.features ?? [], [data])

  const handleMapLoad = useCallback(() => setMapReady(true), [])

  useEffect(() => {
    const map = mapRef.current?.getMap()
    if (!map || !mapReady) return
    const pids = Array.from(
      new Set(events.map(f => f.properties.iconPublicId).filter((p): p is string => !!p)),
    )
    let cancelled = false
    for (const pid of pids) {
      if (loadedIcons.has(pid) || map.hasImage(iconImageId(pid))) continue
      const url = cr360IconUrl(pid)
      if (!url) continue
      map.loadImage(url, (err, image) => {
        if (cancelled || err || !image) return
        const id = iconImageId(pid)
        if (!map.hasImage(id)) {
          try {
            map.addImage(id, image)
          } catch {
            return
          }
        }
        setLoadedIcons(prev => {
          const next = new Set(prev)
          next.add(pid)
          return next
        })
      })
    }
    return () => {
      cancelled = true
    }
  }, [mapReady, events, loadedIcons])

  const iconFeatures = useMemo(
    () => events.filter(f => !!f.properties.iconPublicId && loadedIcons.has(f.properties.iconPublicId)),
    [events, loadedIcons],
  )

  const iconSourceGeojson = useMemo<GeoJSON.FeatureCollection>(() => ({
    type: 'FeatureCollection',
    features: iconFeatures.map(f => ({
      type: 'Feature' as const,
      id: f.id,
      properties: {
        id: f.properties.id,
        alert: f.properties.alertHours != null,
        icon: iconImageId(f.properties.iconPublicId!),
        color: countryMeta(f.properties.countryCode).color,
        age: eventAgeDays(f.properties.date) ?? 99,
        size: ageFactor(eventAgeDays(f.properties.date) ?? 99),
        alpha: ageAlpha(eventAgeDays(f.properties.date) ?? 99),
      },
      geometry: f.geometry,
    })),
  }), [iconFeatures])

  const eventsGeojson = useMemo<GeoJSON.FeatureCollection>(() => ({
    type: 'FeatureCollection',
    features: events.map(f => ({
      type: 'Feature' as const,
      id: f.id,
      properties: {
        id: f.properties.id,
        title: f.properties.title,
        color: countryMeta(f.properties.countryCode).color,
        alert: f.properties.alertHours != null,
        // Énfasis temporal: tamaño/opacidad según la antigüedad del evento.
        age: eventAgeDays(f.properties.date) ?? 99,
        size: ageFactor(eventAgeDays(f.properties.date) ?? 99),
        alpha: ageAlpha(eventAgeDays(f.properties.date) ?? 99),
        // Con icono cargado el punto queda oculto bajo el icono; solo se pinta
        // el punto para eventos sin icono (fallback).
        hasIcon: !!f.properties.iconPublicId && loadedIcons.has(f.properties.iconPublicId),
      },
      geometry: f.geometry,
    })),
  }), [events, loadedIcons])

  const roadsGeojson = useMemo<GeoJSON.FeatureCollection>(() => ({
    type: 'FeatureCollection',
    features: (roads?.features ?? []).map(f => {
      const props: Record<string, unknown> = {
        id: f.properties.id,
        name: f.properties.roadName || f.properties.popupTitle || '',
        color: f.properties.strokeColor || SEVERITY_META[f.properties.severity || '']?.color || '#ef4444',
        width: f.properties.strokeWidth || 3,
        severity: f.properties.severity,
      }
      if (Array.isArray(f.properties.dashPattern)) {
        props.dash = f.properties.dashPattern
      }
      return {
        type: 'Feature' as const,
        id: f.id,
        properties: props,
        geometry: f.geometry,
      }
    }),
  }), [roads])

  const regionsGeojson = useMemo<GeoJSON.FeatureCollection>(() => ({
    type: 'FeatureCollection',
    features: (regions?.features ?? []).map(f => {
      const props: Record<string, unknown> = {
        id: f.properties.id,
        name: f.properties.popupTitle || '',
        fillColor: f.properties.fillColor || '#38bdf8',
        fillOpacity: f.properties.fillOpacity ?? 0.3,
        strokeColor: f.properties.strokeColor || '#38bdf8',
        strokeWidth: f.properties.strokeWidth || 2,
      }
      if (Array.isArray(f.properties.dashPattern)) {
        props.dash = f.properties.dashPattern
      }
      return {
        type: 'Feature' as const,
        id: f.id,
        properties: props,
        geometry: f.geometry,
      }
    }),
  }), [regions])

  const handleMouseMove = useCallback((e: any) => {
    const map = mapRef.current?.getMap()
    if (!map) return
    const features = map.queryRenderedFeatures(e.point, {
      layers: ['radar-events-icon', 'radar-events-point', 'radar-roads-hit', 'radar-regions-fill', 'radar-regions-line'],
    })
    if (features.length > 0) {
      const f = features[0]
      const layerId = f.layer?.id
      const kind: HoverState['kind'] =
        layerId === 'radar-events-icon' || layerId === 'radar-events-point'
          ? 'event'
          : layerId === 'radar-roads-hit' ? 'road' : 'region'
      setHover({ x: e.point.x, y: e.point.y, kind, id: f.properties?.id as number })
    } else {
      setHover(null)
    }
  }, [])

  const handleMouseLeave = useCallback(() => setHover(null), [])

  const handleMapClick = useCallback((e: any) => {
    for (const feature of e.features || []) {
      const layerId = feature.layer?.id
      const id = feature.properties?.id
      if ((layerId === 'radar-events-point' || layerId === 'radar-events-icon') && typeof id === 'number') {
        setSelectedEventId(id)
        setSelectedRoad(null)
        setSelectedRegion(null)
        return
      }
      if (layerId === 'radar-roads-hit' && typeof id === 'number') {
        const road = (roads?.features ?? []).find(r => r.properties.id === id)
        if (road) {
          setSelectedRoad(road)
          setSelectedEventId(null)
          setSelectedRegion(null)
          return
        }
      }
      if ((layerId === 'radar-regions-fill' || layerId === 'radar-regions-line') && typeof id === 'number') {
        const region = (regions?.features ?? []).find(r => r.properties.id === id)
        if (region) {
          setSelectedRegion(region)
          setSelectedEventId(null)
          setSelectedRoad(null)
          return
        }
      }
    }
    setSelectedEventId(null)
    setSelectedRoad(null)
    setSelectedRegion(null)
  }, [roads, regions])

  const refresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['cr360'] })
  }, [queryClient])

  const isLoading = eventsLoading || roadsLoading || regionsLoading
  const isFetching = eventsFetching || roadsFetching || regionsFetching
  const totalEvents = events.length
  const totalRoads = roads?.features.length ?? 0
  const totalRegions = regions?.features.length ?? 0

  return (
    <div className="flex flex-col h-screen bg-bg-base text-text-primary">
      <div className="flex items-center justify-between px-3 py-2 bg-bg-panel border-b border-border-glow">
        <div className="flex items-center gap-2 min-w-0">
          <Link to="/" className="p-1 rounded hover:bg-bg-glass text-text-secondary hover:text-white transition-colors" title="Volver al dashboard">
            <ArrowLeft size={18} />
          </Link>
          <Activity className="text-accent-blue shrink-0" size={20} />
          <span className="font-mono text-sm sm:text-lg font-bold tracking-wider truncate">{RADAR_TITLE}</span>
        </div>
        <div className="flex items-center gap-3">
          {isFetching && (
            <div className="flex items-center gap-1 text-xs text-text-secondary">
              <div className="animate-spin h-3 w-3 border border-accent-blue border-t-transparent rounded-full" />
              <span className="font-mono hidden sm:inline">ACTUALIZANDO…</span>
            </div>
          )}
          <button
            onClick={refresh}
            className="flex items-center gap-1.5 px-2.5 py-1.5 bg-accent-blue/10 text-accent-blue border border-accent-blue/20 rounded-lg hover:bg-accent-blue hover:text-white transition-all duration-300 text-xs font-medium"
            title="Actualizar ahora"
          >
            <RefreshCw size={14} />
            <span className="hidden sm:inline">Actualizar</span>
          </button>
        </div>
      </div>

      <div className="flex-1 relative">
        <Map
          ref={mapRef}
          initialViewState={DEFAULT_VIEWPORT}
          onLoad={handleMapLoad}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          onClick={handleMapClick}
          interactiveLayerIds={['radar-events-icon', 'radar-events-point', 'radar-roads-hit', 'radar-regions-fill', 'radar-regions-line']}
          style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%' } as any}
          mapStyle={MAP_STYLE}
          mapboxAccessToken={MAPBOX_TOKEN}
          reuseMaps
        >
          {totalRegions > 0 && (
            <Source id="radar-regions-src" type="geojson" data={regionsGeojson}>
              <Layer
                id="radar-regions-fill"
                type="fill"
                source="radar-regions-src"
                paint={{
                  'fill-color': ['get', 'fillColor'],
                  'fill-opacity': ['get', 'fillOpacity'],
                }}
              />
              <Layer
                id="radar-regions-line"
                type="line"
                source="radar-regions-src"
                paint={{
                  'line-color': ['get', 'strokeColor'],
                  'line-width': ['get', 'strokeWidth'],
                  'line-opacity': 0.9,
                  'line-dasharray': ['case', ['has', 'dash'], ['get', 'dash'], [1, 0]],
                }}
              />
            </Source>
          )}

          <Source id="radar-ukraine-border-src" type="geojson" data="/geojson/ukraine-border.geojson">
            <Layer
              id="radar-ukraine-border-halo"
              type="line"
              source="radar-ukraine-border-src"
              paint={{
                'line-color': '#000000',
                'line-width': 6,
                'line-opacity': 0.75,
              }}
            />
            <Layer
              id="radar-ukraine-border"
              type="line"
              source="radar-ukraine-border-src"
              paint={{
                'line-color': '#22d3ee',
                'line-width': 2.5,
                'line-opacity': 1,
              }}
            />
          </Source>

          {events.length > 0 && (
            <Source id="radar-events-src" type="geojson" data={eventsGeojson}>
              <Layer
                id="radar-events-point"
                type="circle"
                source="radar-events-src"
                filter={['!', ['get', 'hasIcon']]}
                paint={{
                  'circle-radius': ['*', ['case', ['get', 'alert'], 9, 7], ['get', 'size']],
                  'circle-color': ['get', 'color'],
                  'circle-opacity': ['*', 0.9, ['get', 'alpha']],
                  'circle-stroke-width': 1.5,
                  'circle-stroke-color': '#ffffff',
                  'circle-stroke-opacity': ['*', 0.9, ['get', 'alpha']],
                }}
              />
            </Source>
          )}

          {iconFeatures.length > 0 && (
            <Source id="radar-events-icon-src" type="geojson" data={iconSourceGeojson}>
              <Layer
                id="radar-events-icon"
                type="symbol"
                source="radar-events-icon-src"
                layout={{
                  'icon-image': ['get', 'icon'],
                  'icon-size': ['*', ['case', ['get', 'alert'], 0.55, 0.42], ['get', 'size']],
                  'icon-allow-overlap': true,
                  'icon-ignore-placement': true,
                  // Los eventos de hoy quedan por encima de los anteriores (sort key mayor).
                  'symbol-sort-key': ['-', 0, ['get', 'age']],
                }}
                paint={{
                  'icon-opacity': ['get', 'alpha'],
                }}
              />
              {/* Anillo de color del país alrededor del icono (distintivo de país) */}
              <Layer
                id="radar-events-ring-halo"
                type="circle"
                source="radar-events-icon-src"
                paint={{
                  'circle-radius': ['*', ['case', ['get', 'alert'], 28.5, 22.5], ['get', 'size']],
                  'circle-color': 'transparent',
                  'circle-stroke-width': 1.5,
                  'circle-stroke-color': '#000000',
                  'circle-stroke-opacity': ['*', 0.8, ['get', 'alpha']],
                }}
              />
              <Layer
                id="radar-events-ring"
                type="circle"
                source="radar-events-icon-src"
                paint={{
                  'circle-radius': ['*', ['case', ['get', 'alert'], 27, 21], ['get', 'size']],
                  'circle-color': 'transparent',
                  'circle-stroke-width': 2.5,
                  'circle-stroke-color': ['get', 'color'],
                  'circle-stroke-opacity': ['*', 0.95, ['get', 'alpha']],
                }}
              />
            </Source>
          )}

          {totalRoads > 0 && (
            <Source id="radar-roads-src" type="geojson" data={roadsGeojson}>
              <Layer
                id="radar-roads-glow"
                type="line"
                source="radar-roads-src"
                paint={{
                  'line-color': ['get', 'color'],
                  'line-width': ['+', ['get', 'width'], 6],
                  'line-opacity': 0.2,
                  'line-blur': 3,
                }}
              />
              <Layer
                id="radar-roads-line"
                type="line"
                source="radar-roads-src"
                paint={{
                  'line-color': ['get', 'color'],
                  'line-width': ['get', 'width'],
                  'line-opacity': 0.95,
                  'line-dasharray': ['case', ['has', 'dash'], ['get', 'dash'], [1, 0]],
                }}
              />
              <Layer
                id="radar-roads-hit"
                type="line"
                source="radar-roads-src"
                paint={{
                  'line-color': '#000000',
                  'line-width': 14,
                  'line-opacity': 0,
                }}
              />
            </Source>
          )}

          <NavigationControl position="top-right" />
        </Map>

        {/* Halo rojo táctico alrededor del mapamundi */}
        <div
          className="absolute inset-0 z-10 pointer-events-none"
          style={{
            border: '1.5px solid rgba(239, 68, 68, 0.45)',
            boxShadow: '0 0 18px rgba(239, 68, 68, 0.35), inset 0 0 28px rgba(239, 68, 68, 0.12)',
          }}
        />

        {isLoading && (
          <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-accent-blue text-bg-base text-sm font-mono px-4 py-2 rounded shadow-lg animate-pulse z-50">
            Cargando datos…
          </div>
        )}

        {!isLoading && totalEvents === 0 && totalRoads === 0 && totalRegions === 0 && (
          <div className="absolute top-2 left-1/2 -translate-x-1/2 bg-bg-panel border border-border-glow text-text-secondary text-sm font-mono px-4 py-2 rounded shadow-lg z-50">
            Sin datos para {CR360_COUNTRIES}
          </div>
        )}

        <div className="absolute bottom-4 left-4 font-mono text-[10px] sm:text-xs text-text-secondary bg-bg-glass px-2 py-1 rounded z-40">
          {totalEvents} EVENTOS · {totalRoads} CARRETERAS · {totalRegions} REGIONES
        </div>

        <Legend events={events} roads={roads?.features ?? []} />

        <AnimatePresence>
          {hover && hover.kind === 'event' && (
            <EventTooltip key={`ev-${hover.id}`} hover={hover} events={events} />
          )}
          {hover && hover.kind === 'road' && (
            <RoadTooltip key={`rd-${hover.id}`} hover={hover} roads={roads?.features ?? []} />
          )}
          {hover && hover.kind === 'region' && (
            <RegionTooltip key={`rg-${hover.id}`} hover={hover} regions={regions?.features ?? []} />
          )}
          {selectedEventId !== null && (
            <EventModal key={`modal-ev-${selectedEventId}`} eventId={selectedEventId} onClose={() => setSelectedEventId(null)} />
          )}
          {selectedRoad !== null && (
            <RoadModal key={`modal-rd-${selectedRoad.properties.id}`} road={selectedRoad} onClose={() => setSelectedRoad(null)} />
          )}
          {selectedRegion !== null && (
            <RegionModal key={`modal-rg-${selectedRegion.properties.id}`} region={selectedRegion} onClose={() => setSelectedRegion(null)} />
          )}
        </AnimatePresence>
      </div>
    </div>
  )
}
