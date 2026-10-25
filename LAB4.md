# Laboratorio 04: Medir antes de afirmar

**Curso:** Arquitectura de Computadores II  
**Tema:** Rendimiento, observabilidad y sistemas distribuidos  
**Modalidad:** Laboratorio práctico en grupos, con Docker y Python  
**Duración de la sesión:** 2 horas, más preparación obligatoria antes de la sesión  
**Prerrequisitos:** Laboratorio 01 (Apache Kafka) y Laboratorio 02 (RabbitMQ y Redis Streams)

## 1. Objetivo

En este laboratorio no aprenderán una tecnología nueva: aprenderán a **demostrar con datos** lo que afirman sobre una arquitectura.

En las presentaciones del proyecto Smart City vimos arquitecturas bien planteadas y dashboards atractivos. Pero cuando la pregunta fue "¿qué significa este p95?" o "¿qué pasa si este servidor se cae?", las respuestas no estuvieron a la altura del diseño.

Un gerente no aprueba una arquitectura porque se vea bien en un diagrama. La aprueba cuando el equipo responde con evidencia: cuánto soporta, dónde se rompe y qué pasa cuando algo falla.

> Un dashboard no es una prueba. Es una pregunta bien graficada, o es decoración.

Al finalizar, deberán ser capaces de:

- Calcular e interpretar la media, la mediana, el p90, el p95 y el p99 de la latencia, y explicar por qué el promedio engaña.
- Relacionar throughput, latencia y concurrencia mediante la **ley de Little**.
- Instrumentar un servicio con métricas y consultarlas con **PromQL**.
- Construir y criticar un dashboard de **Grafana**, y detectar cuándo un panel miente.
- Medir el efecto real del **escalamiento horizontal**.
- Identificar **puntos únicos de falla (SPOF)** y los límites de la observabilidad.
- Defender una decisión de arquitectura usando únicamente sus propios datos.

### 1.1 Agenda de la sesión

Cada sección tiene puntos de verificación: si uno falla, resuélvanlo antes de continuar. La preparación de la sección 3 se hace **antes** de la sesión; si llegan sin ella, no les alcanzará el tiempo.

| Tiempo | Bloque | Resultado esperado |
| --- | --- | --- |
| 0:00 – 0:15 | Verificación del ambiente (sección 5) | Todos los puntos de verificación en orden |
| 0:15 – 0:45 | Parte A: estadística del rendimiento | Estadísticas de la prueba base y su interpretación |
| 0:45 – 1:05 | Parte B: observabilidad | p95 de Prometheus comparado con el calculado a mano |
| 1:05 – 1:25 | Parte C: escalamiento horizontal | Predicción en Git y medición con 3 réplicas |
| 1:25 – 1:50 | Parte D: fallas y SPOF | Réplica colgada, caída de Traefik, tabla de dominios de falla |
| 1:50 – 2:00 | Cierre | Evidencias ordenadas; las preguntas de defensa se responden después |

## 2. Conceptos fundamentales

Antes de medir, necesitamos un vocabulario preciso. Cada término de esta sección aparecerá en las preguntas de defensa.

### 2.1 Latencia y throughput

| Concepto | Definición | Ejemplo en la Smart City |
| --- | --- | --- |
| **Latencia** | Tiempo que tarda una solicitud desde que se envía hasta que llega la respuesta | Una lectura de temperatura tardó 180 ms en ser aceptada |
| **Throughput** | Cantidad de solicitudes atendidas por unidad de tiempo | El sistema acepta 60 lecturas por segundo |
| **Concurrencia** | Cantidad de solicitudes que están en el sistema al mismo tiempo | 10 sensores esperando respuesta simultáneamente |
| **Tasa de error** | Porcentaje de solicitudes que fallan | 2 de cada 100 lecturas fueron rechazadas |

Latencia y throughput **no son lo mismo**. Un sistema puede atender muchas solicitudes por segundo y aun así hacer esperar mucho a cada una.

### 2.2 Percentiles: por qué el promedio engaña

El **percentil 95 (p95)** es el valor por debajo del cual queda el 95 % de las mediciones. Si el p95 de la latencia es 240 ms, entonces el 95 % de las solicitudes tardó 240 ms o menos, y **1 de cada 20 tardó más**.

Es el mismo concepto de cuantil que se estudia en estadística descriptiva, aplicado a ingeniería:

| Medida | Qué dice | Qué esconde |
| --- | --- | --- |
| Media | El valor "promedio" | Se deja arrastrar por valores extremos y puede caer donde ninguna solicitud real estuvo |
| Mediana (p50) | La experiencia típica: la mitad tardó menos, la mitad más | No dice nada de las solicitudes lentas |
| p90, p95 | La experiencia de los usuarios con peor suerte, excluyendo extremos | El 5 % o 10 % más lento |
| p99 | La cola de la distribución: 1 de cada 100 | El 1 % más lento, que en un sistema grande son miles de solicitudes |
| Máximo | El peor caso observado | Es un solo dato: muy sensible al azar |

Las latencias casi nunca siguen una distribución normal. Suelen tener una **cola larga a la derecha**: la mayoría de solicitudes son rápidas y unas pocas son muy lentas. Por eso la media casi siempre queda por encima de la mediana.

> Los percentiles **no se pueden promediar**. El promedio del p95 de tres servidores no es el p95 del sistema. Para obtener el p95 del sistema hay que calcularlo sobre todas las mediciones juntas.

### 2.3 Ley de Little

Relaciona tres magnitudes de cualquier sistema estable, desde un banco hasta un clúster de servidores:

```text
L = λ · W
```

Donde L es la cantidad promedio de solicitudes dentro del sistema, λ (lambda) es el throughput en solicitudes por segundo y W es la latencia promedio en segundos.

Ejemplo: si 10 sensores envían lecturas sin pausa (L = 10) y el sistema acepta 50 lecturas por segundo (λ = 50), cada lectura tarda en promedio W = 10 / 50 = 0.2 s. Si el sistema no puede atender más rápido, agregar sensores **solo aumenta la latencia**.

### 2.4 SLI, SLO y escalamiento

