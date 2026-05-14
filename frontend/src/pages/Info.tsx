import { Link } from 'react-router-dom'
import { Activity, Globe, Map, Eye, Zap, Clock, Thermometer, Flag, Shield } from 'lucide-react'

const NATO_COUNTRIES = [
  'Albania', 'Belgium', 'Bulgaria', 'Canada', 'Croatia', 'Czech Republic',
  'Denmark', 'Estonia', 'Finland', 'France', 'Germany', 'Greece', 'Hungary',
  'Iceland', 'Italy', 'Latvia', 'Lithuania', 'Luxembourg', 'Montenegro',
  'Netherlands', 'North Macedonia', 'Norway', 'Poland', 'Portugal', 'Romania',
  'Slovakia', 'Slovenia', 'Spain', 'Sweden', 'Turkey', 'United Kingdom', 'United States',
]

export function Info() {
  return (
    <div className="min-h-screen bg-bg-base text-text-primary font-sans">
      <div className="max-w-3xl mx-auto px-6 py-12">
        <div className="flex items-center gap-3 mb-10">
          <Activity className="text-accent-blue" size={28} />
          <h1 className="text-3xl font-bold tracking-tight">GeoSentinel</h1>
        </div>

        <p className="text-lg text-slate-300 mb-10 leading-relaxed">
          Una herramienta para seguir en tiempo real lo que está pasando en el mundo: conflictos,
          desastres naturales, incendios, actividad militar aérea y naval. Todo sobre un mapa interactivo 3D.
        </p>

        <Section icon={<Eye size={20} />} title="¿Qué se ve en el mapa?">
          <Item color="#ef4444" label="Círculos rojos" desc="Conflictos activos (guerras, batallas, protestas violentas)." />
          <Item color="#fbbf24" label="Círculos amarillos" desc="Desastres naturales (terremotos, tsunamis, erupciones)." />
          <Item color="#f97316" label="Círculos naranjas" desc="Incendios activos detectados por satélites de la NASA." />
          <Item color="#ea580c" label="Círculos naranja oscuro" desc="Anomalías térmicas: hotspots sin historial de incendios cerca de zonas de conflicto." />
          <Item color="#000000" label="Borde negro" desc="Polígonos de países miembro de la OTAN (32 naciones)." />
          <Item color="#3B82F6" label="Borde azul" desc="Otras Áreas de Interés (AOI): regiones de conflicto activo." />
          <Item color="#1E3A8A" label="Aviones" desc="Vuelos militares en tiempo real. Cada avión apunta en la dirección de vuelo." />
          <Item color="#94A3B8" label="Barcos" desc="Buques de guerra y navales. Los que parpadean más tenues pueden estar ocultando su posición." />
          <Item color="#FBBF24" label="Escudo 🛡️" desc="Instalaciones militares de EEUU en el extranjero (232 bases en 60+ países)." />
        </Section>

        <Section icon={<Flag size={20} />} title="Áreas de Interés — Países OTAN">
          <p className="text-slate-300 leading-relaxed mb-3">
            El mapa incluye <strong className="text-text-primary">32 Áreas de Interés (AOI)</strong> con los polígonos geográficos
            de todos los países miembro de la OTAN, importados desde el archivo oficial de fronteras:
          </p>
          <div className="grid grid-cols-3 gap-x-6 gap-y-1 mb-4 text-slate-300 text-sm">
            {NATO_COUNTRIES.map(c => (
              <div key={c} className="font-mono text-xs">{c}</div>
            ))}
          </div>
          <p className="text-slate-300 leading-relaxed mb-3">
            Cada país OTAN es una AOI independiente con borde <strong className="text-text-primary">negro</strong> para
            diferenciarse de otras zonas de monitorización (conflictos regionales como Irán, Ucrania, Sahel, etc.,
            que usan borde azul).
          </p>
          <p className="text-slate-300 leading-relaxed mb-3">
            Al tener cada país como AOI individual, puedes ver exactamente en qué territorio OTAN ocurre cada incidente.
            Antes solo existía una AOI genérica "Europa + Norte de Marruecos" que agrupaba todo el continente.
          </p>
          <p className="text-slate-300 leading-relaxed">
            Las AOI determinan dónde se buscan datos: el sistema solo consulta las fuentes externas (FIRMS, USGS, GDELT, etc.)
            dentro de estas zonas. Si desactivas la capa ZONAS, las AOI siguen filtrando los datos en segundo plano.
          </p>
        </Section>

        <Section icon={<Shield size={20} />} title="Instalaciones militares de EEUU en el extranjero">
          <p className="text-slate-300 leading-relaxed mb-3">
            GeoSentinel incluye un catálogo de <strong className="text-text-primary">232 bases e instalaciones militares</strong> de
            Estados Unidos desplegadas fuera de su territorio, distribuidas en más de 60 países.
          </p>
          <p className="text-slate-300 leading-relaxed mb-3">
            Cada base se representa con el icono <strong className="text-accent-amber">🛡️</strong> (escudo dorado).
            Al pasar el ratón por encima se muestra un tooltip con el <strong className="text-text-primary">nombre de la base</strong>,
            el <strong className="text-text-primary">país anfitrión</strong> y <strong className="text-text-primary">notas</strong> adicionales
            sobre acuerdos, capacidad o contexto histórico.
          </p>
          <div className="space-y-2 text-slate-300 mb-4">
            <p><strong className="text-text-primary">Alemania:</strong> Ramstein, Stuttgart, Spangdahlem y 30+ instalaciones más.</p>
            <p><strong className="text-text-primary">Japón / Corea del Sur:</strong> Okinawa, Yokosuka, Camp Humphreys y docenas de bases.</p>
            <p><strong className="text-text-primary">Oriente Medio:</strong> Al Udeid (Qatar), Al Dhafra (EAU), Camp Lemonnier (Yibuti), Bahrein.</p>
            <p><strong className="text-text-primary">Europa:</strong> Aviano y Nápoles (Italia), Rota (España), Lajes (Portugal), Incirlik (Turquía).</p>
            <p><strong className="text-text-primary">Global:</strong> Diego Garcia (Índico), Guantánamo (Cuba), Thule (Groenlandia), Ascensión (Atlántico).</p>
          </div>
          <p className="text-slate-300 leading-relaxed mb-3">
            Activa la capa con el botón <strong className="text-text-primary">BASES</strong> en la barra superior.
            Los 🛡️ solo se renderizan cuando están dentro del área visible del mapa para mantener el rendimiento.
          </p>
          <p className="text-slate-300 leading-relaxed">
            <strong className="text-accent-amber">Fuente:</strong> datos recopilados de fuentes abiertas sobre presencia militar de EEUU.
            No incluye bases dentro del territorio continental de Estados Unidos.
          </p>
        </Section>

        <Section icon={<Thermometer size={20} />} title="Detección de anomalías térmicas">
          <p className="text-slate-300 leading-relaxed mb-3">
            GeoSentinel analiza los hotspots de FIRMS (NASA) para detectar posibles movimientos de tropas
            o actividad de campamentos mediante correlación térmica:
          </p>
          <ol className="list-decimal list-inside space-y-2 text-slate-300 mb-4">
            <li>Cada hora, se analizan los hotspots térmicos detectados por los satélites VIIRS y MODIS.</li>
            <li>Se descartan los hotspots en zonas con <strong className="text-text-primary">historial de incendios naturales</strong> (90 días, radio 5 km).</li>
            <li>Los hotspots restantes se cruzan con <strong className="text-text-primary">incidentes de conflicto activos</strong> (radio 10 km).</li>
            <li>Si un hotspot aparece en zona sin historial de incendios pero cerca de un conflicto activo,
              se clasifica como <strong className="text-accent-red">anomalía térmica sospechosa</strong> (posible actividad de vehículos o campamentos).</li>
          </ol>
          <p className="text-slate-300 leading-relaxed">
            <strong className="text-text-primary">Precisión:</strong> el sensor VIIRS tiene una resolución de 375 m.
            Puede detectar grandes concentraciones de calor (convoyes, campamentos) pero no vehículos individuales.
            Las detecciones se marcan como <strong className="text-accent-amber">rumor</strong> hasta confirmación humana.
          </p>
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
          <p className="text-slate-300 leading-relaxed mb-3">
            GeoSentinel consulta varias fuentes públicas cada pocos minutos.
            Los datos en crudo se filtran para eliminar duplicados y errores, se clasifican por tipo y severidad,
            y se muestran sobre el mapa.
          </p>
          <p className="text-slate-300 leading-relaxed mb-3">
            Los vuelos militares se identifican por su código de identificación o por patrones en su señal de radio.
            Los barcos se rastrean por el sistema AIS, obligatorio para la navegación.
          </p>
          <p className="text-slate-300 leading-relaxed mb-3">
            El mapa usa tecnología de Mapbox y puede verse en modo 2D (callejero) o 3D (globo terráqueo).
            Los datos se actualizan automáticamente cada 30 segundos.
          </p>
        </Section>

        <Section icon={<Clock size={20} />} title="Ciclo de vida de un incidente">
          <p className="text-slate-300 leading-relaxed mb-3">
            Cada incidente pasa por una máquina de estados que refleja su actividad real:
          </p>
          <div className="space-y-2 text-slate-300 mb-4">
            <p><span className="inline-block w-2 h-2 rounded-full bg-accent-green mr-2" /><strong className="text-text-primary">open</strong> — Recién detectado. Aparece en el mapa y en la lista de activos.</p>
            <p><span className="inline-block w-2 h-2 rounded-full bg-accent-blue mr-2" /><strong className="text-text-primary">updated</strong> — Ha recibido nuevas observaciones desde fuentes externas.</p>
            <p><span className="inline-block w-2 h-2 rounded-full bg-accent-amber mr-2" /><strong className="text-text-primary">stale</strong> — Sin actividad durante <strong>72 horas</strong>. El sistema lo marca automáticamente. Solo visible con el filtro "Inactivos".</p>
            <p><span className="inline-block w-2 h-2 rounded-full bg-text-secondary mr-2" /><strong className="text-text-primary">closed</strong> — Cerrado manualmente. Visible con el filtro "Cerrados".</p>
            <p><span className="inline-block w-2 h-2 rounded-full bg-accent-red mr-2" /><strong className="text-text-primary">false_positive</strong> — Marcado como error por un operador humano.</p>
          </div>
          <p className="text-slate-300 leading-relaxed mb-3">
            <strong className="text-text-primary">¿Por qué hay incidentes de hace varios días en la lista?</strong>
          </p>
          <p className="text-slate-300 leading-relaxed mb-3">
            La fecha que ves es <strong className="text-text-primary">first_seen</strong>: el momento en que se detectó por primera vez.
            Pero lo que determina si un incidente sigue activo es <strong className="text-text-primary">last_seen</strong>: la última vez que una fuente externa
            reportó algo nuevo sobre él. Si un conflicto lleva días activo y sigue generando reportes,
            se mantiene como <strong className="text-text-primary">updated</strong>. Solo cuando pasan 72 horas sin observaciones nuevas
            pasa a <strong className="text-text-primary">stale</strong>.
          </p>
        </Section>

        <Section icon={<Eye size={20} />} title="¿Dónde se buscan los datos?">
          <p className="text-slate-300 leading-relaxed mb-3">
            <strong className="text-text-primary">GeoSentinel solo busca incidentes, vuelos y buques dentro de las Áreas de Interés (AOI) definidas.</strong>
            {' '}Si no hay zonas activas, no se recupera ningún dato. Las fuentes externas no se consultan de forma global.
          </p>
          <p className="text-slate-300 leading-relaxed mb-3">
            Actualmente hay <strong className="text-text-primary">39 AOI activas</strong>: los 32 países de la OTAN más 7 zonas de conflicto regional (Irán, Ucrania, Sudán,
            Sahel, Myanmar, Colombia, Oriente Medio). Cada AOI es un polígono geográfico que filtra las consultas a las fuentes de datos externas.
          </p>
          <p className="text-slate-300 leading-relaxed mb-3">
            Los países OTAN usan borde <strong className="text-text-primary">negro</strong>; el resto de zonas usan borde azul.
            Puedes activar/desactivar la visualización con el botón ZONAS en la barra superior.
          </p>
          <p className="text-slate-300 leading-relaxed">
            Las zonas se gestionan desde base de datos. Si necesitas monitorizar una región nueva,
            hay que añadir su AOI con las coordenadas correctas.
          </p>
        </Section>

        <Section icon={<Map size={20} />} title="Controles del mapa">
          <div className="space-y-2 text-slate-300">
            <p><strong className="text-text-primary">PUNTOS</strong> — Muestra los incidentes como círculos de colores.</p>
            <p><strong className="text-text-primary">CALOR</strong> — Vista de calor: las zonas con más incidentes se ven más brillantes.</p>
            <p><strong className="text-text-primary">ZONAS</strong> — Muestra las Áreas de Interés (OTAN con borde negro, otras con borde azul).</p>
            <p><strong className="text-text-primary">VUELOS</strong> — Activa la capa de aviones militares en el cielo.</p>
            <p><strong className="text-text-primary">BUQUES</strong> — Activa la capa de barcos en el mar.</p>
            <p><strong className="text-text-primary">BASES</strong> — Muestra las instalaciones militares de EEUU en el extranjero (icono 🛡️).</p>
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
        <span className="text-slate-300 ml-2 text-sm">{desc}</span>
      </div>
    </div>
  )
}

function Source({ name, desc }: { name: string; desc: string }) {
  return (
    <div className="mb-2">
      <span className="text-accent-blue font-medium">{name}</span>
      <span className="text-slate-300 ml-2 text-sm">— {desc}</span>
    </div>
  )
}
