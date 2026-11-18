"""Baja los datos de los dos motores a una carpeta (por defecto datos_bt/, que no se sube al repositorio).

  python3 descarga_datos.py [carpeta]

- px2.csv (oficial.py): cierres ajustados de Yahoo de ^GSPC, ^IRX, VFINX, VGTSX, VEURX, VEIEX, VBMFX y VBISX.
- fx.csv y eur3m.csv (oficial.py): github.com/datasets/exchange-rates y github.com/datasets/euribor.
- GSPC.csv, NDX.csv, IRX.csv (dolares.py y pruebas/comprueba_senales.py): cierres sin ajustar de Yahoo.
Para repetir exactamente las cifras de noviembre de 2026, los motores cortan en el 13-11-2026 (oficial)
y usan hasta el último dato (dólares). Al añadir un año en enero, cambiar FIN en data.py.
"""
import os
import subprocess
import sys
import tempfile

import yfinance as yf

d = sys.argv[1] if len(sys.argv) > 1 else 'datos_bt'
os.makedirs(d, exist_ok=True)
t = ['^GSPC', '^IRX', 'VFINX', 'VGTSX', 'VEURX', 'VEIEX', 'VBMFX', 'VBISX']
px = yf.download(t, start='1997-01-01', progress=False, auto_adjust=False)['Adj Close'][t]
px.to_csv(f'{d}/px2.csv')
for tk in ['^GSPC', '^NDX', '^IRX']:
    x = yf.download(tk, start='1985-01-01', progress=False, auto_adjust=False, multi_level_index=False)
    x.index.name = 'Date'
    x[['Open', 'High', 'Low', 'Close', 'Volume']].to_csv(f"{d}/{tk.strip('^')}.csv")
with tempfile.TemporaryDirectory() as tmp:
    for repo, origen, destino in [('exchange-rates', 'data/daily.csv', 'fx.csv'),
                                  ('euribor', 'data/euribor-3m-monthly.csv', 'eur3m.csv')]:
        subprocess.run(['git', 'clone', '-q', '--depth', '1', f'https://github.com/datasets/{repo}', f'{tmp}/{repo}'], check=True)
        os.replace(f'{tmp}/{repo}/{origen}', f'{d}/{destino}')
print('Datos en', d)