| Concepto | Definición | Ejemplo |
| --- | --- | --- |
| **SLI** (indicador) | La métrica que se mide | p95 de latencia de `/lecturas` |
| **SLO** (objetivo) | El valor que el equipo se compromete a cumplir | "El 95 % de las lecturas se acepta en menos de 300 ms" |
| **Escalamiento vertical** | Dar más recursos a una máquina | Pasar de 2 a 8 CPU |
| **Escalamiento horizontal** | Agregar más máquinas o réplicas | Pasar de 1 a 3 réplicas de la API |
| **Servicio sin estado** | Servicio que no guarda datos propios entre solicitudes, por lo que cualquier réplica puede atender cualquier solicitud | La API guarda las lecturas en PostgreSQL, no en memoria |
| **SPOF** | Punto único de falla: un componente cuya caída detiene todo el sistema | Un solo balanceador, una sola base de datos, un solo servidor físico |

### 2.5 Observabilidad: tipos de métrica

| Tipo | Comportamiento | Ejemplo | Cómo se usa |
| --- | --- | --- | --- |
| **Counter** | Solo aumenta (se reinicia si el proceso se reinicia) | Total de solicitudes atendidas | Se grafica su tasa con `rate()`, nunca el valor crudo |
| **Gauge** | Sube y baja | Memoria en uso, solicitudes en curso | Se grafica directamente |
| **Histogram** | Cuenta cuántas mediciones cayeron en cada rango (bucket) | Latencia de las solicitudes | Se estiman percentiles con `histogram_quantile()` |

Para diseñar un dashboard de un servicio usaremos el **método RED**:

- **R**ate: ¿cuántas solicitudes por segundo llegan?
- **E**rrors: ¿cuántas fallan?
- **D**uration: ¿cuánto tardan (en percentiles)?

Regla de este laboratorio: **el título de cada panel es una pregunta**, y el panel debe poder responderla.

## 3. Arquitectura y preparación

El ambiente simula el servicio de ingesta de lecturas de la Smart City: un balanceador reparte las lecturas entre réplicas de una API, que las guardan en PostgreSQL mientras Prometheus y Grafana observan todo.

```text
                                        ┌──────────┐
                                   ┌───►│  api-1   │───┐
                                   │    └──────────┘   │
┌──────────┐ POST  ┌────────────┐  │    ┌──────────┐   │    ┌──────────────┐
│    k6    │──────►│  Traefik   │──┼───►│  api-2   │───┼───►│  PostgreSQL  │
│  carga   │       │   :8000    │  │    └──────────┘   │    │   lecturas   │
└──────────┘       └─────┬──────┘  │    ┌──────────┐   │    └──────────────┘
                         ┆         └───►│  api-3   │───┘
                         ┆              └────┬─────┘
                         ┆   métricas        ┆  (las 3 réplicas)
                         ┆   cada 5 s        ┆
                         ▼                   ▼
                   ┌──────────────────────────────┐ PromQL ┌──────────────┐
                   │          Prometheus          │───────►│   Grafana    │
                   │      recolecta métricas      │        │    :3000     │
                   └──────────────────────────────┘        └──────────────┘
```

Las flechas sólidas son el camino de cada lectura; las punteadas, las métricas que Prometheus recolecta de cada componente.

| Componente | Función | Puerto en su máquina |
| --- | --- | --- |
| **Traefik** | Balanceador de carga y punto de entrada único | 8000 (API), 8080 (panel) |
| **api-1, api-2, api-3** | Réplicas sin estado de la API de ingesta (FastAPI) | Solo a través de Traefik |
| **PostgreSQL** | Almacenamiento compartido de las lecturas | Interno |
| **Prometheus** | Recolecta métricas de la API y de Traefik cada 5 segundos | 9090 |
| **Grafana** | Visualiza las métricas en un dashboard ya preparado | 3000 |
| **k6** | Generador de carga: simula sensores enviando lecturas | Se ejecuta bajo demanda |

Cada contenedor de la API tiene un **límite de CPU** (`cpus` en el docker-compose). Así los cuellos de botella aparecen en cualquier laptop y los resultados son comparables entre grupos.

### 3.1 Requisitos

```text
Docker
Docker Compose
Python 3.10 o superior
Git
```

Compruébenlo mediante:

```bash
docker --version
docker compose version
python3 --version
git --version
```

En Windows el comando suele ser `python` en lugar de `python3`, y en PowerShell usen `curl.exe` en lugar de `curl`.

### 3.2 Preparación obligatoria (antes de la sesión)

Esta parte **no** se hace durante las 2 horas. Descargar las imágenes puede tardar más de 20 minutos en una red lenta.

1. Creen el directorio del laboratorio y un repositorio Git:

```bash
mkdir smartcity-perf
cd smartcity-perf
git init
```

2. Creen todos los archivos de la sección 4. Al terminar, su directorio deberá verse así:

```text
smartcity-perf/
├── .env
├── docker-compose.yml
├── analizar.py
├── api/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── app.py
│   └── congelar.py
├── db/
│   └── init.sql
├── prometheus/
│   └── prometheus.yml
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/prometheus.yml
│   │   └── dashboards/dashboards.yml
│   └── dashboards/
│       └── smartcity.json
├── k6/
│   └── carga.js
└── resultados/
```

3. Descarguen las imágenes y construyan la API:

```bash
docker compose --profile herramientas pull
docker compose build
```

4. Preparen el entorno de Python para el análisis:

Linux / macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pandas matplotlib
```

Windows (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install pandas matplotlib
```

5. Hagan el primer commit:

```bash
git add .
git commit -m "Laboratorio 04: ambiente inicial"
```

Agreguen `.venv/` a un archivo `.gitignore` para no subir el entorno virtual al repositorio.

## 4. Archivos del laboratorio

Creen cada archivo exactamente con el contenido indicado. Lean el código mientras lo copian: varias respuestas de la defensa dependen de detalles que están aquí.

### 4.1 Variables del grupo: `.env`

Cada grupo usa el **número de grupo asignado en el curso**. Este número modifica ligeramente el comportamiento de la API, por lo que cada grupo obtendrá resultados distintos.

```text
GRUPO=<su número de grupo>
```

Por ejemplo, el grupo 3 escribe `GRUPO=3`.

### 4.2 El ambiente: `docker-compose.yml`

