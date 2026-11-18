"""Compara las señales de la app con las del backtest en todas las revisiones desde 1999.

Necesita el histórico largo del S&P 500 (no está en datos/, que solo guarda 2 años):
    python3 pruebas/comprueba_senales.py ruta/GSPC_largo.csv
El CSV debe tener columnas Date y Close (como los de datos/). Para bajarlo:
    python3 -c "import yfinance as yf; yf.download('^GSPC', start='1985-01-01', auto_adjust=False,
                multi_level_index=False).to_csv('GSPC_largo.csv')"

Backtest: fechas con los días que tienen cierre en los datos (último del mes; primero desde el 10;
primero desde el 20), media de 10 cierres de revisión, alcista si el cierre está por encima.
Con un segundo argumento (fecha AAAA-MM-DD) se quita ese día de los datos para ver que la
revisión no desaparece.
"""
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import evalua  # noqa: E402


def backtest(spx, dia, dias_cal):
    idx = spx.index
    s = pd.Series(idx, index=idx)
    out = []
    for mes, g in s.groupby(idx.to_period('M')):
        if dia == 'fin':
            # El mes en curso aún no tiene revisión de fin de mes
            if mes == idx[-1].to_period('M') and dias_cal[dias_cal.to_period('M') == mes][-1] > idx[-1]:
                continue
            out.append(g.iloc[-1])
        else:
            c = g[g.dt.day >= dia]
            if len(c):
                out.append(c.iloc[0])
    f = pd.DatetimeIndex(out)
    c = spx.loc[f]
    m = c.rolling(evalua.N_MEDIA).mean()
    return pd.Series(['Alcista' if a > b else 'Bajista' for a, b in zip(c, m)], index=f)[m.notna().values]


def main(ruta, quitar=None):
    spx = pd.read_csv(ruta, parse_dates=['Date']).set_index('Date')['Close'].dropna()
    spx = spx[~spx.index.duplicated(keep='last')].sort_index()
    spx = spx[spx.index >= '1997-06-01']
    if quitar:
        spx = spx.drop(pd.Timestamp(quitar))
    dias = evalua.dias_bolsa(spx.index[0], spx.index[-1] + pd.Timedelta(days=70))
    huecos = dias[(dias <= spx.index[-1]) & ~dias.isin(spx.index)]
    print(f'Días del calendario NYSE sin cierre en los datos: {len(huecos)} {list(huecos.strftime("%Y-%m-%d"))[:10]}')
    total = 0
    for nombre, dia in evalua.TRAMOS:
        filas = evalua.revisiones_tramo(dia, spx, None, dias)[3]
        app = pd.Series({pd.Timestamp(f['fecha']): f['tendencia'] for f in filas if f['tendencia']})
        app = app[app.index >= '1999-01-01']
        bt = backtest(spx, dia, dias)
        bt = bt[bt.index >= '1999-01-01']
        comunes = app.index.intersection(bt.index)
        dif = (app.loc[comunes] != bt.loc[comunes]).sum()
        solo_app = app.index.difference(bt.index)
        solo_bt = bt.index.difference(app.index)
        aplazadas = [f for f in filas if f['aplazada_desde']]
        print(f'Tramo {nombre}: app {len(app)} revisiones, backtest {len(bt)}, comunes {len(comunes)}, '
              f'señales distintas {dif}, solo en la app {len(solo_app)}, solo en el backtest {len(solo_bt)}, '
              f'aplazadas {[(f["aplazada_desde"], f["fecha"]) for f in aplazadas]}')
        total += dif
    return total


if __name__ == '__main__':
    sys.exit(1 if main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None) else 0)
