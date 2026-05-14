import { create } from 'zustand'
import type { Incident, IncidentFilters } from '../types/incident'

interface MapState {
  selectedIncident: Incident | null
  setSelectedIncident: (incident: Incident | null) => void
  viewport: {
    longitude: number
    latitude: number
    zoom: number
    pitch: number
    bearing: number
  }
  setViewport: (viewport: Partial<MapState['viewport']>) => void
  layers: {
    scatter: boolean
    heat: boolean
    aoi: boolean
    tracks: boolean
    vessels: boolean
    bases: boolean
  }
  toggleLayer: (layer: keyof MapState['layers']) => void
}

const INITIAL_VIEWPORT = {
  longitude: 20,
  latitude: 20,
  zoom: 2.5,
  pitch: 0,
  bearing: 0,
}

export const useMapStore = create<MapState>((set) => ({
  selectedIncident: null,
  setSelectedIncident: (incident) => set({ selectedIncident: incident }),
  viewport: INITIAL_VIEWPORT,
  setViewport: (viewport) =>
    set((state) => ({ viewport: { ...state.viewport, ...viewport } })),
  layers: {
    scatter: true,
    heat: false,
    aoi: true,
    tracks: false,
    vessels: false,
    bases: false,
  },
  toggleLayer: (layer) =>
    set((state) => ({
      layers: { ...state.layers, [layer]: !state.layers[layer] },
    })),
}))

interface FilterState {
  filters: IncidentFilters
  setFilters: (filters: Partial<IncidentFilters>) => void
  resetFilters: () => void
}

const DEFAULT_FILTERS: IncidentFilters = {
  status: 'open,updated',
  page: 1,
  limit: 20,
}

export const useFilterStore = create<FilterState>((set) => ({
  filters: DEFAULT_FILTERS,
  setFilters: (filters) =>
    set((state) => ({ filters: { ...state.filters, ...filters } })),
  resetFilters: () => set({ filters: DEFAULT_FILTERS }),
}))