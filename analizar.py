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
