"""Descarga de Yahoo los cierres del S&P 500 y de los tres fondos, y recalcula datos/estado.json.

Si un valor falla, se conserva su última copia buena y el programa termina con error
(la tarea de GitHub sale en rojo), pero el estado se recalcula con lo que haya.

Si la tarea corre con la bolsa de Nueva York abierta, Yahoo da el precio del momento como si
fuera el cierre de hoy. Esa fila se descarta hasta 15 minutos después del cierre oficial del
día (calendario NYSE, incluidos los días de cierre anticipado).
"""
import os
import sys
import time

import pandas as pd
import pandas_market_calendars as mcal
import yfinance as yf

from evalua import FONDOS, main as evaluar

CARPETA = 'datos'
TICKERS = {'^GSPC': '2y'} | {v['yahoo']: '2y' for v in FONDOS.values()}


MARGEN_CIERRE = pd.Timedelta(minutes=15)


def quitar_sesion_abierta(d, ahora=None):
    """Quita la última fila si es de hoy y Nueva York aún no ha cerrado (cierre del día + 15 min)."""
    if not len(d):
        return d
    ahora = pd.Timestamp.now(tz='UTC') if ahora is None else pd.Timestamp(ahora).tz_convert('UTC')
    hoy_ny = ahora.tz_convert('America/New_York').tz_localize(None).normalize()
    if pd.Timestamp(d.index[-1]).tz_localize(None).normalize() != hoy_ny:
        return d
    sesion = mcal.get_calendar('NYSE').schedule(hoy_ny, hoy_ny)
    if len(sesion) and ahora < sesion['market_close'].iloc[0] + MARGEN_CIERRE:
        print(f'Última fila del {hoy_ny.date()} descartada: Nueva York aún no ha cerrado')
        return d.iloc[:-1]
    return d


def bajar(ticker, periodo):
    for intento in range(3):
        try:
            d = yf.download(ticker, period=periodo, progress=False, auto_adjust=False, multi_level_index=False)
            if len(d) > 100:
                return d
        except Exception as e:  # noqa: BLE001
            print(f'{ticker}: intento {intento + 1} falló ({e})')
        time.sleep(10)
    return None


def principal(carpeta=CARPETA, ahora=None, bajar=bajar):
    os.makedirs(carpeta, exist_ok=True)
    fallos = []
    for t, p in TICKERS.items():
        d = bajar(t, p)
        if d is not None and t.startswith('^'):
            d = quitar_sesion_abierta(d, ahora)
        if d is None:
            fallos.append(t)
            print(f'{t}: FALLO, se conserva la copia anterior')
            continue
        d.index.name = 'Date'
        archivo = f"{carpeta}/{t.replace('^', '')}.csv"
        if os.path.exists(archivo):
            viejo = pd.read_csv(archivo, parse_dates=['Date'])['Date']
            if len(viejo) and d.index[-1] < viejo.iloc[-1]:
                fallos.append(t)
                print(f'{t}: Yahoo devuelve datos más antiguos que la copia guardada; se conserva la copia')
                continue
        d[['Open', 'High', 'Low', 'Close', 'Volume']].to_csv(archivo)
        print(f'{t}: OK, {len(d)} sesiones, última {d.index[-1].date()}')
    evaluar(carpeta)
    if fallos:
        sys.exit(1)


if __name__ == '__main__':
    principal()
