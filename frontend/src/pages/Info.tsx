import { Link } from 'react-router-dom'
import { Activity, Globe, Map, Eye, Zap } from 'lucide-react'

export function Info() {
  return (
    <div className="min-h-screen bg-bg-base text-text-primary font-sans">
      <div className="max-w-3xl mx-auto px-6 py-12">
        <div className="flex items-center gap-3 mb-10">
          <Activity className="text-accent-blue" size={28} />
          <h1 className="text-3xl font-bold tracking-tight">GeoSentinel</h1>
        </div>

        <p className="text-lg text-text-secondary mb-10 leading-relaxed">
          Una herramienta para seguir en tiempo real lo que está pasando en el mundo: conflictos,
          desastres naturales, incendios, actividad militar aérea y naval. Todo sobre un mapa interactivo 3D.
        </p>

        <Section icon={<Eye size={20} />} title="¿Qué se ve en el mapa?">
          <Item color="#ef4444" label="Círculos rojos" desc="Conflictos activos (guerras, batallas, protestas violentas)." />
          <Item color="#fbbf24" label="Círculos amarillos" desc="Desastres naturales (terremotos, tsunamis, erupciones)." />
          <Item color="#f97316" label="Círculos naranjas" desc="Incendios activos detectados por satélites de la NASA." />
          <Item color="#38bdf8" label="Zonas azules" desc="Áreas de interés: regiones que se están monitorizando." />
          <Item color="#3B82F6" label="Aviones ✈" desc="Vuelos militares en tiempo real. Cada avión apunta en la dirección de vuelo." />
          <Item color="#94A3B8" label="Barcos ⛵" desc="Buques de guerra y navales. Los que parpadean más tenues pueden estar ocultando su posición." />
        </Section>

        <Section icon={<Globe size={20} />} title="¿De dónde salen los datos?">
          <Source name="USGS" desc="Terremotos detectados por el servicio geológico de Estados Unidos." />
          <Source name="NASA FIRMS" desc="Incendios activos detectados por los satélites VIIRS y MODIS." />
          <Source name="GDELT Project" desc="Noticias y eventos de conflicto recopilados de medios de todo el mundo." />
          <Source name="ACLED" desc="Base de datos de conflictos verificada por investigadores sobre el terreno." />
          <Source name="OpenSky Network" desc="Red de voluntarios que rastrean vuelos mediante señales de radio ADS-B." />
          <Source name="AISStream" desc="Señales AIS emitidas por barcos. Obligatorias para buques comerciales." />
        </Section>

        <Section icon={<Zap size={20} />} title="¿Cómo funciona?">
          <p className="text-text-secondary leading-relaxed mb-3">
            GeoSentinel consulta varias fuentes públicas cada pocos minutos.
            Los datos en crudo se filtran para eliminar duplicados y errores, se clasifican por tipo y severidad,
            y se muestran sobre el mapa.
          </p>
          <p className="text-text-secondary leading-relaxed mb-3">
            Los vuelos militares se identifican por su código de identificación o por patrones en su señal de radio.
            Los barcos se rastrean por el sistema AIS, obligatorio para la navegación.
          </p>
          <p className="text-text-secondary leading-relaxed">
            El mapa usa tecnología de Mapbox y puede verse en modo 2D (callejero) o 3D (globo terráqueo).
            Los datos se actualizan automáticamente cada 30 segundos.
          </p>
        </Section>

        <Section icon={<Map size={20} />} title="Controles del mapa">
          <div className="space-y-2 text-text-secondary">
            <p><strong className="text-text-primary">PUNTOS</strong> — Muestra los incidentes como círculos de colores.</p>
            <p><strong className="text-text-primary">CALOR</strong> — Vista de calor: las zonas con más incidentes se ven más brillantes.</p>
            <p><strong className="text-text-primary">ZONAS</strong> — Muestra las regiones que se están monitorizando.</p>
            <p><strong className="text-text-primary">VUELOS</strong> — Activa la capa de aviones militares en el cielo.</p>
            <p><strong className="text-text-primary">BUQUES</strong> — Activa la capa de barcos en el mar.</p>
            <p><strong className="text-text-primary">2D / 3D</strong> — Cambia entre mapa plano y globo terráqueo.</p>
            <p><strong className="text-text-primary">Click en un avión o barco</strong> — Muestra todos sus datos.</p>
            <p><strong className="text-text-primary">Click en un incidente</strong> — Lo selecciona y centra el mapa.</p>
          </div>
        </Section>

        <div className="mt-12 pt-6 border-t border-border-glow text-center">
          <Link to="/" className="text-accent-blue hover:text-accent-blue/80 font-medium">
            ← Volver al mapa
          </Link>
        </div>
      </div>
    </div>
  )
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <div className="mb-8">
      <div className="flex items-center gap-2 mb-4">
        <span className="text-accent-blue">{icon}</span>
        <h2 className="text-xl font-semibold">{title}</h2>
      </div>
      {children}
    </div>
  )
}

function Item({ color, label, desc }: { color: string; label: string; desc: string }) {
  return (
    <div className="flex items-start gap-3 mb-2">
      <span className="w-4 h-4 rounded-full mt-0.5 shrink-0" style={{ backgroundColor: color }} />
      <div>
        <span className="text-text-primary font-medium">{label}</span>
        <span className="text-text-secondary ml-2 text-sm">{desc}</span>
      </div>
    </div>
  )
}

function Source({ name, desc }: { name: string; desc: string }) {
  return (
    <div className="mb-2">
      <span className="text-accent-blue font-medium">{name}</span>
      <span className="text-text-secondary ml-2 text-sm">— {desc}</span>
    </div>
  )
}
