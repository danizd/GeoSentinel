// Tipos para la API pública de CR360 (Conflict Radar 360), servida vía proxy /v1/cr360.

export interface Cr360EventProperties {
  id: number
  title: string
  date: string
  createdAt: string
  entityType: string | null
  alertHours: number | null
  alertExpiresAt: string | null
  iconId: string | null
  iconName: string | null
  iconPublicId: string | null
  iconCategory: string | null
  forceName: string | null
  forceColor: string | null
  forceLogoUrl: string | null
  forceAcronym: string | null
  forceType: string | null
  criminalGroupName: string | null
  criminalGroupColor: string | null
  countryCode: string
  criminalGroupAcronym: string | null
  flagImage: string | null
  description: string | null
}

export interface Cr360EventFeature {
  type: 'Feature'
  id: number
  geometry: { type: 'Point'; coordinates: [number, number] }
  properties: Cr360EventProperties
}

export interface Cr360EventCollection {
  type: 'FeatureCollection'
  features: Cr360EventFeature[]
}

export interface Cr360Media {
  id: number
  eventId: number
  publicId: string
  type: string
  caption: string | null
  sortOrder: number
}

export interface Cr360Force {
  id: number
  type: string | null
  name: string | null
  countryCode: string | null
  acronym: string | null
  color: string | null
  logoUrl: string | null
}

export interface Cr360CriminalGroup {
  id: number
  name: string | null
  countryCode: string | null
  acronym: string | null
  color: string | null
}

export interface Cr360EventDetail {
  id: number
  entityType: string | null
  countryCode: string
  lat: number
  lng: number
  title: string
  description: string | null
  source: string | null
  sourceName: string | null
  urlYoutube: string | null
  urlTelegram: string | null
  urlTiktok: string | null
  urlX: string | null
  urlInstagram: string | null
  date: string | null
  time: string | null
  alertHours: number | null
  alertExpiresAt: string | null
  status: string | null
  confidence: number | null
  aiGenerated: boolean
  createdAt: string | null
  updatedAt: string | null
  force: Cr360Force | null
  criminalGroup: Cr360CriminalGroup | null
  icon: { id: number; name: string | null; category: string | null; publicId: string | null } | null
  media: Cr360Media[]
  tags: string[]
  translatedTitle: string | null
  translatedDescription: string | null
}

export interface Cr360RoadProperties {
  id: number
  regionId: number | null
  geometryType: string | null
  fillColor: string | null
  strokeColor: string | null
  fillOpacity: number | null
  strokeOpacity: number | null
  strokeWidth: number | null
  dashPattern: number[] | null
  popupTitle: string | null
  popupContent: string | null
  roadName: string | null
  threatType: string | null
  severity: string | null
  blinkSpeed: string | null
  countryCode: string
  source: string | null
  sourceName: string | null
  conflictId: number | null
  criminalGroupId: number | null
  conflictName: string | null
  criminalGroupName: string | null
}

export interface Cr360RoadFeature {
  type: 'Feature'
  id: number
  geometry: { type: 'LineString'; coordinates: [number, number][] }
  properties: Cr360RoadProperties
}

export interface Cr360RoadCollection {
  type: 'FeatureCollection'
  features: Cr360RoadFeature[]
}

export interface Cr360RegionProperties {
  id: number
  regionId: number | null
  geometryType: string | null
  fillColor: string | null
  strokeColor: string | null
  fillOpacity: number | null
  strokeOpacity: number | null
  strokeWidth: number | null
  dashPattern: number[] | null
  pattern: string | null
  popupTitle: string | null
  popupContent: string | null
  regionDate: string | null
  countryCode: string
  conflictId: number | null
  conflictName: string | null
  criminalGroupId: number | null
  criminalGroupName: string | null
  forceId: number | null
  forceName: string | null
  forceAcronym: string | null
  forceColor: string | null
  forceLogoUrl: string | null
  parentGroupId: number | null
  parentGroupName: string | null
  ownerType: string | null
}

export interface Cr360RegionFeature {
  type: 'Feature'
  id: number
  geometry: GeoJSON.Polygon | GeoJSON.MultiPolygon
  properties: Cr360RegionProperties
}

export interface Cr360RegionCollection {
  type: 'FeatureCollection'
  features: Cr360RegionFeature[]
}
