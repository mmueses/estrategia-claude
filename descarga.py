"""Descarga de Yahoo los cierres del S&P 500 y de los tres fondos, y recalcula datos/estado.json.

Si un valor falla, se conserva su última copia buena y el programa termina con error
(la tarea de GitHub sale en rojo), pero el estado se recalcula con lo que haya.
"""
import os
import sys
import time

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
        d[['Open', 'High', 'Low', 'Close', 'Volume']].to_csv(f"{CARPETA}/{t.replace('^', '')}.csv")
        print(f'{t}: OK, {len(d)} sesiones, última {d.index[-1].date()}')
    evaluar(CARPETA)
    if fallos:
        sys.exit(1)


if __name__ == '__main__':
    principal()
