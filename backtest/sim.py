"""Simulador realista de carteras para un inversor residente en Navarra (motor oficial).

Origen: claude/codigo-backtest.md, con el dual pricing de la fase 1 (COSTE_FONDO).

Cada estrategia es una lista de bolsillos (peso, modo, señales):
  - modo 'fondo': traspasos sin tributar hasta el reembolso final; la venta se valora al cierre de t+1
    y la compra al de t+LAG (días fuera de mercado);
  - modo 'etf': compraventa en bolsa con comisión, medio diferencial y tributación de cada venta.
Fiscalidad (base del ahorro de Navarra): fondos, todo al final; ETF, FIFO, compensación 4 años,
regla de los dos meses, cuota calculada el 1 de marzo y pagada el 30 de junio del año siguiente.
"""
from collections import defaultdict, deque

import numpy as np
import pandas as pd

# Navarra, base liquidable del ahorro 2025-2026 (art. 60 DFL 4/2008)
TRAMOS_NAVARRA = [(6000, 0.20), (10000, 0.22), (15000, 0.24), (200000, 0.26), (300000, 0.27), (np.inf, 0.28)]

LAG_FONDO = 5
COMISION_ETF = 3.0
MEDIO_SPREAD = 0.0005
# Fase 1: dual pricing de los fondos iShares clase S en cada compra y cada venta (el monetario no tiene)
COSTE_FONDO = {'SP': 0.0005, 'BONOS': 0.0005, 'BONOS_C': 0.0005}


def cuota(base, tramos=TRAMOS_NAVARRA):
    t, prev = 0.0, 0.0
    for lim, tipo in tramos:
        if base <= prev:
            break
        t += (min(base, lim) - prev) * tipo
        prev = lim
    return t


class Cuenta:
    def __init__(self, modo, capital, assets, coste_fondo):
        self.modo = modo
        self.coste_fondo = coste_fondo
        self.lotes = {a: deque() for a in assets}
        self.units = defaultdict(float)
        self.transito = []
        self.efectivo = 0.0
        self.coste_total = capital
        self.capital0 = capital
        self.realizado = defaultdict(float)
        self.perdidas_pend = {}
        self.costes = 0.0
        self.operaciones = 0

    def valor(self, P, i):
        v = self.efectivo + sum(e for _, d in self.transito for e in d.values())
        return v + sum(u * P[a][i] for a, u in self.units.items() if u)

    def vender(self, a, euros, P, i, fecha):
        if euros <= 0:
            return 0.0
        price = P[a][i]
        u_sell = min(self.units[a], euros / price)
        self.units[a] -= u_sell
        if self.modo == 'etf':
            rest, coste = u_sell, 0.0
            lots = self.lotes[a]
            while rest > 1e-12 and lots:
                u, c = lots[0]
                take = min(u, rest)
                coste += take * c
                rest -= take
                if take >= u - 1e-12:
                    lots.popleft()
                else:
                    lots[0] = (u - take, c)
            bruto = u_sell * price
            neto = bruto * (1 - MEDIO_SPREAD) - COMISION_ETF
            g = neto - coste
            self.realizado[fecha.year] += g
            if g < 0:
                self.perdidas_pend[a] = (-g, fecha, u_sell, fecha.year)
            self.costes += bruto - neto
            self.operaciones += 1
            return neto
        bruto = u_sell * price
        neto = bruto * (1 - self.coste_fondo.get(a, 0.0))
        self.costes += bruto - neto
        return neto

    def comprar(self, a, euros, P, i, fecha):
        if euros <= 0:
            return
        price = P[a][i]
        if self.modo == 'etf':
            neto = (euros - COMISION_ETF) * (1 - MEDIO_SPREAD)
            self.costes += euros - neto
            self.operaciones += 1
            u = neto / price
            coste_u = euros / u
            if a in self.perdidas_pend:
                perd, f, u_sold, yr = self.perdidas_pend[a]
                if (fecha - f).days <= 61:
                    frac = min(1.0, u / u_sold)
                    diferida = perd * frac
                    self.realizado[yr] += diferida
                    coste_u += diferida / u
                    rem = perd - diferida
                    if rem > 1e-9:
                        self.perdidas_pend[a] = (rem, f, u_sold - u, yr)
                    else:
                        del self.perdidas_pend[a]
                else:
                    del self.perdidas_pend[a]
            self.lotes[a].append((u, coste_u))
        else:
            neto = euros * (1 - self.coste_fondo.get(a, 0.0))
            self.costes += euros - neto
            u = neto / price
        self.units[a] += u

    def rebalancear(self, objetivo, P, i, fecha, idx_compra):
        tot = self.valor(P, i) - self.efectivo - sum(e for _, d in self.transito for e in d.values())
        if tot <= 0:
            return
        actual = {a: self.units[a] * P[a][i] for a in self.units if self.units[a] > 1e-12}
        ventas = {a: v - objetivo.get(a, 0) * tot for a, v in actual.items() if v - objetivo.get(a, 0) * tot > 1e-6 * tot}
        compras = {a: objetivo[a] * tot - actual.get(a, 0) for a in objetivo if objetivo[a] * tot - actual.get(a, 0) > 1e-6 * tot}
        if not ventas and not compras:
            return
        liquido = sum(self.vender(a, e, P, i, fecha) for a, e in ventas.items())
        if self.modo == 'fondo':
            self.operaciones += 1
        tot_c = sum(compras.values())
        if tot_c <= 0:
            self.efectivo += liquido
            return
        reparto = {a: liquido * e / tot_c for a, e in compras.items()}
        if self.modo == 'fondo' and idx_compra > i:
            self.transito.append((idx_compra, reparto))
        else:
            for a, e in reparto.items():
                self.comprar(a, e, P, i, fecha)

    def liquidar_transito(self, P, i, fecha):
        resto = []
        for k, d in self.transito:
            if k <= i:
                for a, e in d.items():
                    self.comprar(a, e, P, i, fecha)
            else:
                resto.append((k, d))
        self.transito = resto


