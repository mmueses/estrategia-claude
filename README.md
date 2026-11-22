# Estrategia S&P 500 (Proyecto «Estrategia Claude»)

App web que dice, para cada tercio de la cartera, si hay que estar en el fondo del S&P 500 o en refugio, y si toca hacer un traspaso.

> ## ⚠ AVISO IMPORTANTE: NO ES UNA RECOMENDACIÓN DE INVERSIÓN
>
> Proyecto personal y experimental de un particular, para su propio uso. Nada de este repositorio ni de la app constituye, bajo ningún concepto, asesoramiento ni recomendación de inversión, análisis financiero u oferta de instrumentos financieros (Ley 6/2023 de los Mercados de Valores y de los Servicios de Inversión, MiFID II y Reglamento (UE) 596/2014). El autor no es asesor ni está registrado en la CNMV. Invertir en bolsa conlleva riesgo, incluida la pérdida total del capital; los resultados pasados y los backtests no garantizan resultados futuros. Los datos vienen de terceros sin garantía y pueden tener errores. En la máxima medida permitida por la ley, el autor no se hace responsable de ninguna pérdida derivada del uso de este contenido. Texto completo en la propia app.

**Abrir la app:** https://mmueses.github.io/estrategia-claude/
En Android, ábrela con Chrome y pulsa ⋮ > **Añadir a pantalla de inicio** (o **Instalar aplicación**).

## Reglas

- La cartera va en tres tramos iguales (tercios), en fondos de MyInvestor (los traspasos entre fondos no pagan impuestos hasta el reembolso). Desde el 17-11-2026; antes eran dos mitades (días fin de mes y 15).
- **Tramo A:** se revisa el último día con bolsa abierta en Nueva York de cada mes.
- **Tramo B:** se revisa el primer día con bolsa abierta a partir del día 10 de cada mes.
- **Tramo C:** se revisa el primer día con bolsa abierta a partir del día 20 de cada mes.
- En su fecha, cada tramo compara el cierre del índice S&P 500 con la media de sus 10 últimos cierres de revisión.
  - Por encima: fondo S&P 500 (iShares US Index Fund (IE) clase S Acc EUR, IE000N4ZYX28).
  - Por debajo: refugio. Va a bonos (iShares Global Aggregate 1-5Y cubierto EUR, IE0004ZP1ND3) si su rentabilidad en las 12 últimas revisiones supera a la del monetario (AXA IM Euro Liquidity SRI, FR0000978371). Si no, al monetario.
- El traspaso se ordena el día siguiente a la revisión.
- Si un día de revisión no tiene cierre del índice (cierre imprevisto de la bolsa, hueco de Yahoo), la revisión pasa al siguiente día con cierre y la app lo indica.

## Cómo funciona

- `descarga.py` baja de Yahoo los cierres del S&P 500 (`^GSPC`) y de los tres fondos, y llama a `evalua.py`.
- `evalua.py` aplica las reglas y escribe `datos/estado.json`, que es lo que lee la app (`index.html`).
- La tarea `.github/workflows/actualiza.yml` lo hace sola de lunes a viernes a las 21:47 UTC y de martes a sábado a las 05:17 UTC.
  A mano: pestaña **Actions** > **Actualiza datos** > **Run workflow**.
- Si Yahoo falla, se conserva la última copia buena y la ejecución sale en rojo. La app avisa si los datos tienen más de 5 días.
- Si la tarea corre con la bolsa de Nueva York abierta, el precio de ese momento no se guarda como cierre: se descarta hasta 15 minutos después del cierre oficial del día.
- Dependencias con versión exacta y huella (`requirements.txt`, se instala con `--require-hashes`) y acciones de GitHub fijadas por commit. Dependabot propone las actualizaciones cada mes.

## Comprobaciones

- Pruebas (sin red): `python3 -m unittest discover -s pruebas -v`. Se ejecutan solas en cada cambio (tarea «Pruebas»).
- Las señales de `evalua.py` coinciden con las del backtest en todas las revisiones de los tres tramos entre 1999 y noviembre de 2026 (334, 335 y 334, cero diferencias): `python3 pruebas/comprueba_senales.py GSPC_largo.csv`.
- El código de los backtests está en `backtest/`.
- La tarjeta «Desde que empezaste» compara la estrategia con tener todo en el fondo del S&P 500 desde la fecha que pongas (se guarda solo en ese navegador). Usa los valores liquidativos de los fondos (`valores_liquidativos` en `estado.json`) y las órdenes de cada tramo (`ordenes`).
- Reglas de la casa: https://claude.ai/artifact/A2WrfZTghWGtpGg7JMYpPK

## Avisos al móvil (ntfy)

`avisa.py` se ejecuta tras cada actualización y envía con [ntfy](https://ntfy.sh) (una sola vez cada uno, registrados en `datos/avisos.json`):
- El resultado de cada revisión en cuanto hay cierre: «TRASPASO tramo X» (prioridad alta, con el fondo y el día de la orden) o «Tramo X: sin cambios».
- Si el resultado de una revisión ya avisada cambia, «CORRECCIÓN: …» con prioridad máxima.
- La víspera de una revisión, si ese tramo está a menos de un 1 % de su media.
- Si los datos llevan más de 4 días sin actualizarse.

Para activarlos: instala la app ntfy en el móvil, suscríbete al tema y guarda ese mismo tema en el secreto `NTFY_TOPIC` del repositorio (Settings > Secrets and variables > Actions). Sin el secreto no se envía nada. Prueba: Actions > Actualiza datos > Run workflow, marcando «Enviar un aviso de prueba al móvil».

Un aviso solo no mueve dinero: se confirma en la app, y a la entidad se entra desde su propia app, nunca desde un enlace.
