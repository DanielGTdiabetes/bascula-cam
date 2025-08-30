# 1) Ir al proyecto y hacer copia de seguridad del main actual
cd ~/bascula-cam
cp main.py main.py.bak.$(date +%F-%H%M)

# 2) Sustituir el archivo COMPLETO por el launcher nuevo
cat > main.py <<'PY'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from bascula.ui.app import BasculaAppTk

if __name__ == "__main__":
    BasculaAppTk().run()
PY

# 3) Dar permisos de ejecución y verificar contenido
chmod +x main.py
sed -n '1,40p' main.py