def procesar_anio(yr, cuentas, arrastre, cuota_pendiente, tramos):
    g = sum(c.realizado.get(yr, 0.0) for c, _ in cuentas if c.modo == 'etf')
    arrastre = [(y, x) for y, x in arrastre if yr - y <= 4]
    if g > 0:
        nuevo = []
        for y, x in arrastre:
            usa = min(x, g)
            g -= usa
            if x - usa > 1e-9:
                nuevo.append((y, x - usa))
        arrastre = nuevo
        if g > 0:
            cuota_pendiente[yr] = cuota(g, tramos)
    elif g < 0:
        arrastre.append((yr, -g))
    return arrastre


def simular(R, senales, capital=30000.0, inicio=None, fin=None, lag=LAG_FONDO, tramos=TRAMOS_NAVARRA,
            impuestos=True, coste_fondo=COSTE_FONDO):
    """R: rentabilidades diarias en EUR. senales: lista de (peso, modo, Series de dicts por fecha de señal)."""
    R = R.loc[inicio:fin]
    fechas = R.index
    P = {a: np.concatenate([[1.0], (1 + R[a].fillna(0).values).cumprod()]) for a in R.columns}
    cuentas = [(Cuenta(modo, capital * peso, R.columns, coste_fondo), sen) for peso, modo, sen in senales]
    pendientes = []
    for c, sen in cuentas:
        prev = sen.loc[:fechas[0] - pd.Timedelta(days=1)]
        obj = prev.iloc[-1] if len(prev) else {'CASH': 1.0}
        tot_c = sum(obj.values())
        for a, w in obj.items():
            c.comprar(a, c.capital0 * w / tot_c, P, 0, fechas[0])
        c.efectivo = 0.0
        c.costes = 0.0
        c.operaciones = 0
        c.ultimo_obj = obj
    sig_map = []
    for c, sen in cuentas:
        s = sen.loc[fechas[0]:fechas[-1]]
        d = {}
        for f, obj in s.items():
            k = fechas.searchsorted(f)
            if k < len(fechas) and fechas[k] == f:
                d[k] = obj
        sig_map.append(d)

    valores = np.empty(len(fechas))
    impuestos_pagados = 0.0
    arrastre = []
    cuota_pendiente = {}
    anio_calc = anio_pago = fechas[0].year - 1
    for i, f in enumerate(fechas):
        pi = i + 1
        for (c, _), smap in zip(cuentas, sig_map):
            c.liquidar_transito(P, pi, f)
            for (k, cc, obj) in [p for p in pendientes if p[0] == i and p[1] is c]:
                c.rebalancear(obj, P, pi, f, (i + lag - 1) + 1 if c.modo == 'fondo' else pi)
        pendientes = [p for p in pendientes if p[0] != i]
        if impuestos and f.month >= 3 and anio_calc < f.year - 1:
            anio_calc = f.year - 1
            arrastre = procesar_anio(anio_calc, cuentas, arrastre, cuota_pendiente, tramos)
        if impuestos and f.month >= 7 and anio_pago < f.year - 1:
            anio_pago = f.year - 1
            q = cuota_pendiente.pop(anio_pago, 0.0)
            if q > 0:
                etfs = [c for c, _ in cuentas if c.modo == 'etf']
                tot = sum(c.valor(P, pi) for c in etfs)
                for c in etfs:
                    vc = c.valor(P, pi)
                    parte = q * vc / tot
                    for a in list(c.units):
                        if c.units[a] > 1e-12:
                            c.vender(a, parte * c.units[a] * P[a][pi] / vc, P, pi, f)
                impuestos_pagados += q
        valores[i] = sum(c.valor(P, pi) for c, _ in cuentas)
        for (c, _), smap in zip(cuentas, sig_map):
            if i in smap:
                obj = smap[i]
                if obj != c.ultimo_obj:
                    pendientes.append((i + 1, c, obj))
                    c.ultimo_obj = obj

    fin_idx = len(fechas)
    ganancia_final = 0.0
    for c, _ in cuentas:
        for a in list(c.units):
            if c.units[a] > 1e-12 and c.modo == 'etf':
                c.vender(a, c.units[a] * P[a][fin_idx], P, fin_idx, fechas[-1])
        if c.modo == 'fondo':
            ganancia_final += c.valor(P, fin_idx) - c.coste_total
    yr = fechas[-1].year
    if impuestos:
        for y in range(anio_calc + 1, yr):
            arrastre = procesar_anio(y, cuentas, arrastre, cuota_pendiente, tramos)
        g = ganancia_final + sum(c.realizado.get(yr, 0.0) for c, _ in cuentas if c.modo == 'etf')
        arrastre = [(y, x) for y, x in arrastre if yr - y <= 4]
        for y, x in arrastre:
            usa = min(x, max(g, 0))
            g -= usa
        q_final = cuota(max(g, 0.0), tramos)
        q_prev = sum(cuota_pendiente.values())
    else:
        q_final = q_prev = 0.0
    neto_final = valores[-1] - q_final - q_prev
    impuestos_pagados += q_final + q_prev
    return pd.Series(valores, index=fechas), dict(
        neto_final=neto_final, impuestos=impuestos_pagados, capital=capital,
        operaciones=sum(c.operaciones for c, _ in cuentas), costes=sum(c.costes for c, _ in cuentas))


def metricas(v, info):
    yrs = len(v) / 252
    cagr = (v.iloc[-1] / info['capital']) ** (1 / yrs) - 1
    cagr_neto = (info['neto_final'] / info['capital']) ** (1 / yrs) - 1
    dd = v / np.maximum.accumulate(np.maximum(v.values, info['capital'])) - 1
    anual = v.resample('YE').last()
    anual = anual / pd.concat([pd.Series([info['capital']]), anual.iloc[:-1]]).values - 1
    peak = np.maximum.accumulate(v.values)
    uw, maxuw, start = False, 0, None
    for d, x, p in zip(v.index, v.values, peak):
        if x < p * 0.999:
            if not uw:
                uw, start = True, d
            maxuw = max(maxuw, (d - start).days)
        else:
            uw = False
    return dict(cagr=cagr, cagr_neto=cagr_neto, maxdd=dd.min(), peor_anio=anual.min(),
                max_bajo_agua_anios=maxuw / 365.25, ops_anio=info['operaciones'] / yrs,
                final_neto=info['neto_final'], impuestos=info['impuestos'])
