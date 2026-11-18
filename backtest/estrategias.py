"""Señales. Cada función devuelve una Series indexada por fecha de señal con {activo: peso}.

Solo se guardan las que usa la estrategia elegida (media de 10 revisiones con refugio dinámico) y el
comprar y mantener. Las descartadas (GEM, ARALP, rotación, mezclas) están en claude/codigo-backtest.md.
"""
import numpy as np
import pandas as pd


def fin_de_mes(idx, desfase=0):
    """Último día con cierre de cada mes (desfase > 0: n días antes)."""
    s = pd.Series(idx, index=idx)
    g = s.groupby(idx.to_period('M'))
    return pd.DatetimeIndex([x.iloc[-1 - desfase] if len(x) > desfase else x.iloc[-1] for _, x in g])


def dia_n(idx, n, desfase=0):
    """Primer día con cierre a partir del día n de cada mes (desfase > 0: n días hábiles después)."""
    s = pd.Series(idx, index=idx)
    out = []
    for _, g in s.groupby(idx.to_period('M')):
        c = g[g.dt.day >= n]
        if len(c) > desfase:
            out.append(c.iloc[desfase])
    return pd.DatetimeIndex(out)


def buy_hold(sig, dias, activo='SP'):
    return pd.Series([{activo: 1.0}] * len(dias), index=dias)


def _mom(sig, dias, col, L):
    tr = sig[col].loc[dias]
    return tr / tr.shift(L) - 1


def media_movil_refugio_dinamico(sig, dias, n=10, L=12, riesgo='SP', bonos='BONOS_C',
                                 tr_bonos='TR_BONOS_C_EUR', tr_cash='TR_CASH_EUR'):
    """Media de n revisiones del S&P; por debajo, bonos si baten al monetario en L revisiones (en euros)."""
    m = sig['GSPC'].loc[dias]
    sma = m.rolling(n).mean()
    mb, mc = _mom(sig, dias, tr_bonos, L), _mom(sig, dias, tr_cash, L)
    out = []
    for i in range(len(dias)):
        if np.isnan(sma.iloc[i]) or np.isnan(mb.iloc[i]):
            out.append(None)
            continue
        if m.iloc[i] > sma.iloc[i]:
            out.append({riesgo: 1.0})
        else:
            out.append({bonos: 1.0} if mb.iloc[i] > mc.iloc[i] else {'CASH': 1.0})
    return pd.Series(out, index=dias).dropna()