```yaml
name: smartcity-perf

# Configuración común de las réplicas de la API
x-api: &api
  build: ./api
  image: smartcity-api:lab4
  cpus: 0.5
  environment:
    GRUPO: ${GRUPO:-0}
    DB_URL: postgresql://smartcity:smartcity@postgres:5432/smartcity
  depends_on:
    postgres:
      condition: service_healthy
  labels:
    - traefik.enable=true
    - traefik.http.routers.api.rule=PathPrefix(`/`)
    - traefik.http.routers.api.entrypoints=web
    - traefik.http.services.api.loadbalancer.server.port=8000
    - traefik.http.services.api.loadbalancer.healthcheck.path=/salud
    - traefik.http.services.api.loadbalancer.healthcheck.interval=5s
    - traefik.http.services.api.loadbalancer.healthcheck.timeout=2s

services:

  traefik:
    image: traefik:v3
    command:
      - --providers.docker=true
      - --providers.docker.exposedbydefault=false
      - --entrypoints.web.address=:80
      - --entrypoints.metrics.address=:8082
      - --metrics.prometheus=true
      - --metrics.prometheus.entrypoint=metrics
      - --metrics.prometheus.addServicesLabels=true
      - --api.dashboard=true
      - --api.insecure=true
    ports:
      - "8000:80"      # entrada de la API (a través del balanceador)
      - "8080:8080"    # panel de Traefik
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro

  api-1:
    <<: *api
    hostname: api-1

  api-2:
    <<: *api
    hostname: api-2

  api-3:
    <<: *api
    hostname: api-3
    cpus: 0.25

  postgres:
    image: postgres:17
    cpus: 1
    environment:
      POSTGRES_USER: smartcity
      POSTGRES_PASSWORD: smartcity
      POSTGRES_DB: smartcity
    volumes:
      - ./db/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U smartcity -d smartcity"]
      interval: 5s
      timeout: 3s
      retries: 10

  prometheus:
    image: prom/prometheus:latest
    volumes:
      - ./prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:latest
    environment:
      GF_SECURITY_ADMIN_USER: smartcity
      GF_SECURITY_ADMIN_PASSWORD: smartcity
    volumes:
      - ./grafana/provisioning:/etc/grafana/provisioning:ro
      - ./grafana/dashboards:/var/lib/grafana/dashboards:ro
    ports:
      - "3000:3000"
    depends_on:
      - prometheus

  k6:
    image: grafana/k6:latest
    profiles: ["herramientas"]
    user: root
    volumes:
      - ./k6:/scripts:ro
      - ./resultados:/resultados
```

Observen tres detalles:

- Las tres réplicas comparten la configuración `x-api` mediante un ancla de YAML (`&api` y `<<: *api`). Traefik las descubre a todas a través de sus etiquetas (`labels`) y las agrupa en un mismo servicio llamado `api`.
- Traefik revisa la salud de cada réplica consultando `/salud` cada 5 segundos. Si una réplica no responde en 2 segundos, deja de enviarle tráfico.
- El servicio `k6` pertenece al perfil `herramientas`: no se levanta con los demás, solo se ejecuta cuando lo invocamos.

### 4.3 La API: `api/app.py`

```python
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
```

Cada lectura que llega a `/lecturas` pasa por tres pasos: se "firma" con trabajo de CPU, se guarda en PostgreSQL y se calcula el promedio reciente de su zona. El endpoint `/admin/congelar` simula una réplica que se queda colgada; lo usaremos en la Parte D.

### 4.4 Script para congelar una réplica: `api/congelar.py`

```python
import sys
import urllib.request

segundos = sys.argv[1] if len(sys.argv) > 1 else "45"
solicitud = urllib.request.Request(
    f"http://localhost:8000/admin/congelar?segundos={segundos}", method="POST"
)
print(urllib.request.urlopen(solicitud).read().decode())
```

### 4.5 Dependencias y imagen: `api/requirements.txt` y `api/Dockerfile`

```text
fastapi
uvicorn
psycopg[binary]
psycopg-pool
prometheus-client
```

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py congelar.py ./

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
```

### 4.6 La base de datos: `db/init.sql`

```sql
CREATE TABLE lecturas (
    id        BIGSERIAL PRIMARY KEY,
    sensor_id TEXT             NOT NULL,
    zona      TEXT             NOT NULL,
    valor     DOUBLE PRECISION NOT NULL,
    firma     TEXT             NOT NULL,
    ts        TIMESTAMPTZ      NOT NULL DEFAULT now()
);

CREATE INDEX idx_lecturas_zona_ts ON lecturas (zona, ts);
```

### 4.7 Recolección de métricas: `prometheus/prometheus.yml`

```yaml
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: api
    static_configs:
      - targets: ["api-1:8000", "api-2:8000", "api-3:8000"]

  - job_name: traefik
    static_configs:
      - targets: ["traefik:8082"]
```

Prometheus funciona por **pull**: cada 5 segundos visita `/metrics` de cada objetivo y guarda lo que encuentra como series de tiempo.

### 4.8 Grafana: fuente de datos y dashboard

`grafana/provisioning/datasources/prometheus.yml`:

```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    uid: prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
```

`grafana/provisioning/dashboards/dashboards.yml`:

```yaml
apiVersion: 1

providers:
  - name: smartcity
    folder: Smart City
    type: file
    options:
      path: /var/lib/grafana/dashboards
