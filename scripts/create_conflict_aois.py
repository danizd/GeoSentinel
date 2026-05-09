import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import WKTElement
from models.aoi import Aoi
import uuid

db_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/geosentinel")
engine = create_engine(db_url)
Session = sessionmaker(bind=engine)

AOIS_CONFLICT = [
    {
        "name": "Ukraine Conflict Zone",
        "description": "Eastern Ukraine conflict area",
        "bbox": (22, 44, 40, 53),  # Eastern Ukraine
        "categories": ["conflict"],
    },
    {
        "name": "Middle East Conflicts",
        "description": "Israel, Gaza, Syria, Yemen conflict zones",
        "bbox": (34, 29, 42, 38),  # Levant region
        "categories": ["conflict"],
    },
    {
        "name": "Sudan Conflict",
        "description": "Darfur and Sudan civil war",
        "bbox": (21, 8, 38, 22),  # Sudan
        "categories": ["conflict"],
    },
    {
        "name": "Sahel Region",
        "description": "Mali, Burkina Faso, Niger conflict belt",
        "bbox": (-5, 10, 15, 25),  # Sahel
        "categories": ["conflict"],
    },
    {
        "name": "Colombia",
        "description": "FARC dissidents and ELN zones",
        "bbox": (-77, 0, -66, 8),  # Colombia
        "categories": ["conflict"],
    },
    {
        "name": "Myanmar",
        "description": "Myanmar civil war",
        "bbox": (92, 10, 101, 28),  # Myanmar
        "categories": ["conflict"],
    },
]

def create_aoi_polygon(bbox):
    lon_min, lat_min, lon_max, lat_max = bbox
    polygon_wkt = f"POLYGON(({lon_min} {lat_min}, {lon_max} {lat_min}, {lon_max} {lat_max}, {lon_min} {lat_max}, {lon_min} {lat_min}))"
    return polygon_wkt

with Session() as session:
    print("Creando AOIs de conflicto...")
    
    for aoi_data in AOIS_CONFLICT:
        polygon = create_aoi_polygon(aoi_data["bbox"])
        
        aoi = Aoi(
            aoi_id=uuid.uuid4(),
            name=aoi_data["name"],
            description=aoi_data["description"],
            geometry=WKTElement(polygon, srid=4326),
            categories=aoi_data["categories"],
            min_severity=3.0,
            is_active=True,
            created_by="system",
        )
        session.add(aoi)
        print(f"  + {aoi_data['name']}: {aoi_data['bbox']}")
    
    session.commit()
    print(f"\n{len(AOIS_CONFLICT)} AOIs de conflicto creados.")

    # Verificar
    from sqlalchemy import select
    aois = session.execute(select(Aoi).where(Aoi.is_active == True)).scalars().all()
    print(f"AOIs activos en BD: {len(aois)}")
