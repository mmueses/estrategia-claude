"""Cifras oficiales de la versión elegida: solo S&P 500, 3 tramos (fin de mes, día 10, día 20).

Uso: python3 oficial.py carpeta_datos
Esperado (fase 3, 17-11-2026, 1999-01 a 13-11-2026, 10.000 €): estrategia 9,0 % neto y -22,5 %;
S&P comprar y mantener 7,6 % y -64,7 %; según fechas (8 calendarios) 8,4-9,0 %, típico 8,8 % y -31 %.
"""
import sys

import numpy as np
import pandas as pd
import pandas_market_calendars as mcal

from data import load, FIN
from estrategias import buy_hold, dia_n, fin_de_mes, media_movil_refugio_dinamico
from sim import metricas, simular


def meses_completos(idx):
    """Quita el último mes si aún no ha terminado (su último día con bolsa abierta es posterior al último dato)."""
    ultimo = idx[-1]
    sig = mcal.get_calendar('NYSE').valid_days(ultimo + pd.Timedelta(days=1), ultimo + pd.Timedelta(days=10))
    if len(sig) and sig[0].tz_localize(None).to_period('M') == ultimo.to_period('M'):
        return idx[idx < ultimo.to_period('M').start_time]
    return idx


def tramos(sig, idx, desfase=0):
    # El tramo A solo cuenta meses terminados: así, al cambiar FIN en data.py no hay que tocar nada más
    dA = fin_de_mes(meses_completos(idx), desfase)
    # Como final.py del motor original: fin de mes k días hábiles antes; días 10 y 20, k días naturales después
    return [dA, dia_n(idx, 10 + desfase), dia_n(idx, 20 + desfase)]


def estrategia(sig, fechas):
    return [(1 / 3, 'fondo', media_movil_refugio_dinamico(sig, d)) for d in fechas]


def main(ddir):
    R, SIG, _ = load(ddir)
    idx = SIG.index[SIG.index <= FIN]
    f0 = tramos(SIG, idx)
    filas = {}
    for nombre, sl in [('S&P 500 comprar y mantener', [(1, 'fondo', buy_hold(SIG, f0[0]))]),
                       ('Estrategia 3 tramos', estrategia(SIG, f0))]:
        v, info = simular(R, sl, capital=10000, inicio='1999-01-05')
        filas[nombre] = metricas(v, info)
    t = pd.DataFrame(filas).T
    print(t[['cagr', 'cagr_neto', 'maxdd', 'peor_anio', 'max_bajo_agua_anios', 'ops_anio']].round(4).to_string())
    cal = []
    for k in range(8):
        v, info = simular(R, estrategia(SIG, tramos(SIG, idx, k)), capital=10000, inicio='1999-01-05')
        m = metricas(v, info)
        cal.append((m['cagr_neto'], m['maxdd']))
    cal = np.array(cal)
    print('8 calendarios: rentab. neta %.1f-%.1f %% (mediana %.1f) | peor caída %.1f a %.1f %% (mediana %.1f)' % (
        cal[:, 0].min() * 100, cal[:, 0].max() * 100, np.median(cal[:, 0]) * 100,
        cal[:, 1].max() * 100, cal[:, 1].min() * 100, np.median(cal[:, 1]) * 100))
    return t


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'datos_bt')