```

`grafana/dashboards/smartcity.json`:

```json
{
  "uid": "smartcity-perf",
  "title": "Smart City - Rendimiento",
  "schemaVersion": 39,
  "refresh": "5s",
  "time": { "from": "now-15m", "to": "now" },
  "panels": [
    {
      "type": "timeseries",
      "title": "¿Cuántas lecturas por segundo acepta el sistema?",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 0 },
      "fieldConfig": { "defaults": { "unit": "reqps" } },
      "targets": [
        { "refId": "A", "legendFormat": "lecturas aceptadas/s",
          "expr": "sum(rate(smartcity_solicitud_duracion_segundos_count{estado=\"201\"}[30s]))" }
      ]
    },
    {
      "type": "timeseries",
      "title": "¿Cómo se reparte el tráfico entre réplicas?",
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 0 },
      "fieldConfig": { "defaults": { "unit": "reqps" } },
      "targets": [
        { "refId": "A", "legendFormat": "{{instance}}",
          "expr": "sum by (instance) (rate(smartcity_solicitud_duracion_segundos_count[30s]))" }
      ]
    },
    {
      "type": "timeseries",
      "title": "p95 del sistema (ms)",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 8 },
      "fieldConfig": { "defaults": { "unit": "ms" } },
      "targets": [
        { "refId": "A", "legendFormat": "p95",
          "expr": "avg(histogram_quantile(0.95, sum by (le, instance) (rate(smartcity_solicitud_duracion_segundos_bucket[30s])))) * 1000" }
      ]
    },
    {
      "type": "timeseries",
      "title": "Latencia p50 y p99 del sistema (ms)",
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 8 },
      "fieldConfig": { "defaults": { "unit": "ms" } },
      "targets": [
        { "refId": "A", "legendFormat": "p50",
          "expr": "histogram_quantile(0.50, sum by (le) (rate(smartcity_solicitud_duracion_segundos_bucket[30s]))) * 1000" },
        { "refId": "B", "legendFormat": "p99",
          "expr": "histogram_quantile(0.99, sum by (le) (rate(smartcity_solicitud_duracion_segundos_bucket[30s]))) * 1000" }
      ]
    },
    {
      "type": "timeseries",
      "title": "¿Qué porcentaje de lecturas falla en la API?",
      "gridPos": { "h": 8, "w": 12, "x": 0, "y": 16 },
      "fieldConfig": { "defaults": { "unit": "percent" } },
      "targets": [
        { "refId": "A", "legendFormat": "% de fallas",
          "expr": "100 * sum(rate(smartcity_solicitud_duracion_segundos_count{estado!=\"201\"}[30s])) / sum(rate(smartcity_solicitud_duracion_segundos_count[30s]))" }
      ]
    },
    {
      "type": "timeseries",
      "title": "Traefik: solicitudes por segundo según código HTTP",
      "gridPos": { "h": 8, "w": 12, "x": 12, "y": 16 },
      "fieldConfig": { "defaults": { "unit": "reqps" } },
      "targets": [
        { "refId": "A", "legendFormat": "HTTP {{code}}",
          "expr": "sum by (code) (rate(traefik_service_requests_total[30s]))" }
      ]
    },
    {
      "type": "timeseries",
      "title": "¿Qué réplicas reporta Prometheus como activas? (1 = activa)",
      "gridPos": { "h": 8, "w": 24, "x": 0, "y": 24 },
      "targets": [
        { "refId": "A", "legendFormat": "{{instance}}",
          "expr": "up{job=\"api\"}" }
      ]
    }
  ]
}
```

### 4.9 El generador de carga: `k6/carga.js`

```javascript
import http from 'k6/http';
import { check, sleep } from 'k6';

const URL = __ENV.URL || 'http://traefik/lecturas';
const ZONAS = ['zona-1', 'zona-4', 'zona-7', 'zona-10', 'zona-11'];

export const options = {
  vus: Number(__ENV.VUS || 10),
  duration: __ENV.DURACION || '2m',
  summaryTrendStats: ['avg', 'min', 'med', 'p(90)', 'p(95)', 'p(99)', 'max'],
};

export default function () {
  const lectura = {
    sensorId: `TEMP-${String(__VU).padStart(3, '0')}`,
    zone: ZONAS[Math.floor(Math.random() * ZONAS.length)],
    value: 20 + Math.random() * 15,
  };

  const respuesta = http.post(URL, JSON.stringify(lectura), {
    headers: { 'Content-Type': 'application/json' },
    timeout: '60s',
  });

  const aceptada = check(respuesta, {
    'lectura aceptada (201)': (r) => r.status === 201,
  });

  // Si falla, esperar medio segundo antes de reintentar
  if (!aceptada) {
    sleep(0.5);
  }
}
```

k6 simula **10 usuarios virtuales (VUs)**, es decir, 10 sensores que envían una lectura, esperan la respuesta y envían la siguiente sin pausa. Por defecto la prueba dura 2 minutos.

### 4.10 El análisis estadístico: `analizar.py`

```python
"""Análisis estadístico de una prueba de carga de k6 exportada a CSV."""

import argparse
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

parser = argparse.ArgumentParser(description="Analiza el CSV de una prueba de k6")
parser.add_argument("archivo", help="ruta del CSV generado por k6")
parser.add_argument("--umbral", type=float, help="contar solicitudes más lentas que este valor (ms)")
args = parser.parse_args()

datos = pd.read_csv(args.archivo, low_memory=False)

duraciones = datos[datos["metric_name"] == "http_req_duration"]
fallas = datos[(datos["metric_name"] == "http_req_failed") & (datos["metric_value"] == 1)]
exitosas = duraciones[duraciones["expected_response"].astype(str).str.lower() == "true"]
latencia = exitosas["metric_value"]

inicio = duraciones["timestamp"].min()
fin = duraciones["timestamp"].max()
segundos = fin - inicio + 1

print(f"\nArchivo: {args.archivo}")
print(f"Duración de la prueba:    {segundos} s")
print(f"Solicitudes totales:      {len(duraciones)}")
print(f"Solicitudes exitosas:     {len(exitosas)}")
print(f"Solicitudes fallidas:     {len(fallas)}")
print(f"Throughput (exitosas/s):  {len(exitosas) / segundos:.2f}")

print("\nLatencia de las solicitudes exitosas (ms)")
print(f"  media:       {latencia.mean():9.1f}")
print(f"  mediana:     {latencia.median():9.1f}")
print(f"  p90:         {latencia.quantile(0.90):9.1f}")
print(f"  p95:         {latencia.quantile(0.95):9.1f}")
print(f"  p99:         {latencia.quantile(0.99):9.1f}")
print(f"  máximo:      {latencia.max():9.1f}")
print(f"  desv. est.:  {latencia.std():9.1f}")

if len(fallas) > 0:
    primera, ultima = fallas["timestamp"].min(), fallas["timestamp"].max()
    print("\nFallas")
    print(f"  primera: {datetime.fromtimestamp(primera):%H:%M:%S} (segundo {primera - inicio} de la prueba)")
    print(f"  última:  {datetime.fromtimestamp(ultima):%H:%M:%S} (segundo {ultima - inicio} de la prueba)")

if args.umbral is not None:
    lentas = duraciones[duraciones["metric_value"] > args.umbral]
    print(f"\nSolicitudes con latencia mayor a {args.umbral:.0f} ms: {len(lentas)}")

# Histograma con las medidas de posición marcadas
salida = Path(args.archivo).with_name(Path(args.archivo).stem + "_histograma.png")
fig, eje = plt.subplots(figsize=(10, 5))
eje.hist(latencia, bins=60, color="#7f8c8d", edgecolor="white")
marcas = [
    ("media", latencia.mean(), "#2980b9"),
    ("p50", latencia.median(), "#27ae60"),
    ("p95", latencia.quantile(0.95), "#e67e22"),
    ("p99", latencia.quantile(0.99), "#c0392b"),
]
for nombre, valor, color in marcas:
    eje.axvline(valor, color=color, linestyle="--", linewidth=1.5, label=f"{nombre}: {valor:.0f} ms")
