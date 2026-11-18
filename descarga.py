"""Descarga de Yahoo los cierres del S&P 500 y de los tres fondos, y recalcula datos/estado.json.

Si un valor falla, se conserva su última copia buena y el programa termina con error
(la tarea de GitHub sale en rojo), pero el estado se recalcula con lo que haya.
"""
import os
import sys
import time

import pandas as pd
import yfinance as yf

from evalua import FONDOS, main as evaluar

CARPETA = 'datos'
TICKERS = {'^GSPC': '2y'} | {v['yahoo']: '2y' for v in FONDOS.values()}


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


def principal():
    os.makedirs(CARPETA, exist_ok=True)
    fallos = []
    for t, p in TICKERS.items():
        d = bajar(t, p)
        if d is None:
            fallos.append(t)
            print(f'{t}: FALLO, se conserva la copia anterior')
            continue
        d.index.name = 'Date'
        archivo = f"{CARPETA}/{t.replace('^', '')}.csv"
        if os.path.exists(archivo):
            viejo = pd.read_csv(archivo, parse_dates=['Date'])['Date']
            if len(viejo) and d.index[-1] < viejo.iloc[-1]:
                fallos.append(t)
                print(f'{t}: Yahoo devuelve datos más antiguos que la copia guardada; se conserva la copia')
                continue
        d[['Open', 'High', 'Low', 'Close', 'Volume']].to_csv(archivo)
        print(f'{t}: OK, {len(d)} sesiones, última {d.index[-1].date()}')
    evaluar(CARPETA)
    if fallos:
        sys.exit(1)


if __name__ == '__main__':
    principal()
