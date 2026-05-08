import sys
from pathlib import Path

# Anade la raiz del proyecto al sys.path para que los tests puedan importar
# los paquetes locales (ingestors, validation, jobs, etc.)
ROOT = Path(__file__).parent.resolve()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
