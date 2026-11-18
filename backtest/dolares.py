"""Motor en dólares de la auditoría del 18-11-2026 (claude/codigo-verificacion-2026-11-18.md).

Índices sin dividendos, sin impuestos, 3 tramos, media de 10 revisiones, 5 días fuera por cambio,
0,1 % de coste por cambio, refugio en letras del Tesoro (^IRX), mezcla S&P + Nasdaq igualada cada enero.
Sirve para comparar versiones rápido; las cifras oficiales son las de oficial.py (euros, impuestos).

Uso: python3 dolares.py carpeta   (con GSPC.csv, NDX.csv e IRX.csv de Yahoo: columnas Date y Close)
Esperado (1999-01-04 a 17-11-2026, mediana de 8 calendarios): solo S&P 6,5 % y -24 %; mezcla 9,2 % y -25 %.
"""
import sys

import numpy as np
import pandas as pd

N, L, C = 10, 5, 0.001


def leer(d, t):
    s = pd.read_csv(f'{d}/{t}.csv', parse_dates=['Date']).set_index('Date')['Close'].dropna()
    return s[~s.index.duplicated(keep='last')].sort_index()


class Motor:
    def __init__(self, d):
        sp, nd, irx = leer(d, 'GSPC'), leer(d, 'NDX'), leer(d, 'IRX')
        self.idx = sp.index[sp.index >= '1997-06-01']
        self.P = {'SP': sp.reindex(self.idx).ffill(), 'ND': nd.reindex(self.idx).ffill()}
        self.rf = (irx.reindex(self.idx).ffill() / 100 / 252).shift(1).fillna(0)

    def fechas(self, dia, desf):
        idx = self.idx
        s = pd.Series(np.arange(len(idx)), index=idx)
        out = []
        for _, g in s.groupby(idx.to_period('M')):
            if dia == 'fin':
                k = g.iloc[-1]
            else:
                c = g[g.index.day >= dia]
                if not len(c):
                    continue
                k = c.iloc[0]
            out.append(min(k + desf, len(idx) - 1))
        return sorted(set(out))

    def tramo(self, a, dia, desf=0):
        p = self.P[a]
        r = p.pct_change().fillna(0).values
        ks = self.fechas(dia, desf)
        c = p.values[ks]
        sma = pd.Series(c).rolling(N).mean().values
        sig = {k: (1 if c[j] > sma[j] else 0) for j, k in enumerate(ks) if not np.isnan(sma[j])}
        ret = np.zeros(len(self.idx))
        cur, out_until, nxt, rfv = None, -1, None, self.rf.values
        for i in range(len(self.idx)):
            if nxt is not None and i == nxt[0]:
                out_until, cur, nxt = i + L - 1, ('out', nxt[1]), None
            if cur is None:
                ret[i] = 0
            elif isinstance(cur, tuple):
                ret[i] = 0
                if i == out_until:
                    cur = cur[1]
                    ret[i] -= C
            else:
                ret[i] = r[i] if cur == 1 else rfv[i]
            if i in sig:
                s = sig[i]
                if cur is None:
                    cur = s
                else:
                    actual = cur[1] if isinstance(cur, tuple) else cur
                    if s != actual:
                        nxt = (i + 2, s)
        return pd.Series(ret, index=self.idx)

    def cartera(self, activos, desf=0, ini='1999-01-04'):
        partes = {}
        for a in activos:
            v = [(1 + self.tramo(a, d, desf).loc[ini:]).cumprod() for d in ('fin', 10, 20)]
            partes[a] = sum(v) / 3
        df = pd.DataFrame(partes)
        if len(activos) == 1:
            return df.iloc[:, 0]
        r = df.pct_change().fillna(0)
        w, tot, val, yr = np.array([.5, .5]), 1.0, [], None
        for d, row in r.iterrows():
            if yr is not None and d.year != yr:
                w = np.array([.5, .5])
            yr = d.year
            g = w * (1 + row.values)
            tot *= g.sum()
            w = g / g.sum()
            val.append(tot)
        return pd.Series(val, index=df.index)


def cagr(v):
    return (v.iloc[-1] / v.iloc[0]) ** (365.25 / (v.index[-1] - v.index[0]).days) - 1


def caida(v):
    return (v / v.cummax() - 1).min()


def main(d):
    m = Motor(d)
    bh = m.P['SP'].loc['1999-01-04':]
    print('S&P comprar y mantener: %.1f %% / %.0f %%' % (cagr(bh) * 100, caida(bh) * 100))
    res = {}
    for nombre, act in [('solo S&P', ['SP']), ('mezcla S&P + Nasdaq', ['SP', 'ND'])]:
        x = np.array([(cagr(v), caida(v)) for v in (m.cartera(act, k) for k in range(8))])
        res[nombre] = x
        print('%-20s rentab. mediana %.1f %% (mín %.1f) | caída mediana %.0f %% (peor %.0f %%)' % (
            nombre, np.median(x[:, 0]) * 100, x[:, 0].min() * 100, np.median(x[:, 1]) * 100, x[:, 1].min() * 100))
    return res


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else 'datos_bt')