eje.set_title(f"Distribución de la latencia: {Path(args.archivo).name}")
eje.set_xlabel("Latencia (ms)")
eje.set_ylabel("Cantidad de solicitudes")
eje.legend()
fig.tight_layout()
fig.savefig(salida, dpi=120)
print(f"\nHistograma guardado en: {salida}\n")
```

Este script hace a mano lo que Grafana hará después: a partir de los tiempos de **cada** solicitud registrada por k6, calcula las estadísticas y dibuja el histograma. Así tendrán una referencia para verificar lo que muestran los dashboards.

## 5. Levantar y verificar el ambiente

Iniciamos con **una sola réplica** de la API. Las otras dos se agregarán en la Parte C.

```bash
docker compose up -d traefik api-1 postgres prometheus grafana
```

Recorran estos puntos de verificación en orden. No continúen si alguno falla.

**Verificación 1: contenedores.** Ejecuten `docker compose ps`. Deben aparecer 5 contenedores en estado `running`; `postgres` debe indicar `healthy`.

**Verificación 2: la API responde a través de Traefik.**

```bash
curl http://localhost:8000/salud
```

Respuesta esperada:

```text
{"estado":"ok","replica":"api-1"}
```

**Verificación 3: se puede registrar una lectura.**

```bash
curl -X POST http://localhost:8000/lecturas -H "Content-Type: application/json" -d "{\"sensorId\":\"TEMP-001\",\"zone\":\"zona-1\",\"value\":28.5}"
```

Deben recibir un JSON con `replica`, `firma`, `promedioZona` y `lecturasZona`.

**Verificación 4: Traefik.** Abran `http://localhost:8080`. En **HTTP → Services** debe aparecer `api@docker` con **1 servidor**.

**Verificación 5: Prometheus.** Abran `http://localhost:9090/targets`. Deben ver `api-1` y `traefik` en estado **UP**. Los objetivos `api-2` y `api-3` aparecerán **DOWN**: es lo esperado, todavía no existen.

**Verificación 6: Grafana.** Abran `http://localhost:3000` (usuario `smartcity`, contraseña `smartcity`). En **Dashboards → Smart City** abran **Smart City - Rendimiento**.

**Verificación 7: prueba de humo de k6.**

```bash
docker compose run --rm k6 run -e DURACION=10s /scripts/carga.js
```

Al final del resumen, la línea del check `lectura aceptada (201)` debe mostrar 100 %.

| Problema | Causa probable | Solución |
| --- | --- | --- |
| Traefik muestra un error de versión del cliente de Docker | Imagen de Traefik antigua | `docker compose pull traefik` y volver a levantar |
| `port is already allocated` | Otro programa usa el puerto 8000, 8080, 9090 o 3000 | Cambiar el puerto del lado izquierdo en `docker-compose.yml` |
| `curl` devuelve 404 o `Bad Gateway` | La API todavía está iniciando | Esperar unos segundos y revisar `docker compose logs api-1` |
| Grafana no muestra el dashboard | Ruta o nombre de carpeta incorrecto | Revisar la estructura de la sección 3.2 |

---

# PARTE A: Estadística del rendimiento

## 6. La prueba base

En esta parte calcularemos las estadísticas **a mano**, a partir de cada solicitud individual, antes de mirar cualquier dashboard.

### 6.1 Calentamiento

Un sistema recién iniciado no se comporta igual que uno en operación: las conexiones a la base de datos se están abriendo y las cachés están vacías. Por eso la primera corrida **se descarta**:

```bash
docker compose run --rm k6 run -e DURACION=30s /scripts/carga.js
```

### 6.2 Dos corridas de la prueba base

Anoten la **hora de inicio y fin** de cada corrida; la necesitarán para ubicarla en Grafana.

```bash
docker compose run --rm k6 run --out csv=/resultados/base1.csv /scripts/carga.js
```

Al terminar, tomen una captura del resumen de k6. Luego repitan exactamente la misma prueba:

```bash
docker compose run --rm k6 run --out csv=/resultados/base2.csv /scripts/carga.js
```

### 6.3 Análisis

Con el entorno virtual activo:

```bash
python analizar.py resultados/base1.csv
python analizar.py resultados/base2.csv
```

Cada ejecución imprime las estadísticas y genera un histograma en `resultados/`.

Creen el archivo `respuestas.md` en la raíz del repositorio y registren:

| Medida | base1 | base2 | Diferencia (%) |
| --- | --- | --- | --- |
| Throughput (lecturas/s) |  |  |  |
| Media (ms) |  |  |  |
| Mediana (ms) |  |  |  |
| p90 (ms) |  |  |  |
| p95 (ms) |  |  |  |
| p99 (ms) |  |  |  |
| Máximo (ms) |  |  |  |

### 6.4 Interpretación

Respondan en `respuestas.md`, siempre con sus propios números:

1. Comparen el p95 del resumen de k6 con el p95 de `analizar.py`. ¿Coinciden? Si hay una diferencia pequeña, ¿a qué se debe?
2. Observen el histograma de `base1`. ¿Es simétrico? ¿La media quedó por encima o por debajo de la mediana? Expliquen por qué.
3. Completen la oración: *"El \_\_\_ % de las lecturas fue aceptado en \_\_\_ ms o menos; 1 de cada \_\_\_ tardó más."*
4. **Ley de Little.** Con λ = throughput de `base1` y W = latencia media en segundos, calculen L = λ · W. Comparénlo con los 10 usuarios virtuales de k6. ¿Coincide? Si no coincide exactamente, ¿qué tiempo no está contando la latencia?
5. **Variabilidad.** ¿Cuánto difieren `base1` y `base2` en el p95 y en el throughput? Si dos corridas idénticas difieren en X %, una "mejora" menor que X % no está demostrada.

---

# PARTE B: Observabilidad

## 7. Prometheus y Grafana

Ya tienen un p95 calculado a partir de cada solicitud. Ahora veremos cómo lo calcula un sistema de monitoreo, que **no guarda cada solicitud**, sino conteos agrupados.

### 7.1 Las métricas crudas

```bash
curl http://localhost:8000/metrics
```

Busquen las líneas que comienzan con `smartcity_solicitud_duracion_segundos`. Encontrarán tres tipos:

- `_bucket{le="0.5"}`: cuántas solicitudes tardaron **0.5 segundos o menos**. Los buckets son acumulativos: cada uno incluye a los anteriores.
- `_count`: total de solicitudes medidas.
- `_sum`: suma de todas las duraciones.

Comparen los límites `le` con los `buckets` definidos en `app.py`.

### 7.2 Consultas PromQL

Abran `http://localhost:9090/query`. Ejecuten cada consulta, primero en la pestaña **Graph** con un rango que cubra sus dos corridas base.

