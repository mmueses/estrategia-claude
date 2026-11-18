"""Series diarias de rentabilidad en EUR para un inversor español (motor oficial del proyecto).

Origen: claude/codigo-backtest.md, con los cambios de la fase 1 (refugio real BONOS_C, decisión en euros),
de la fase 3 (solo días con cierre del ^GSPC: antes se colaban festivos de EE. UU.).

Entradas (carpeta de datos, ver descarga_datos.py):
  px2.csv     cierres ajustados de Yahoo (^GSPC, ^IRX, VFINX, VGTSX, VEURX, VEIEX, VBMFX, VBISX)
  fx.csv      tipos de cambio diarios (github.com/datasets/exchange-rates, origen FRED); 'Euro' = EUR por USD
  eur3m.csv   Euríbor 3 meses mensual (github.com/datasets/euribor, origen EMMI)

Supuestos:
  - S&P 500 en EUR = rentabilidad total de VFINX en USD pasada a EUR, menos DRAG_SP (retención del 15 %
    sobre dividendos en un fondo irlandés + diferencia de comisiones).
  - Monetario EUR = Euríbor 3m - SPREAD_CASH.
  - BONOS_C (refugio real, fase 1) = bonos EE. UU. 1-5 años (VBISX) cubiertos a EUR, menos 0,10 % de gastos.
  - BONOS (original) = bonos agregados EE. UU. (VBMFX) cubiertos a EUR.
  - LEV2 = 2x el S&P en USD - financiación - costes, a EUR (solo para estrategias descartadas).
"""
import pandas as pd

DRAG_SP = 0.0020
DRAG_INTL = 0.0030
SPREAD_CASH = 0.0020
TER_LEV = 0.0180
TER_BONOS_C = 0.0010
BD = 252
FIN = '2026-11-13'   # último día con todos los datos en las cifras oficiales


def load(ddir, fin=FIN):
    px = pd.read_csv(f'{ddir}/px2.csv', index_col=0, parse_dates=True)
    px = px[px.index.dayofweek < 5]
    px = px[px['^GSPC'].notna()]                       # fase 3: solo días con cierre del S&P 500
    fx = pd.read_csv(f'{ddir}/fx.csv', parse_dates=['Date'])
    eurusd = fx[fx.Country == 'Euro'].set_index('Date')['Exchange rate'].rename('EURperUSD')
    e3 = pd.read_csv(f'{ddir}/eur3m.csv', parse_dates=['date']).set_index('date')['rate']

    idx = px.index[(px.index >= '1998-01-01')]
    px = px.reindex(idx).ffill()
    eurusd = eurusd.reindex(eurusd.index.union(idx)).ffill().reindex(idx)
    e3m = e3.groupby(e3.index.to_period('M')).first()
    e3d = pd.Series(e3m.reindex(idx.to_period('M')).values, index=idx).ffill()

    usd_rf = (px['^IRX'] / 100).shift(1)
    eur_rf = (e3d / 100).shift(1)

    fxr = eurusd.pct_change()
    r = pd.DataFrame(index=idx)
    usd = px[['VFINX', 'VGTSX', 'VEURX', 'VEIEX', 'VBMFX', 'VBISX']].pct_change()

    def to_eur(rusd):
        return (1 + rusd) * (1 + fxr) - 1

    r['SP'] = to_eur(usd['VFINX']) - DRAG_SP / BD
    r['EXUS'] = to_eur(usd['VGTSX']) - DRAG_INTL / BD
    r['EUROPA'] = to_eur(usd['VEURX']) - DRAG_INTL / BD
    r['EMERG'] = to_eur(usd['VEIEX']) - DRAG_INTL / BD
    r['CASH'] = (eur_rf - SPREAD_CASH) / BD
    r['BONOS'] = usd['VBMFX'] + (eur_rf - usd_rf) / BD
    r['BONOS_C'] = usd['VBISX'] + (eur_rf - usd_rf) / BD - TER_BONOS_C / BD
    r['LEV2'] = to_eur(2 * usd['VFINX'] - usd_rf / BD - TER_LEV / BD)
    sig = pd.DataFrame({'GSPC': px['^GSPC']})
    tr_usd = (1 + usd.fillna(0)).cumprod()
    for c, n in [('VFINX', 'SP'), ('VGTSX', 'EXUS'), ('VEURX', 'EUROPA'), ('VEIEX', 'EMERG'), ('VBMFX', 'BONOS')]:
        sig['TR_' + n] = tr_usd[c]
    sig['TR_CASH'] = (1 + (usd_rf.fillna(0) / BD)).cumprod()
    sig['TR_BONOS_C_EUR'] = (1 + r['BONOS_C'].fillna(0)).cumprod()
    sig['TR_CASH_EUR'] = (1 + r['CASH'].fillna(0)).cumprod()
    r = r.loc['1999-01-05':fin]
    return r, sig, eurusd
