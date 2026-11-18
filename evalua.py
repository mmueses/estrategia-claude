"""Evalúa la estrategia con los datos de la carpeta datos/ y escribe datos/estado.json.

Reglas (desde el 18-11-2026: mitad S&P 500 y mitad Nasdaq-100, cada una con su propia señal y 3 tramos;
backtest del proyecto, fases 1 y 2 del plan de mejora y claude/otros-indices-2026-11-17.md):
- La cartera va en 6 bloques iguales (sextos): 3 tramos del S&P 500 y 3 del Nasdaq-100.
  Copia de la versión solo S&P 500: rama solo-sp500 del repositorio.
- Cada índice tiene 3 tramos:
  - Tramo A: se revisa el último día con bolsa abierta en Nueva York de cada mes.
  - Tramo B: se revisa el primer día con bolsa abierta a partir del día 10 de cada mes.
  - Tramo C: se revisa el primer día con bolsa abierta a partir del día 20 de cada mes.
- En su fecha, cada tramo compara el cierre de su índice (^GSPC o ^NDX) con la media de sus
  10 últimos cierres de revisión (el de hoy y los 9 anteriores de ese mismo tramo).
  Por encima: el fondo de ese índice. Por debajo: refugio.
- Refugio: bonos si la rentabilidad del fondo de bonos en las 12 últimas revisiones de ese tramo
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
    'SP': {'nombre': 'iShares US Index Fund (IE), clase S Acc EUR', 'isin': 'IE000N4ZYX28', 'yahoo': '0P0001XF42.F'},
    'BONOS': {'nombre': 'iShares Global Aggregate 1-5Y Bond Index, cubierto EUR', 'isin': 'IE0004ZP1ND3', 'yahoo': '0P0001W7AI.F'},
    'MONETARIO': {'nombre': 'AXA IM Euro Liquidity SRI', 'isin': 'FR0000978371', 'yahoo': '0P00000N5G.F'},
    'NASDAQ': {'nombre': 'MyInvestor Nasdaq 100 FI', 'isin': 'ES0165265002', 'yahoo': '0P0001MRGW.F'},
}
NOMBRE_DESTINO = {'SP': 'Fondo S&P 500', 'NASDAQ': 'Fondo Nasdaq-100', 'BONOS': 'Fondo de bonos', 'MONETARIO': 'Fondo monetario',
                  None: 'Refugio (comprobar a mano)'}
# Índices: clave -> (ticker de Yahoo, nombre, fondo cuando la señal es alcista)
INDICES = {'SP': ('^GSPC', 'S&P 500', 'SP'), 'NDX': ('^NDX', 'Nasdaq-100', 'NASDAQ')}
# (nombre, día de revisión: 'fin' = último día con bolsa abierta del mes; n = primer día con bolsa abierta desde el día n)
TRAMOS = [('A', 'fin'), ('B', 10), ('C', 20)]
REGLA = {'fin': 'Último día con bolsa abierta de cada mes'} | {n: f'Primer día con bolsa abierta a partir del día {n} de cada mes' for n in (10, 20)}
N_MEDIA = 10
N_MOMENTUM = 12


def leer(carpeta, ticker):
    archivo = f"{carpeta}/{ticker.replace('^', '')}.csv"
    d = pd.read_csv(archivo, parse_dates=['Date']).set_index('Date')['Close'].dropna()
    return d[~d.index.duplicated(keep='last')].sort_index()


def dias_bolsa(desde, hasta):
    dias = mcal.get_calendar('NYSE').valid_days(desde, hasta)
    return pd.DatetimeIndex(dias.tz_localize(None).normalize())


def fechas_revision(dias, dia):
    s = pd.Series(dias, index=dias)
    out = []
    for _, g in s.groupby(dias.to_period('M')):
        if dia == 'fin':
            out.append(g.iloc[-1])
        else:
            c = g[g.dt.day >= dia]
            if len(c):
                out.append(c.iloc[0])
    return pd.DatetimeIndex(out)


def valor_en(serie, fecha):
    s = serie.loc[:fecha]
    return float(s.iloc[-1]) if len(s) else None


def revisiones_tramo(dia, spx, fondos, dias_todos, fondo_bolsa='SP'):
    """Todas las revisiones hechas del tramo, con su tendencia, destino y día de la orden."""
    ultimo = spx.index[-1]
    revisiones = fechas_revision(dias_todos, dia)
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
            destino = fondo_bolsa
        if i >= N_MOMENTUM and fondos:
            f0 = hechas[i - N_MOMENTUM]
            b1, b0 = valor_en(fondos['BONOS'], f), valor_en(fondos['BONOS'], f0)
            m1, m0 = valor_en(fondos['MONETARIO'], f), valor_en(fondos['MONETARIO'], f0)
            if None not in (b1, b0, m1, m0):
                rb, rm = b1 / b0 - 1, m1 / m0 - 1
        if tendencia == 'Bajista' and rb is not None:
            destino = 'BONOS' if rb > rm else 'MONETARIO'
        siguientes = dias_todos[dias_todos > f]
        filas.append(dict(fecha=f.strftime('%Y-%m-%d'), cierre=round(c, 2),
                          media=None if pd.isna(m) else round(float(m), 2),
                          distancia_pct=None if pd.isna(m) else round((c / m - 1) * 100, 2),
                          tendencia=tendencia, destino=destino,
                          bonos_12m_pct=None if rb is None else round(rb * 100, 2),
                          monetario_12m_pct=None if rm is None else round(rm * 100, 2),
                          fecha_orden=siguientes[0].strftime('%Y-%m-%d') if len(siguientes) else None))
    return hechas, cierres, revisiones, filas


def evaluar_tramo(nombre, dia, spx, fondos, dias_todos, indice='SP'):
    """spx: cierres del índice de este tramo (S&P 500 o Nasdaq-100)."""
    ticker, nombre_indice, fondo_bolsa = INDICES[indice]
    ultimo = spx.index[-1]
    hechas, cierres, revisiones, filas = revisiones_tramo(dia, spx, fondos, dias_todos, fondo_bolsa)
    actual, anterior = filas[-1], filas[-2]
    cambio = actual['destino'] != anterior['destino']
    # Si hoy fuera revisión: el último cierre frente a la media con los 9 últimos de este tramo
    ult9 = list(cierres.iloc[-9:]) if hechas[-1] != ultimo else list(cierres.iloc[-10:-1])
    media_hoy = (sum(ult9) + float(spx.iloc[-1])) / N_MEDIA
    futuras = revisiones[revisiones > ultimo]
    return dict(
        tramo=nombre,
        indice=indice,
        indice_nombre=nombre_indice,
        nombre=f"{'S&P' if indice == 'SP' else 'Nasdaq'} {nombre}",
        regla=REGLA[dia],
        ultima_revision=actual,
        revision_anterior=anterior,
        destino=actual['destino'],
        destino_texto=NOMBRE_DESTINO[actual['destino']],
        cambio=bool(cambio),
        fecha_orden=actual['fecha_orden'],
        revision_hoy=hechas[-1] == ultimo,
        proxima_revision=futuras[0].strftime('%Y-%m-%d') if len(futuras) else None,
        si_hoy_fuera_revision=dict(cierre=round(float(spx.iloc[-1]), 2), media=round(media_hoy, 2),
                                   distancia_pct=round((float(spx.iloc[-1]) / media_hoy - 1) * 100, 2)),
        historial=filas[-13:][::-1],
        # Para la comparación con el S&P desde la fecha de inicio: cada orden de cambio de fondo
        ordenes=[dict(fecha_orden=f['fecha_orden'], destino=f['destino'] or 'MONETARIO', fecha=f['fecha'])
                 for f in filas if f['fecha'] >= '2025-06-01'],
    )


def main(carpeta='datos'):
    idx = {k: leer(carpeta, v[0]) for k, v in INDICES.items()}
    spx = idx['SP']
    fondos = {k: leer(carpeta, v['yahoo']) for k, v in FONDOS.items()}
    hoy = pd.Timestamp.now(tz='UTC').tz_localize(None).normalize()
    dias_todos = dias_bolsa(min(s.index[0] for s in idx.values()), hoy + pd.Timedelta(days=70))
    tramos = [evaluar_tramo(n, d, idx[k], fondos, dias_todos, k) for k in INDICES for n, d in TRAMOS]
    # Valores liquidativos de los tres fondos (para comparar con el S&P desde la fecha de inicio)
    vl = pd.DataFrame(fondos).sort_index().ffill().dropna()
    estado = dict(
        generado=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
        ultimo_cierre=dict(fecha=spx.index[-1].strftime('%Y-%m-%d'), valor=round(float(spx.iloc[-1]), 2)),
        ultimos_cierres={k: dict(nombre=INDICES[k][1], fecha=s.index[-1].strftime('%Y-%m-%d'), valor=round(float(s.iloc[-1]), 2))
                         for k, s in idx.items()},
        tramos=tramos,
        fondos=[dict(clave=k, **v, ultimo_valor=round(float(fondos[k].iloc[-1]), 4),
                     fecha=fondos[k].index[-1].strftime('%Y-%m-%d')) for k, v in FONDOS.items()],
        valores_liquidativos=dict(fechas=[d.strftime('%Y-%m-%d') for d in vl.index],
                                  **{k: [round(float(x), 5) for x in vl[k]] for k in FONDOS}),
    )
    with open(f'{carpeta}/estado.json', 'w', encoding='utf-8') as fh:
        json.dump(estado, fh, ensure_ascii=False, indent=1)
    for t in tramos:
        print(f"{t['nombre']}: {t['destino_texto']} | revisión {t['ultima_revision']['fecha']} "
              f"cierre {t['ultima_revision']['cierre']} media {t['ultima_revision']['media']} | cambio: {t['cambio']}")
    return estado


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'datos')