1. El contador crudo:

```text
smartcity_solicitud_duracion_segundos_count
```

La línea solo sube. ¿Qué información útil se puede obtener de esta gráfica tal como está?

2. La tasa por segundo:

```text
rate(smartcity_solicitud_duracion_segundos_count[30s])
```

Comparénla con el throughput que obtuvieron en la Parte A.

3. El p95 estimado por Prometheus para toda la corrida `base1`. Cambien a la pestaña **Table**, ajusten el **tiempo de evaluación** a la hora en que terminó `base1` y ejecuten:

```text
histogram_quantile(0.95, sum by (le) (rate(smartcity_solicitud_duracion_segundos_bucket[2m]))) * 1000
```

La ventana `[2m]` cubre los 2 minutos de la corrida, así que el resultado es comparable con el p95 calculado a mano.

### 7.3 Comparación: Prometheus contra el cálculo a mano

Registren en `respuestas.md`:

| Corrida | p95 calculado con `analizar.py` (ms) | p95 estimado por Prometheus (ms) | Diferencia (%) |
| --- | --- | --- | --- |
| base1 |  |  |  |

Luego respondan:

1. ¿Entre qué dos límites `le` cae su p95? Prometheus no conoce el valor exacto de cada solicitud dentro de ese bucket. ¿Qué supone sobre cómo se reparten dentro de él?
2. k6 mide la latencia desde el **cliente** y la API la mide desde el **servidor**. ¿Qué tiempo queda fuera de la medición del servidor?
3. Si tuvieran que reportar el p95 a un gerente, ¿cuál de los dos usarían y por qué?
4. ¿Qué cambiarían en `app.py` para que Prometheus estimara mejor el p95? ¿Qué costo tendría ese cambio?

### 7.4 Leer el dashboard con ojo crítico

En Grafana, ajusten el rango de tiempo para cubrir sus corridas base. Completen esta tabla en `respuestas.md`:

| Panel | ¿Qué pregunta responde? | Valor observado durante base1 | ¿La responde correctamente? ¿Cómo lo saben? |
| --- | --- | --- | --- |
| Lecturas por segundo |  |  |  |
| Tráfico por réplica |  |  |  |
| p95 del sistema |  |  |  |
| p50 y p99 del sistema |  |  |  |
| Porcentaje de fallas |  |  |  |
| Traefik por código HTTP |  |  |  |
| Réplicas activas |  |  |  |

Identifiquen qué paneles cubren cada letra del método **RED**.

Para cada consulta, hagan clic en el título del panel y elijan **Edit** para leer su PromQL. No confíen en un panel cuya consulta no entienden. Vuelvan a esta tabla al terminar la Parte C: algún valor podría cambiar de significado.

---

# PARTE C: Escalamiento horizontal

## 8. De una réplica a tres

La respuesta intuitiva es "tres servidores, el triple de capacidad". En esta parte la pondremos a prueba.

### 8.1 Predicción antes de medir

Antes de agregar réplicas, creen el archivo `prediccion.md`:

| Medida | base1 (medido) | Predicción con 3 réplicas | Razonamiento |
| --- | --- | --- | --- |
| Throughput (lecturas/s) |  |  |  |
| p50 (ms) |  |  |  |
| p99 (ms) |  |  |  |

Revisen el `docker-compose.yml` antes de predecir. Luego hagan commit:

```bash
git add prediccion.md respuestas.md
git commit -m "Prediccion antes de escalar"
```

No modifiquen `prediccion.md` después de este commit. **No se califica acertar, sino el razonamiento**: una predicción equivocada pero bien argumentada vale más que una correcta escrita después de medir. El historial de Git muestra cuándo se escribió cada archivo.

### 8.2 Agregar las réplicas

```bash
docker compose up -d api-2 api-3
```

Verifiquen que Traefik reparte el tráfico ejecutando varias veces `/salud`.

Linux / macOS:

```bash
for i in 1 2 3 4 5 6; do curl -s http://localhost:8000/salud; echo; done
```

Windows (PowerShell):

```powershell
1..6 | ForEach-Object { curl.exe -s http://localhost:8000/salud; "" }
```

Deben aparecer `api-1`, `api-2` y `api-3`. Confirmen también que Traefik muestra **3 servidores** y que Prometheus marca los tres objetivos de la API como **UP**.

### 8.3 Medir con tres réplicas

Calentamiento:

```bash
docker compose run --rm k6 run -e DURACION=30s /scripts/carga.js
```

Prueba (anoten la hora de inicio y fin):

```bash
docker compose run --rm k6 run --out csv=/resultados/escalado.csv /scripts/carga.js
```

Mientras la prueba corre, en otra terminal tomen una captura del consumo de recursos:

```bash
docker stats --no-stream
```

Al terminar:

```bash
python analizar.py resultados/escalado.csv
```

### 8.4 Registrar y comparar

En `respuestas.md`:

| Medida | base1 | escalado | Factor (escalado / base1) |
| --- | --- | --- | --- |
| Throughput (lecturas/s) |  |  |  |
| p50 (ms) |  |  |  |
| p95 (ms) |  |  |  |
| p99 (ms) |  |  |  |
| Máximo (ms) |  |  |  |

Comparen el histograma de `escalado` con el de `base1`. ¿Cambió la forma de la distribución, no solo su posición?

### 8.5 Investigar por réplica

En Prometheus, para el intervalo de la prueba `escalado`, ejecuten:

```text
sum by (instance) (rate(smartcity_solicitud_duracion_segundos_count[1m]))
```

```text
histogram_quantile(0.95, sum by (le, instance) (rate(smartcity_solicitud_duracion_segundos_bucket[1m]))) * 1000
```

Respondan: ¿las tres réplicas reciben la misma cantidad de solicitudes por segundo? ¿Responden con la misma latencia? Usen la captura de `docker stats` y el `docker-compose.yml` para explicar lo que observan.

Finalmente, regresen a la tabla de la sección 7.4 y revisen de nuevo cada panel con los datos de `escalado`. Hagan un segundo commit:

```bash
git add .
git commit -m "Resultados de escalamiento"
```

---

# PARTE D: Fallas y puntos únicos de falla

## 9. Romper el sistema a propósito

Un sistema distribuido no se evalúa por cómo funciona cuando todo está bien, sino por cómo se comporta cuando algo falla. En esta parte provocaremos dos fallas distintas y observaremos qué ve cada herramienta.

### 9.1 Una réplica colgada

Una réplica colgada no se apaga: sigue encendida, pero no responde. Es una de las fallas más difíciles de detectar en producción.

