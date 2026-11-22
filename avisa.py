"""Avisos al móvil con ntfy (https://ntfy.sh) a partir de datos/estado.json.

Avisa de:
- El resultado de cada revisión, en cuanto la app tiene el cierre de ese día:
  "TRASPASO" (prioridad alta) o "sin cambios".
- La víspera de una revisión, si ese tramo está a menos de un 1 % de su media.
- Si los datos llevan más de 4 días sin actualizarse.

Cada aviso se envía una sola vez: los ya enviados se guardan en datos/avisos.json.
La clave del aviso de una revisión lleva el destino: si el resultado de una revisión ya avisada
cambia (por ejemplo, Yahoo corrige el cierre), sale un aviso nuevo «CORRECCIÓN» con prioridad máxima.
Si un aviso no se puede enviar, se reintenta en la siguiente ejecución y la tarea de GitHub sale en rojo.
El tema de ntfy va en el secreto NTFY_TOPIC del repositorio; sin él no se envía nada.

Uso: python3 avisa.py [carpeta_datos] [--prueba]
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

import pandas as pd
import pandas_market_calendars as mcal

APP = 'https://mmueses.github.io/estrategia-claude/'
UMBRAL_CERCA = 1.0   # % de distancia a la media para avisar la víspera
DIAS_VIEJO = 4       # días naturales sin datos nuevos para avisar


def fecha(s):
    return datetime.strptime(s, '%Y-%m-%d').strftime('%d/%m/%Y')


def num(x):
    return f"{x:,.2f}".replace(',', ' ').replace('.', ',').replace(' ', '.')


def pct(x):
    return f"{x:+.2f} %".replace('.', ',')


AVISO_LEGAL = ('\n\nNota personal de un proyecto experimental. No es recomendación ni asesoramiento de inversión; '
               'invertir en bolsa puede hacer perder dinero. Sin responsabilidad por pérdidas.')


def enviar(topic, titulo, mensaje, prioridad=3, etiquetas=()):
    mensaje = mensaje + AVISO_LEGAL
    if not topic:
        print(f'[sin NTFY_TOPIC, no se envía] {titulo}: {mensaje}')
        return True
    datos = json.dumps(dict(topic=topic, title=titulo, message=mensaje, priority=prioridad,
                            tags=list(etiquetas), click=APP)).encode()
    req = urllib.request.Request('https://ntfy.sh/', data=datos, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        print('Enviado:', titulo, r.status)
        return 200 <= r.status < 300


def siguiente_dia_bolsa(dia):
    dias = mcal.get_calendar('NYSE').valid_days(dia + pd.Timedelta(days=1), dia + pd.Timedelta(days=10))
    return dias[0].tz_localize(None).normalize()


def avisos(estado, hoy):
    """Lista de (clave, título, mensaje, prioridad, etiquetas)."""
    out = []
    ultimo = pd.Timestamp(estado['ultimo_cierre']['fecha'])
    if (hoy - ultimo).days > DIAS_VIEJO:
        out.append((f"viejo-{estado['ultimo_cierre']['fecha']}", 'La app no se actualiza',
                    f"El último cierre del S&P 500 es del {fecha(estado['ultimo_cierre']['fecha'])}. "
                    'Si hoy hay revisión, compruébala a mano (reglas de la casa, "Si algo falla").', 4, ['warning']))
        return out
    manana = siguiente_dia_bolsa(ultimo)
    for t in estado['tramos']:
        r = t['ultima_revision']
        if t['revision_hoy']:
            clave = f"rev-{t['tramo']}-{r['fecha']}-{t['destino'] or 'REFUGIO'}"
            nota = (f" (Aplazada: el {fecha(r['aplazada_desde'])} no hubo cierre del índice: comprueba en ProRealTime que ese día no hubo sesión.)"
                    if r.get('aplazada_desde') else '')
            if t['cambio']:
                out.append((clave, f"TRASPASO tramo {t['tramo']}",
                            f"Revisión del {fecha(r['fecha'])}: cierre {num(r['cierre'])} frente a media {num(r['media'])} "
                            f"({pct(r['distancia_pct'])}). Ordena el {fecha(t['fecha_orden'])} en MyInvestor el traspaso "
                            f"de este tercio a: {t['destino_texto']}.{nota}", 5, ['rotating_light']))
            else:
                out.append((clave, f"Tramo {t['tramo']}: sin cambios",
                            f"Revisión del {fecha(r['fecha'])}: cierre {num(r['cierre'])} frente a media {num(r['media'])} "
                            f"({pct(r['distancia_pct'])}). Sigue en {t['destino_texto'].lower()}. No hay que hacer nada.{nota}",
                            4, ['white_check_mark']))
        prox = t['proxima_revision']
        d = t['si_hoy_fuera_revision']['distancia_pct']
        if prox and pd.Timestamp(prox) == manana and abs(d) < UMBRAL_CERCA:
            out.append((f"cerca-{t['tramo']}-{prox}", f"Mañana se revisa el tramo {t['tramo']}",
                        f"Con el cierre de hoy estaría a {pct(d)} de su media: puede haber traspaso. "
                        f"Mira la app mañana {fecha(prox)} por la noche.", 4, ['eyes']))
    return out


def main(carpeta='datos', prueba=False):
    topic = os.environ.get('NTFY_TOPIC', '').strip()
    if prueba:
        enviar(topic, 'Prueba de avisos', 'Si ves esto, los avisos de la estrategia funcionan.', 4, ['tada'])
        return
    estado = json.load(open(f'{carpeta}/estado.json', encoding='utf-8'))
    ruta = f'{carpeta}/avisos.json'
    enviados = json.load(open(ruta, encoding='utf-8')) if os.path.exists(ruta) else {}
    hoy = pd.Timestamp(datetime.now(timezone.utc).date())
    fallos = []
    for clave, titulo, mensaje, prio, tags in avisos(estado, hoy):
        if clave in enviados:
            continue
        if clave.startswith('rev-'):
            # Misma revisión ya avisada con otro resultado: corrección
            base = clave.rsplit('-', 1)[0] + '-'
            if any(k.startswith(base) for k in enviados):
                titulo, prio, tags = f'CORRECCIÓN: {titulo}', 5, ['warning']
                mensaje = 'El resultado de esta revisión ha cambiado; olvida el aviso anterior. ' + mensaje
        try:
            ok = enviar(topic, titulo, mensaje, prio, tags)
        except Exception as e:  # un fallo de ntfy no debe parar la actualización de datos
            print('No se pudo enviar', clave, e)
            ok = False
        if ok and topic:
            enviados[clave] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        elif not ok:
            fallos.append(clave)
    # Solo se guardan los últimos 200 avisos
    enviados = dict(sorted(enviados.items(), key=lambda kv: kv[1])[-200:])
    with open(ruta, 'w', encoding='utf-8') as fh:
        json.dump(enviados, fh, ensure_ascii=False, indent=1)
    # Si algún aviso no salió, la tarea de GitHub se marca en rojo (se reintenta en la siguiente ejecución)
    return fallos


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if main(args[0] if args else 'datos', '--prueba' in sys.argv):
        sys.exit(1)
