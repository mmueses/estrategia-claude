# Estrategia S&P 500 (Proyecto «Estrategia Claude»)

App web que dice, para cada tercio de la cartera, si hay que estar en el fondo del S&P 500 o en refugio, y si toca hacer un traspaso.

**Abrir la app:** https://mmueses.github.io/estrategia-claude/
En Android, ábrela con Chrome y pulsa ⋮ > **Añadir a pantalla de inicio** (o **Instalar aplicación**).

## Reglas

- La cartera va en tres tramos iguales (tercios), en fondos de MyInvestor (los traspasos entre fondos no pagan impuestos en Navarra). Desde el 17-11-2026; antes eran dos mitades (días fin de mes y 15).
- **Tramo A:** se revisa el último día con bolsa abierta en Nueva York de cada mes.
- **Tramo B:** se revisa el primer día con bolsa abierta a partir del día 10 de cada mes.
- **Tramo C:** se revisa el primer día con bolsa abierta a partir del día 20 de cada mes.
- En su fecha, cada tramo compara el cierre del índice S&P 500 con la media de sus 10 últimos cierres de revisión.
  - Por encima: fondo S&P 500 (iShares US Index Fund (IE) clase S Acc EUR, IE000N4ZYX28).
  - Por debajo: refugio. Va a bonos (iShares Global Aggregate 1-5Y cubierto EUR, IE0004ZP1ND3) si su rentabilidad en las 12 últimas revisiones supera a la del monetario (AXA IM Euro Liquidity SRI, FR0000978371). Si no, al monetario.
- El traspaso se ordena el día siguiente a la revisión.

## Cómo funciona

- `descarga.py` baja de Yahoo los cierres del S&P 500 (`^GSPC`) y de los tres fondos, y llama a `evalua.py`.
- `evalua.py` aplica las reglas y escribe `datos/estado.json`, que es lo que lee la app (`index.html`).
- La tarea `.github/workflows/actualiza.yml` lo hace sola de lunes a viernes a las 21:47 UTC y de martes a sábado a las 05:17 UTC.
  A mano: pestaña **Actions** > **Actualiza datos** > **Run workflow**.
- Si Yahoo falla, se conserva la última copia buena y la ejecución sale en rojo. La app avisa si los datos tienen más de 5 días.

## Comprobaciones

- Las señales de `evalua.py` coinciden con las del backtest en todas las revisiones de los tres tramos entre 1999 y noviembre de 2026 (334, 335 y 334).
- La tarjeta «Desde que empezaste» compara la estrategia con tener todo en el fondo del S&P 500 desde la fecha que pongas (se guarda solo en ese navegador). Usa los valores liquidativos de los fondos (`valores_liquidativos` en `estado.json`) y las órdenes de cada tramo (`ordenes`).
- Reglas de la casa: https://claude.ai/artifact/A2WrfZTghWGtpGg7JMYpPK
- Informe completo del backtest y documentos: Proyecto de claude.ai «Estrategia De Inversion CLAUDE».