1. Con las tres réplicas activas, en la terminal 1 inicien la prueba y anoten la hora:

```bash
docker compose run --rm k6 run --out csv=/resultados/colgada.csv /scripts/carga.js
```

2. Unos 30 segundos después, en la terminal 2, congelen `api-2` durante 45 segundos:

```bash
docker compose exec api-2 python congelar.py 45
```

3. Durante esos 45 segundos, observen y capturen: el panel de Traefik (servicio `api@docker`), la página de objetivos de Prometheus (`http://localhost:9090/targets`) y el dashboard de Grafana.
4. Al terminar la prueba:

```bash
python analizar.py resultados/colgada.csv --umbral 5000
```

Registren en `respuestas.md`:

| Herramienta | ¿Qué mostró sobre `api-2` durante el congelamiento? |
| --- | --- |
| Panel de Traefik |  |
| Objetivos de Prometheus |  |
| Grafana: réplicas activas |  |
| Grafana: tráfico por réplica |  |
| Grafana: porcentaje de fallas |  |
| `analizar.py` (solicitudes mayores a 5000 ms, máximo, fallas) |  |

### 9.2 La caída del balanceador

1. En la terminal 1 inicien la prueba y anoten la hora:

```bash
docker compose run --rm k6 run --out csv=/resultados/sin_traefik.csv /scripts/carga.js
```

2. Unos 30 segundos después, en la terminal 2, detengan Traefik. Esperen 30 segundos y vuelvan a iniciarlo:

```bash
docker compose stop traefik
```

```bash
docker compose start traefik
```

3. Al terminar la prueba:

```bash
python analizar.py resultados/sin_traefik.csv
```

4. En Grafana, ubiquen exactamente el intervalo en que Traefik estuvo detenido y tomen una captura de **todo el dashboard** con la hora visible.

Registren cuántas solicitudes fallaron según `analizar.py`, entre qué segundos de la prueba ocurrieron las fallas, y qué mostró cada panel de Grafana en ese mismo intervalo.

### 9.3 Dominios de falla

Completen esta tabla para el ambiente del laboratorio:

| Componente | ¿Qué pasa si falla? | ¿Es SPOF? | ¿Cómo se enterarían? (métrica o alerta) | ¿Cómo se eliminaría en la nube? |
| --- | --- | --- | --- | --- |
| Traefik |  |  |  |  |
| Una réplica de la API |  |  |  |  |
| PostgreSQL |  |  |  |  |
| Prometheus |  |  |  |  |
| Grafana |  |  |  |  |
| Docker Engine |  |  |  |  |
| La laptop completa |  |  |  |  |

Respondan: si las tres réplicas corren en la misma laptop, ¿contra qué tipo de falla las protegen y contra cuál no?

Después, construyan **la misma tabla para la arquitectura de su proyecto Smart City**, con sus propios componentes. Esa tabla es parte de su defensa.

Hagan un último commit:

```bash
git add .
git commit -m "Experimentos de fallas y dominios de falla"
```

---

## 10. Preguntas de defensa

Estas preguntas se responden **después de la sesión**, en `respuestas.md`. Todas dependen de sus datos: una respuesta correcta en teoría pero sin sus números vale cero.

Pueden usar cualquier herramienta, incluida la inteligencia artificial, para entender los conceptos. Pero ninguna herramienta puede ver sus datos: las respuestas deben construirse con ellos, y ustedes deben poder explicarlas.

1. **Predicción.** Comparen su `prediccion.md` con los resultados de `escalado`. ¿En qué acertaron, en qué se equivocaron y qué no consideraron? Incluyan el hash del commit de la predicción (`git log --oneline`).
2. Expliquen, con sus datos, por qué el throughput se triplicó al pasar de una a tres réplicas.
3. Al pasar de una a tres réplicas, ¿qué ocurrió con el p50 y con el p99? Si alguno mejoró menos de lo esperado o empeoró, identifiquen qué réplica es responsable, muestren la consulta PromQL que lo prueba y expliquen la causa con evidencia.
4. Uno de los paneles del dashboard entregado presenta un valor incorrecto durante la prueba `escalado`. Identifíquenlo, calculen cuánto se equivoca usando su CSV, escriban la consulta corregida y expliquen por qué con una sola réplica el error no era visible.
5. Escriban en una oración qué significa su p95 de `base1`. Luego escriban qué **no** dice ese número. Finalmente: si la pantalla del centro de control hace **(10 + número de grupo)** solicitudes para cargarse, ¿cuál es la probabilidad de que al menos una supere el p95? ¿Qué le dirían a un gerente con ese resultado?
6. Al detener Traefik, ¿cuántas solicitudes fallaron según su CSV? Comparénlo con lo que mostró Grafana en ese mismo intervalo y expliquen la diferencia. ¿Qué implica esto para el monitoreo de su proyecto Smart City?
7. Durante la réplica congelada: ¿cuántas solicitudes tardaron más de 5 segundos? ¿Prometheus consideró a `api-2` activa o caída? ¿Por qué Traefik dejó de enviarle tráfico y Prometheus no lo notó? ¿Qué parámetros de su configuración controlan cuánto tarda Traefik en reaccionar y qué costo tendría reducirlos?
8. La ciudad necesita aceptar **(50 × número de grupo)** lecturas por segundo. Con sus mediciones, ¿cuántas réplicas necesitarían? ¿Por qué agregar réplicas en la misma máquina deja de servir a partir de cierto punto? ¿Qué cambiarían en la arquitectura?
9. Sus corridas `base1` y `base2` difirieron en cierto porcentaje en el p95. ¿Qué mejora mínima tendría que mostrar una optimización para considerarla real? ¿Qué harían para reducir esa incertidumbre?

## 11. Entrega y reglas de evidencia

Entreguen el repositorio completo, **incluida la carpeta `.git`** para que el historial de commits sea visible. Debe contener:

- Todo el código de la sección 4.
- La carpeta `resultados/` con los CSV y los histogramas de todas las corridas.
- `prediccion.md` y `respuestas.md`.
- Una carpeta `capturas/` con: resúmenes de k6, el dashboard de Grafana de cada experimento con la hora visible, Traefik con 3 servidores, objetivos de Prometheus durante el congelamiento y la salida de `docker stats`.
- Las dos tablas de dominios de falla: la del laboratorio y la de su proyecto.

**Reglas:**

