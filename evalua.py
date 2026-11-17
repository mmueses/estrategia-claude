"""Evalúa la estrategia con los datos de la carpeta datos/ y escribe datos/estado.json.

Reglas (las del backtest de noviembre de 2026):
- Mitad A: se revisa el último día con bolsa abierta en Nueva York de cada mes.
- Mitad B: se revisa el primer día con bolsa abierta a partir del día 15 de cada mes.
- En su fecha, cada mitad compara el cierre del índice S&P 500 (^GSPC) con la media de sus
  10 últimos cierres de revisión (el de hoy y los 9 anteriores de esa misma mitad).
  Por encima: fondo S&P 500. Por debajo: refugio.
- Refugio: bonos si la rentabilidad del fondo de bonos en las 12 últimas revisiones de esa mitad
  supera a la del monetario; si no, monetario.
- La orden de traspaso se da el día siguiente a la revisión.

Uso: python3 evalua.py [carpeta_datos]
"""
import json
import sys
from datetime import datetime, timezone

import pandas as pd
import pandas_market_calendars as mcal

FONDOS = {
    'SP': {'nombre': 'iShares US Equity Index Fund, clase S (EUR)', 'isin': 'IE000N4ZYX28', 'yahoo': '0P0001XF42.F'},
    'BONOS': {'nombre': 'iShares Global Aggregate 1-5Y Bond Index, cubierto EUR', 'isin': 'IE0004ZP1ND3', 'yahoo': '0P0001W7AI.F'},
    'MONETARIO': {'nombre': 'AXA IM Euro Liquidity SRI', 'isin': 'FR0000978371', 'yahoo': '0P00000N5G.F'},
}
NOMBRE_DESTINO = {'SP': 'Fondo S&P 500', 'BONOS': 'Fondo de bonos', 'MONETARIO': 'Fondo monetario', None: 'Refugio (comprobar a mano)'}
N_MEDIA = 10
N_MOMENTUM = 12


def leer(carpeta, ticker):
    archivo = f"{carpeta}/{ticker.replace('^', '')}.csv"
    d = pd.read_csv(archivo, parse_dates=['Date']).set_index('Date')['Close'].dropna()
    return d[~d.index.duplicated(keep='last')].sort_index()


def dias_bolsa(desde, hasta):
    dias = mcal.get_calendar('NYSE').valid_days(desde, hasta)
    return pd.DatetimeIndex(dias.tz_localize(None).normalize())


def fechas_revision(dias, mitad):
    s = pd.Series(dias, index=dias)
    out = []
    for _, g in s.groupby(dias.to_period('M')):
        if mitad == 'A':
            out.append(g.iloc[-1])
        else:
            c = g[g.dt.day >= 15]
            if len(c):
                out.append(c.iloc[0])
    return pd.DatetimeIndex(out)


def valor_en(serie, fecha):
    s = serie.loc[:fecha]
    return float(s.iloc[-1]) if len(s) else None


def evaluar_mitad(mitad, spx, fondos, dias_todos):
    ultimo = spx.index[-1]
    revisiones = fechas_revision(dias_todos, mitad)
    hechas = revisiones[revisiones <= ultimo]
    # Solo cuentan las revisiones con cierre de ese mismo día
    hechas = pd.DatetimeIndex([f for f in hechas if f in spx.index])
    cierres = spx.loc[hechas]
    media = cierres.rolling(N_MEDIA).mean()
    filas = []
    for i, f in enumerate(hechas):
        c, m = float(cierres.iloc[i]), media.iloc[i]
        tendencia = None if pd.isna(m) else ('Alcista' if c > m else 'Bajista')
        destino, rb, rm = None, None, None
        if tendencia == 'Alcista':
            destino = 'SP'
        if i >= N_MOMENTUM:
            f0 = hechas[i - N_MOMENTUM]
            b1, b0 = valor_en(fondos['BONOS'], f), valor_en(fondos['BONOS'], f0)
            m1, m0 = valor_en(fondos['MONETARIO'], f), valor_en(fondos['MONETARIO'], f0)
            if None not in (b1, b0, m1, m0):
                rb, rm = b1 / b0 - 1, m1 / m0 - 1
        if tendencia == 'Bajista' and rb is not None:
            destino = 'BONOS' if rb > rm else 'MONETARIO'
        filas.append(dict(fecha=f.strftime('%Y-%m-%d'), cierre=round(c, 2),
                          media=None if pd.isna(m) else round(float(m), 2),
                          distancia_pct=None if pd.isna(m) else round((c / m - 1) * 100, 2),
                          tendencia=tendencia, destino=destino,
                          bonos_12m_pct=None if rb is None else round(rb * 100, 2),
                          monetario_12m_pct=None if rm is None else round(rm * 100, 2)))
    actual, anterior = filas[-1], filas[-2]
    cambio = actual['destino'] != anterior['destino']
    # Si hoy fuera revisión: el último cierre frente a la media con los 9 últimos de esta mitad
    ult9 = list(cierres.iloc[-9:]) if hechas[-1] != ultimo else list(cierres.iloc[-10:-1])
    media_hoy = (sum(ult9) + float(spx.iloc[-1])) / N_MEDIA
    futuras = revisiones[revisiones > ultimo]
    return dict(
        mitad=mitad,
        regla='Último día con bolsa abierta de cada mes' if mitad == 'A' else 'Primer día con bolsa abierta a partir del 15 de cada mes',
        ultima_revision=actual,
        revision_anterior=anterior,
        destino=actual['destino'],
        destino_texto=NOMBRE_DESTINO[actual['destino']],
        cambio=bool(cambio),
        revision_hoy=hechas[-1] == ultimo,
        proxima_revision=futuras[0].strftime('%Y-%m-%d') if len(futuras) else None,
        si_hoy_fuera_revision=dict(cierre=round(float(spx.iloc[-1]), 2), media=round(media_hoy, 2),
                                   distancia_pct=round((float(spx.iloc[-1]) / media_hoy - 1) * 100, 2)),
        historial=filas[-13:][::-1],
    )


def main(carpeta='datos'):
    spx = leer(carpeta, '^GSPC')
    fondos = {k: leer(carpeta, v['yahoo']) for k, v in FONDOS.items()}
    hoy = pd.Timestamp.now(tz='UTC').tz_localize(None).normalize()
    dias_todos = dias_bolsa(spx.index[0], hoy + pd.Timedelta(days=70))
    estado = dict(
        generado=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        ultimo_cierre=dict(fecha=spx.index[-1].strftime('%Y-%m-%d'), valor=round(float(spx.iloc[-1]), 2)),
        mitades=[evaluar_mitad('A', spx, fondos, dias_todos), evaluar_mitad('B', spx, fondos, dias_todos)],
        fondos=[dict(clave=k, **v, ultimo_valor=round(float(fondos[k].iloc[-1]), 4),
                     fecha=fondos[k].index[-1].strftime('%Y-%m-%d')) for k, v in FONDOS.items()],
    )
    with open(f'{carpeta}/estado.json', 'w', encoding='utf-8') as fh:
        json.dump(estado, fh, ensure_ascii=False, indent=1)
    for m in estado['mitades']:
        print(f"Mitad {m['mitad']}: {m['destino_texto']} | revisión {m['ultima_revision']['fecha']} "
              f"cierre {m['ultima_revision']['cierre']} media {m['ultima_revision']['media']} | cambio: {m['cambio']}")
    return estado


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'datos')
