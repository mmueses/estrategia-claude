# Backtests de la estrategia

Código para repetir las cifras del proyecto y añadir cada año en la revisión de enero.

| Programa | Qué calcula | Cifras que reproduce (comprobado el 18-11-2026) |
|---|---|---|
| `oficial.py` (+ `data.py`, `estrategias.py`, `sim.py`) | Motor oficial: euros, impuestos del ahorro, dual pricing 0,05 %, refugio real (bonos 1-5 años cubiertos o monetario), traspasos con 5 días fuera, festivos corregidos. Versión elegida: solo S&P 500, 3 tramos. | Estrategia 9,0 % neto y -22,5 %; S&P comprar y mantener 7,6 % y -64,7 % (1999-01 a 13-11-2026). Según fechas: 8,4-9,0 %, típico 8,8 % y -31 %. |
| `dolares.py` | Motor de la auditoría: dólares, índices sin dividendos, sin impuestos. Para comparar versiones rápido (incluida la mezcla con el Nasdaq-100). | Solo S&P 6,5 % y -24 %; mezcla 9,2 % y -25 % (mediana de 8 calendarios). |
| `../pruebas/comprueba_senales.py` | Que las señales de la app coinciden con las del backtest. | 334, 335 y 334 revisiones desde 1999, cero diferencias. |

Uso:
```
pip install yfinance pandas pandas_market_calendars
python3 descarga_datos.py datos_bt
python3 oficial.py datos_bt
python3 dolares.py datos_bt
python3 ../pruebas/comprueba_senales.py datos_bt/GSPC.csv
```
Los datos no se guardan en el repositorio. Yahoo revisa a veces sus series: si una cifra se mueve una décima, es por eso.
Las estrategias descartadas (GEM, ARALP, rotación, apalancamiento, bandas) están en el proyecto, en claude/codigo-backtest.md y en los documentos de cada fase.