1. Toda respuesta numérica cita su fuente: el CSV y el comando que lo analizó, la consulta PromQL, o una captura con la hora visible. **Sin evidencia, la respuesta vale cero.**
2. Las respuestas usan los números de su propio grupo. Dos entregas con los mismos datos serán revisadas.
3. **Defensa oral.** En la siguiente clase se elegirá al azar a un integrante de cada grupo para explicar una pregunta elegida al azar. La calificación de esa pregunta depende de esa explicación. Todos los integrantes deben poder explicar todas las respuestas.

| Componente | Ponderación |
| --- | --- |
| Ejecución de los experimentos y evidencias | 25 % |
| Parte A: estadísticas e interpretación | 20 % |
| Preguntas de defensa (escritas) | 30 % |
| Defensa oral | 15 % |
| Tabla de dominios de falla del proyecto Smart City | 10 % |

## 12. Retos opcionales

Para quienes quieran ir más allá. Cada reto debe documentarse con la misma regla: medición antes, medición después y evidencia.

1. **Buckets correctos.** Cambien los `buckets` de `app.py` para que Prometheus estime mejor el p95 y repitan la comparación de la sección 7.3.
2. **Limitación de tasa.** Agreguen un middleware `ratelimit` de Traefik. Comparen un sistema que responde `429 Too Many Requests` de forma controlada contra uno que colapsa.
3. **Caché.** Agreguen Redis con el patrón *cache-aside* para el promedio por zona. Midan la latencia y la proporción de aciertos de caché.
4. **Síncrono contra asíncrono.** Creen un endpoint que publique la lectura en RabbitMQ y responda `202 Accepted`. Comparen su comportamiento ante un pico de carga con el endpoint actual.
5. **Modelo abierto de carga.** Usen el executor `constant-arrival-rate` de k6, que envía solicitudes a ritmo fijo sin esperar respuestas. Comparen las latencias con las del modelo cerrado que usamos.

## 13. Para seguir estudiando

Este laboratorio apenas toca la superficie. Cada tema de esta tabla es un campo completo de estudio; no tienen que dominarlos ahora, pero sí saber que existen.

| Tema | Por qué importa | Por dónde empezar |
| --- | --- | --- |
| Omisión coordinada y modelos de carga | Muchas pruebas de carga subestiman la latencia real sin que nadie lo note | Charla "How NOT to Measure Latency" de Gil Tene; executors de k6 |
| Teoría de colas | Explica por qué la latencia se dispara cuando un recurso se acerca al 100 % de uso | Ley de Little y el modelo M/M/1 |
| Ley universal de escalabilidad | Explica por qué cada nodo adicional rinde menos que el anterior | Trabajo de Neil Gunther sobre la USL |
| Trazas distribuidas | Permiten seguir una solicitud a través de varios servicios | [OpenTelemetry](https://opentelemetry.io/docs/) |
| SRE, SLO y presupuesto de errores | Convierten la confiabilidad en un acuerdo medible con el negocio | Libros de Google SRE, gratuitos en [sre.google](https://sre.google/books/) |
| Orquestación y autoescalamiento | Escalar y recuperarse sin intervención manual | Kubernetes y el HorizontalPodAutoscaler |
| Alta disponibilidad en la nube | Eliminar los SPOF de máquina, de zona y de región | Zonas de disponibilidad, RPO y RTO, pilar de confiabilidad de AWS Well-Architected |
| Ingeniería del caos | Provocar fallas controladas antes de que ocurran solas | [Principles of Chaos Engineering](https://principlesofchaos.org/) |
| Sistemas de datos distribuidos | Consistencia, replicación y consenso entre nodos | *Designing Data-Intensive Applications* de Martin Kleppmann; CAP y PACELC; algoritmo Raft |

## 14. Detener el laboratorio

Desactiven el entorno virtual:

```bash
deactivate
```

Detengan y eliminen los contenedores:

```bash
docker compose down
```

Como no configuramos volúmenes, las lecturas guardadas en PostgreSQL y las métricas de Prometheus **se perderán**. Sus resultados quedan a salvo en la carpeta `resultados/` y en su repositorio.

Para liberar espacio en disco al terminar el curso:

```bash
docker image rm smartcity-api:lab4
```

---

## 15. Cierre del curso

Con este laboratorio cerramos el curso.

En pocas semanas pasaron de levantar un contenedor a diseñar una arquitectura con Kafka, RabbitMQ, Redis Streams, un balanceador de carga y un sistema de monitoreo. Y hoy dieron el paso que separa a quien arma sistemas de quien los entiende: **medir antes de afirmar**.

Es muy probable que terminen este laboratorio con más preguntas que al empezarlo. Eso no significa que algo salió mal. Significa que ya entienden lo suficiente para ver todo lo que falta, y ese es el punto de partida de cualquier ingeniero serio.

La tabla de la sección 13 puede parecer abrumadora. No se preocupen por ella ahora. Nadie domina todos esos temas, ni siquiera quienes los enseñan. Las herramientas que usamos en este curso cambiarán, y algunas serán reemplazadas antes de que ustedes se gradúen. Lo que no cambia es la forma de pensar:

- Medir antes de afirmar.
- Diseñar sabiendo que algo va a fallar.
- Explicar cada decisión con evidencia.
- Tener la honestidad de decir "no lo sé, pero sé cómo averiguarlo".

El título universitario no es el final del aprendizaje. Es el momento en que nadie les volverá a entregar un laboratorio con instrucciones, y tendrán que diseñar sus propios experimentos. Este curso intentó prepararlos para eso.

> Un buen ingeniero no es el que sabe todas las respuestas, sino el que sabe hacer las preguntas correctas y tiene la disciplina de buscar la evidencia.

Gracias por su trabajo y su esfuerzo durante el curso. Sigan midiendo, sigan preguntando y, sobre todo, sigan aprendiendo.

*— Su catedrático*

---

## Referencias

- Prometheus, histogramas y resúmenes: [prometheus.io/docs/practices/histograms](https://prometheus.io/docs/practices/histograms/)
- Prometheus, consultas PromQL: [prometheus.io/docs/prometheus/latest/querying/basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- Grafana, documentación: [grafana.com/docs/grafana/latest](https://grafana.com/docs/grafana/latest/)
- k6, documentación: [grafana.com/docs/k6/latest](https://grafana.com/docs/k6/latest/)
- Traefik, proveedor Docker y health checks: [doc.traefik.io/traefik](https://doc.traefik.io/traefik/)
- Google SRE, libros gratuitos: [sre.google/books](https://sre.google/books/)
- FastAPI: [fastapi.tiangolo.com](https://fastapi.tiangolo.com/)
