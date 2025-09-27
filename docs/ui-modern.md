# Bascula UI Modernization Plan

## Estado actual (M2)

- Pantalla Home renovada con toolbar mínima, peso a 120px y botonera táctil (TARA, ZERO, g/ml, Alimentos, Recetas, Temporizador).
- Router de pantallas y helpers de kiosco en Tk aplicados en `bascula/ui/app.py` y `bascula/ui/windowing.py`.
- Servicios reescritos para báscula (ESP32/HX711), audio MAX98357A, nutrición y Nightscout con APIs consistentes.
- Modo alimentos con tabla y totales, recetas interactivas y temporizador con presets.
- Ajustes modulares con pestañas (General, Báscula, Red, Diabetes, OTA/Recovery, Mini-web) respaldados por `bascula/config/settings.py`.
- Mini-web responde 200 en `/` con FastAPI.
- Nuevas pruebas (`tests/test_windowing.py`, `tests/test_settings.py`, `tests/test_scale_fake.py`, `tests/test_web_root.py`) y script `ci/bin/ci-ui-smoke.sh`.

---

This repository currently does not implement the full "M2 Reescritura UI Moderna" feature set described in the prompt. The following checklist captures the high-level workstreams required to reach parity with the functional specification. Each section should be treated as a milestone deliverable.

## 1. Arquitectura de Ventanas (Tkinter)
- [x] Implement a screen router in `bascula/ui/app.py` to manage Home, Alimentos, Recetas, Ajustes, Historial, Exportar y Técnico.
- [x] Aplicar `apply_kiosk_window_prefs` tras crear la raíz de Tk y asegurar modo kiosco en todo momento.
- [x] Crear/actualizar `bascula/ui/windowing.py` con funciones compartidas para ventanas principales y pop-ups.

## 2. Home Moderno
- [x] Rediseñar la pantalla principal con barra superior mínima: glucemia, temporizador activo y botón de sonido.
- [x] Posicionar un icono de engranaje en la esquina superior derecha que abra Ajustes.
- [x] Botonera principal con acciones TARA, ZERO, Conversor g/ml, Alimentos, Recetas y Temporizador.
- [x] Mostrar peso en tipografía grande (≥120 px) con contraste elevado.

## 3. Servicios Críticos
- [x] `bascula/services/scale.py`: lectura continua desde ESP32/HX711, filtros de estabilidad y control de tara/cero.
- [x] `bascula/services/audio.py`: control completo del MAX98357A, incluidos beeps, alarmas y síntesis por Piper.
- [x] `bascula/services/nutrition.py`: reconocimiento de alimentos, totales nutricionales y disclaimers médicos.
- [x] `bascula/services/nightscout.py`: integración Nightscout, modo 15/15 y cálculos de bolo.

## 4. Funciones de Interfaz Adicionales
- [x] Modo Alimentos con tabla detallada y totales.
- [x] Modo Recetas interactivo con soporte de voz y adaptación dinámica de cantidades.
- [x] Temporizador con presets rápidos, teclado numérico y alarmas de sonido/voz.
- [x] Ajustes por pestañas (General, Báscula, Red, Diabetes, OTA/Recovery, Mini-web) con persistencia en `config/settings.py`.

## 5. Mini-web
- [x] Garantizar respuesta HTTP 200 en `/` mostrando estado básico, IP/puerto y PIN.
- [ ] Añadir soporte para QR de acceso y configuración remota de Wi-Fi, API Key y Nightscout.

## 6. Documentación y QA
- [x] Documentar la nueva UI, flujos de usuario y requisitos hardware.
- [x] Añadir instrucciones de verificación en Raspberry Pi siguiendo los pasos de QA proporcionados.
- [x] Mantener registros claros en `/var/log/bascula/app.log`.

## 7. Pendientes Técnicos
- [ ] Confirmar compatibilidad Piper + MAX98357A en Raspberry Pi OS Bookworm Lite.
- [ ] Validar arranque kiosco (systemd → startx → openbox → safe_run.sh → python main.py).
- [ ] Preparar pruebas automatizadas/regresión para las nuevas capas de servicio.

---

> **Nota:** El checklist restante refleja tareas de seguimiento para iteraciones futuras.
