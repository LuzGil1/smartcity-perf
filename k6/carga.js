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
