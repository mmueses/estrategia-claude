# Estrategia S&P 500 + Nasdaq-100 (Proyecto «Estrategia Claude»)

App web que dice, para cada bloque de la cartera, si hay que estar en el fondo de su índice o en refugio, y si toca hacer un traspaso.

**Copia de seguridad de la versión solo S&P 500 (3 tramos, hasta el 18-11-2026):** rama [`solo-sp500`](https://github.com/mmueses/estrategia-claude/tree/solo-sp500). Para volver a ella: copiar sus `evalua.py`, `descarga.py`, `avisa.py`, `index.html` y `sw.js` a `main`.

**Abrir la app:** https://mmueses.github.io/estrategia-claude/
En Android, ábrela con Chrome y pulsa ⋮ > **Añadir a pantalla de inicio** (o **Instalar aplicación**).

## Reglas

- Desde el 18-11-2026 la cartera va mitad S&P 500 y mitad Nasdaq-100, cada mitad con su propia señal y en tres tramos: 6 bloques iguales (sextos), en fondos de MyInvestor (los traspasos entre fondos no pagan impuestos en Navarra). Del 17 al 18-11-2026 eran 3 tramos solo del S&P; antes, dos mitades (días fin de mes y 15).
- **Tramo A:** se revisa el último día con bolsa abierta en Nueva York de cada mes.
- **Tramo B:** se revisa el primer día con bolsa abierta a partir del día 10 de cada mes.
- **Tramo C:** se revisa el primer día con bolsa abierta a partir del día 20 de cada mes.
- Los tramos A, B y C existen para cada índice (S&P A, B, C y Nasdaq A, B, C).
- En su fecha, cada tramo compara el cierre de su índice (S&P 500 o Nasdaq-100) con la media de sus 10 últimos cierres de revisión.
  - Por encima: el fondo de su índice: S&P 500 (iShares US Index Fund (IE) clase S Acc EUR, IE000N4ZYX28) o Nasdaq-100 (MyInvestor Nasdaq 100 FI, ES0165265002).
  - Por debajo: refugio. Va a bonos (iShares Global Aggregate 1-5Y cubierto EUR, IE0004ZP1ND3) si su rentabilidad en las 12 últimas revisiones supera a la del monetario (AXA IM Euro Liquidity SRI, FR0000978371). Si no, al monetario.
- El traspaso se ordena el día siguiente a la revisión.

## Cómo funciona

- `descarga.py` baja de Yahoo los cierres del S&P 500 (`^GSPC`), del Nasdaq-100 (`^NDX`) y de los cuatro fondos, y llama a `evalua.py`.
- `evalua.py` aplica las reglas y escribe `datos/estado.json`, que es lo que lee la app (`index.html`).
- La tarea `.github/workflows/actualiza.yml` lo hace sola de lunes a viernes a las 21:47 UTC y de martes a sábado a las 05:17 UTC.
  A mano: pestaña **Actions** > **Actualiza datos** > **Run workflow**.
- Si Yahoo falla, se conserva la última copia buena y la ejecución sale en rojo. La app avisa si los datos tienen más de 5 días.

## Comprobaciones

- Las señales de `evalua.py` coinciden con las del backtest en todas las revisiones de los tres tramos entre 1999 y noviembre de 2026 (334, 335 y 334).
- Nasdaq-100: señales de `evalua.py` comprobadas contra un cálculo independiente en 1998-2026 (349, 350 y 349 revisiones, 0 diferencias).
- La tarjeta «Desde que empezaste» compara la estrategia (6 bloques) con tener todo en el fondo del S&P 500 desde la fecha que pongas (se guarda solo en ese navegador). Usa los valores liquidativos de los fondos (`valores_liquidativos` en `estado.json`) y las órdenes de cada tramo (`ordenes`).
- Reglas de la casa: https://claude.ai/artifact/A2WrfZTghWGtpGg7JMYpPK
- Informe completo del backtest y documentos: Proyecto de claude.ai «Estrategia De Inversion CLAUDE».

## Avisos al móvil (ntfy)

`avisa.py` se ejecuta tras cada actualización y envía con [ntfy](https://ntfy.sh) (una sola vez cada uno, registrados en `datos/avisos.json`):
- El resultado de cada revisión en cuanto hay cierre: «TRASPASO S&P A» / «TRASPASO Nasdaq B»… (prioridad alta, con el fondo y el día de la orden) o «… sin cambios».
- La víspera de una revisión, si ese tramo está a menos de un 1 % de su media.
- Si los datos llevan más de 4 días sin actualizarse.

Para activarlos: instala la app ntfy en el móvil, suscríbete al tema y guarda ese mismo tema en el secreto `NTFY_TOPIC` del repositorio (Settings > Secrets and variables > Actions). Sin el secreto no se envía nada. Prueba: Actions > Actualiza datos > Run workflow, marcando «Enviar un aviso de prueba al móvil».
