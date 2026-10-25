import asyncio
import hashlib
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Histogram, generate_latest
from psycopg_pool import ConnectionPool
from pydantic import BaseModel

GRUPO = int(os.getenv("GRUPO", "0"))
REPLICA = os.getenv("HOSTNAME", "api")
DB_URL = os.getenv("DB_URL", "postgresql://smartcity:smartcity@postgres:5432/smartcity")

# Trabajo de CPU por lectura: simula validar y firmar el evento
ITERACIONES = 8000 + GRUPO * 400

# Histograma de latencia del lado del servidor
DURACION = Histogram(
    "smartcity_solicitud_duracion_segundos",
    "Duracion de las solicitudes a /lecturas atendidas por la API",
    ["ruta", "estado"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
)

pool = ConnectionPool(DB_URL, min_size=1, max_size=5, open=False)
congelada_hasta = 0.0


@asynccontextmanager
async def ciclo_de_vida(app):
    pool.open(wait=True)
    yield
    pool.close()


app = FastAPI(title="Smart City API", lifespan=ciclo_de_vida)


class Lectura(BaseModel):
    sensorId: str
    zone: str
    value: float


@app.middleware("http")
async def medir(request: Request, call_next):
    ruta = request.url.path
    if ruta == "/metrics":
        return await call_next(request)

    # Si la replica esta "congelada", toda solicitud espera (excepto /admin y /metrics)
    espera = congelada_hasta - time.time()
    if espera > 0 and not ruta.startswith("/admin"):
        await asyncio.sleep(espera)

    inicio = time.perf_counter()
    respuesta = await call_next(request)
    if ruta == "/lecturas":
        DURACION.labels(ruta=ruta, estado=str(respuesta.status_code)).observe(
            time.perf_counter() - inicio
        )
    return respuesta


def firmar(lectura: Lectura) -> str:
    datos = f"{lectura.sensorId}|{lectura.zone}|{lectura.value}".encode()
    for _ in range(ITERACIONES):
        datos = hashlib.sha256(datos).digest()
    return datos.hex()[:16]


@app.post("/lecturas", status_code=201)
def registrar(lectura: Lectura):
    firma = firmar(lectura)
    with pool.connection() as conexion:
        conexion.execute(
            "INSERT INTO lecturas (sensor_id, zona, valor, firma) VALUES (%s, %s, %s, %s)",
            (lectura.sensorId, lectura.zone, lectura.value, firma),
        )
        promedio, cantidad = conexion.execute(
            "SELECT avg(valor), count(*) FROM lecturas "
            "WHERE zona = %s AND ts > now() - interval '1 minute'",
            (lectura.zone,),
        ).fetchone()
    return {
        "replica": REPLICA,
        "firma": firma,
        "promedioZona": round(promedio, 2),
        "lecturasZona": cantidad,
    }


@app.get("/salud")
def salud():
    return {"estado": "ok", "replica": REPLICA}


@app.get("/metrics")
def metricas():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.post("/admin/congelar")
async def congelar(segundos: int = 45):
    global congelada_hasta
    congelada_hasta = time.time() + segundos
    return {"replica": REPLICA, "congelada_por_segundos": segundos}
