"""Pruebas de la app (sin red). Ejecutar desde la raíz: python3 -m unittest discover -s pruebas -v

- A1: una fila de hoy con la bolsa de Nueva York abierta no cuenta como cierre de revisión.
- A1: si el resultado de una revisión ya avisada cambia, sale un aviso «CORRECCIÓN».
- A2: si falta el cierre de un día de revisión, la revisión pasa al siguiente día con cierre.
- L6: si un aviso no sale, se reintenta y la tarea sale en rojo.
- L7: el aviso de una revisión aplazada pide comprobarla en ProRealTime.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

import pandas as pd

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

import avisa  # noqa: E402
import descarga  # noqa: E402
import evalua  # noqa: E402


def copia_datos():
    tmp = tempfile.mkdtemp()
    for f in os.listdir('datos'):
        if f.endswith('.csv'):
            shutil.copy(f'datos/{f}', tmp)
    return tmp


def leer_csv(carpeta, ticker):
    return pd.read_csv(f"{carpeta}/{ticker.replace('^', '')}.csv", parse_dates=['Date']).set_index('Date')


class SesionAbierta(unittest.TestCase):
    """Día de revisión del tramo C (20-11-2026) con Yahoo dando el precio a media sesión."""

    def preparar(self):
        self.dir = copia_datos()
        base = leer_csv(self.dir, '^GSPC')
        base = base[base.index < '2026-11-18']
        base.to_csv(f'{self.dir}/GSPC.csv')   # los datos reales ya traen el cierre del 20-11: se quitan
        extra = pd.DataFrame({c: [base[c].iloc[-1]] * 3 for c in base.columns},
                             index=pd.DatetimeIndex(['2026-11-18', '2026-11-19', '2026-11-20'], name='Date'))
        self.gspc = pd.concat([base, extra])
        fondos = {v['yahoo']: leer_csv(self.dir, v['yahoo']) for v in evalua.FONDOS.values()}

        def bajar(t, p):
            return self.gspc.copy() if t == '^GSPC' else fondos[t].copy()
        return bajar

    def tramo_c(self, ahora):
        bajar = self.preparar()
        try:
            descarga.principal(self.dir, ahora=pd.Timestamp(ahora), bajar=bajar)
        except SystemExit:
            pass
        estado = json.load(open(f'{self.dir}/estado.json', encoding='utf-8'))
        shutil.rmtree(self.dir)
        return estado, next(t for t in estado['tramos'] if t['tramo'] == 'C')

    def test_media_sesion_no_es_revision(self):
        estado, c = self.tramo_c('2026-11-20 17:00:00+00:00')   # 12:00 en Nueva York
        self.assertEqual(estado['ultimo_cierre']['fecha'], '2026-11-19')
        self.assertFalse(c['revision_hoy'])
        self.assertEqual(c['proxima_revision'], '2026-11-20')

    def test_antes_del_margen_no_es_revision(self):
        _, c = self.tramo_c('2026-11-20 21:10:00+00:00')         # cierre 21:00 UTC, margen hasta 21:15
        self.assertFalse(c['revision_hoy'])

    def test_tras_el_cierre_si_es_revision(self):
        estado, c = self.tramo_c('2026-11-20 21:47:00+00:00')
        self.assertEqual(estado['ultimo_cierre']['fecha'], '2026-11-20')
        self.assertTrue(c['revision_hoy'])

    def test_cierre_anticipado(self):
        # 27-11-2026 (día después de Acción de Gracias) cierra a las 13:00 en Nueva York (18:00 UTC)
        d = pd.DataFrame({'Close': [1.0, 2.0]}, index=pd.DatetimeIndex(['2026-11-25', '2026-11-27']))
        self.assertEqual(len(descarga.quitar_sesion_abierta(d, pd.Timestamp('2026-11-27 18:10:00+00:00'))), 1)
        self.assertEqual(len(descarga.quitar_sesion_abierta(d, pd.Timestamp('2026-11-27 18:20:00+00:00'))), 2)


class Correccion(unittest.TestCase):
    def estado(self, destino, cambio):
        hoy = pd.Timestamp.now(tz='UTC').strftime('%Y-%m-%d')
        rev = dict(fecha=hoy, cierre=100.0, media=99.0, distancia_pct=1.0, aplazada_desde=None)
        tramo = dict(tramo='C', ultima_revision=rev, revision_hoy=True, cambio=cambio, destino=destino,
                     destino_texto=evalua.NOMBRE_DESTINO[destino], fecha_orden=hoy, proxima_revision=None,
                     si_hoy_fuera_revision=dict(distancia_pct=5.0))
        return dict(ultimo_cierre=dict(fecha=hoy, valor=100.0), tramos=[tramo])

    def test_resultado_distinto_avisa_correccion(self):
        tmp = tempfile.mkdtemp()
        enviados = []
        original = avisa.enviar
        avisa.enviar = lambda topic, titulo, mensaje, prio=3, tags=(): enviados.append((titulo, prio)) or True
        os.environ['NTFY_TOPIC'] = 'tema-de-prueba'
        try:
            json.dump(self.estado('SP', False), open(f'{tmp}/estado.json', 'w'))
            avisa.main(tmp)
            avisa.main(tmp)                       # misma revisión, mismo resultado: no repite
            json.dump(self.estado('MONETARIO', True), open(f'{tmp}/estado.json', 'w'))
            avisa.main(tmp)                       # el resultado cambia: corrección
        finally:
            avisa.enviar = original
            del os.environ['NTFY_TOPIC']
            shutil.rmtree(tmp)
        self.assertEqual(len(enviados), 2)
        self.assertEqual(enviados[0][0], 'Tramo C: sin cambios')
        self.assertTrue(enviados[1][0].startswith('CORRECCIÓN'))
        self.assertEqual(enviados[1][1], 5)


class AvisoFallido(unittest.TestCase):
    estado = Correccion.estado

    def test_fallo_de_ntfy_marca_rojo_y_reintenta(self):
        tmp = tempfile.mkdtemp()
        original = avisa.enviar
        os.environ['NTFY_TOPIC'] = 'tema-de-prueba'

        def falla(*a, **k):
            raise OSError('ntfy caído')
        try:
            json.dump(self.estado('SP', False), open(f'{tmp}/estado.json', 'w'))
            avisa.enviar = falla
            fallos = avisa.main(tmp)
            guardados = json.load(open(f'{tmp}/avisos.json'))
            avisa.enviar = lambda *a, **k: True
            fallos2 = avisa.main(tmp)
        finally:
            avisa.enviar = original
            del os.environ['NTFY_TOPIC']
            shutil.rmtree(tmp)
        self.assertEqual(len(fallos), 1)
        self.assertEqual(guardados, {})
        self.assertEqual(fallos2, [])

    def test_aplazada_pide_prorealtime(self):
        e = self.estado('SP', False)
        e['tramos'][0]['ultima_revision']['aplazada_desde'] = '2026-10-20'
        hoy = pd.Timestamp(e['ultimo_cierre']['fecha'])
        mensaje = avisa.avisos(e, hoy)[0][2]
        self.assertIn('comprueba en ProRealTime', mensaje)


class RevisionSinCierre(unittest.TestCase):
    def revisiones(self, quitar):
        spx = evalua.leer('datos', '^GSPC')
        spx = spx[spx.index <= '2026-11-17']
        spx = spx.drop(pd.Timestamp(quitar))
        dias = evalua.dias_bolsa(spx.index[0], pd.Timestamp('2027-02-01'))
        return {dia: evalua.revisiones_tramo(dia, spx, None, dias)[3] for dia in ('fin', 10, 20)}

    def test_dia_20_sin_cierre(self):
        filas = self.revisiones('2026-10-20')[20]
        f = next(x for x in filas if x['fecha'].startswith('2026-10'))
        self.assertEqual((f['fecha'], f['aplazada_desde']), ('2026-10-21', '2026-10-20'))

    def test_fin_de_mes_sin_cierre(self):
        filas = self.revisiones('2026-10-30')['fin']
        f = next(x for x in filas if x['aplazada_desde'] == '2026-10-30')
        self.assertEqual(f['fecha'], '2026-11-02')


if __name__ == '__main__':
    unittest.main()
