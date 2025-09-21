# QA Checklist · STAGE-5 (Validación Baseline Pi 5)

Este checklist asegura que la rama actual mantiene paridad funcional con la baseline del **06‑Sep‑2025**. Está pensado para ejecutarse en una **Raspberry Pi 5** con la báscula instalada.

## 1. Preparación

1. Actualiza el repositorio y dependencias:
   ```bash
   cd ~/bascula-cam
   git pull
   make venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Reinicia servicios para partir de un estado limpio:
   ```bash
   sudo systemctl restart bascula-ui.service bascula-web.service bascula-recognizer.service
   ```
3. Verifica que el smoke test básico siga funcionando:
   ```bash
   ./scripts/smoke.sh
   ```
   Debe finalizar en «OK» sin errores.

## 2. UI «Nuevo plato → Añadir → Tabla → Resumen»

1. Conecta pantalla/ratón o usa VNC.
2. Desde la UI principal selecciona **Nuevo plato**.
3. Añade dos ingredientes ficticios (usa cámara o introduce peso simulado si no hay sensor):
   - Verifica que cada ingrediente aparezca en la tabla con peso y macros.
   - Comprueba que el botón **Resumen** muestre totales y el desglose nutricional.
4. Guarda como favorito y confirma que aparece en la lista de recetas/favoritos.
5. Captura de pantalla: vista de la tabla y del resumen (se adjuntan al informe de QA).

## 3. Reconocimiento (local + GPT)

### 3.1 Con token válido y red disponible
1. Asegúrate de tener conectividad (`ping 8.8.8.8`).
2. Coloca un alimento conocido frente a la cámara.
3. Comprueba en la UI que:
   - Se muestra el resultado del modelo local.
   - Tras la llamada a GPT (ver logs en `/var/log/bascula/recognizer.log`) se refine la descripción.

### 3.2 Sin token / sin red (fallback manual)
1. Renombra temporalmente la API Key:
   ```bash
   mv ~/.config/bascula/apikey.json ~/.config/bascula/apikey.json.bak
   sudo systemctl restart bascula-recognizer.service
   ```
2. Repite el flujo de reconocimiento:
   - La UI debe mostrar solo el resultado local y ofrecer edición manual.
   - Confirma que **no** se bloquea la interfaz.
3. Restaura la API Key al finalizar.

## 4. Recetas y favoritos

1. Desde la UI, abre **Recetas** y verifica que las existentes cargan correctamente.
2. Genera una receta nueva (conexión activa) y guarda como favorita.
3. Desconecta la red y abre de nuevo la sección para asegurar que las recetas guardadas se muestran desde cache local.
4. Comprueba en disco que `~/.config/bascula/recipes.jsonl` contiene el nuevo registro.

## 5. Mini-web + fallback AP

1. En la Pi ejecuta:
   ```bash
   sudo systemctl status bascula-web.service
   curl -sSf http://127.0.0.1:8080/health
   ```
   Debe devolver `{ "ok": true }`.
2. Desde otro dispositivo en la misma LAN accede a `http://<IP_Pi>:8080/` e inicia sesión con el PIN mostrado en la UI.
3. Verifica las acciones:
   - Guardar API Key (usar una clave de prueba).
   - Actualizar Nightscout y parámetros de bolo.
   - Comprobar que `/api/status` muestra `api_key_present: true` tras guardar la clave.
4. Simula caída de red doméstica para probar modo AP:
   - Desactiva Wi‑Fi doméstico (`nmcli radio wifi off`).
   - Reinicia `bascula-ap.service` si aplica y conéctate a `Bascula_AP`.
   - Accede a `http://10.42.0.1:8080/` y repite el flujo anterior.

## 6. Logs de verificación rápida

Revisa que no aparezcan errores críticos tras las pruebas:
```bash
sudo journalctl -u bascula-ui.service -u bascula-web.service -u bascula-recognizer.service --since "-30 min"
```

## 7. Pruebas automatizadas ligeras

1. Ejecuta los tests sin hardware real:
   ```bash
   source ~/bascula-cam/.venv/bin/activate
   pytest tests/test_miniweb.py tests/test_recipes_steps.py
   ```
   Deben pasar todos los casos.
2. (Opcional) Ejecuta la batería completa:
   ```bash
   pytest
   ```

> Guarda capturas relevantes (UI tabla/resumen, mini-web, modo AP) en `docs/screenshots/QA-<fecha>.png` y adjúntalas en el informe.

