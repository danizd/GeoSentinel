import type { Cr360EventCollection, Cr360EventDetail, Cr360RegionCollection, Cr360RoadCollection } from '../types/cr360'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

/** Países de interés (ISO-3 separados por coma). Configurable en `.env`. */
export const CR360_COUNTRIES: string = (import.meta.env.VITE_CR360_COUNTRIES || 'ESP,RUS,UKR').toUpperCase()

/** Título del enlace y de la página del radar. Configurable en `.env`. */
export const RADAR_TITLE: string = import.meta.env.VITE_RADAR_TITLE || 'Conflicto Ucrania - Rusia'

/** Intervalo de polling de la página /radar (ms). Default: 3 horas. */
export const RADAR_POLL_MS: number = Number(import.meta.env.VITE_POLL_CR360_MS) || 3 * 60 * 60 * 1000

/** URL de una media de CR360 (patrón Cloudinary verificado). */
export function cr360MediaUrl(publicId: string | null): string | null {
  if (!publicId) return null
  return `https://res.cloudinary.com/dmmlghevj/image/upload/f_auto,q_auto/${publicId}`
}

/** URL de un icono de evento de CR360 redimensionado a 64 px (los originales son 1024×1024). */
export function cr360IconUrl(publicId: string | null): string | null {
  if (!publicId) return null
  return `https://res.cloudinary.com/dmmlghevj/image/upload/f_auto,q_auto,w_64,h_64,c_fit/${publicId}`
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url)
  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}: ${response.statusText}`)
  }
  return response.json() as Promise<T>
}

export function fetchCr360Events(): Promise<Cr360EventCollection> {
  return getJson(`${API_BASE_URL}/v1/cr360/events?countries=${CR360_COUNTRIES}`)
}

export function fetchCr360Event(eventId: number): Promise<Cr360EventDetail> {
  return getJson(`${API_BASE_URL}/v1/cr360/events/${eventId}`)
}

export function fetchCr360Roads(): Promise<Cr360RoadCollection> {
  return getJson(`${API_BASE_URL}/v1/cr360/roads?countries=${CR360_COUNTRIES}`)
}

export function fetchCr360Regions(): Promise<Cr360RegionCollection> {
  return getJson(`${API_BASE_URL}/v1/cr360/regions?countries=${CR360_COUNTRIES}`)
}
