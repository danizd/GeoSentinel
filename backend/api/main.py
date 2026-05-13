from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import incidents, aoi, corrections, health, seed, military, ais


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="GeoSentinel API",
    description="Sistema de monitorización de incidentes en tiempo real",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/v1", tags=["health"])
app.include_router(seed.router, prefix="/v1", tags=["seed"])
app.include_router(incidents.router, prefix="/v1", tags=["incidents"])
app.include_router(aoi.router, prefix="/v1", tags=["aoi"])
app.include_router(corrections.router, prefix="/v1", tags=["corrections"])
app.include_router(military.router, prefix="/v1", tags=["military"])
app.include_router(ais.router, prefix="/v1", tags=["ais"])


@app.get("/")
def root():
    return {"message": "GeoSentinel API", "version": "1.0.0", "docs": "/docs"}