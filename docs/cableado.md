# Cableado HX711 ↔ ESP32 y ESP32 ↔ Raspberry Pi (UART)

## 1) HX711 → ESP32
- HX711 **VCC** → ESP32 **3V3**
- HX711 **GND** → ESP32 **GND**
- HX711 **DT/DOUT** → ESP32 **GPIO 4**  (HX711_DOUT_PIN)
- HX711 **SCK** → ESP32 **GPIO 5**      (HX711_SCK_PIN)

> Los pines 4 y 5 son configurables en `main.cpp`.

## 2) ESP32 ↔ Raspberry Pi (UART GPIO)
- ESP32 **TX (UART1_TX_PIN=GPIO17)** → **Pi RX (GPIO15 / pin físico 10)**
- ESP32 **RX (UART1_RX_PIN=GPIO16)** → **Pi TX (GPIO14 / pin físico 8)**
- **GND común** entre ESP32 y Raspberry Pi

> **Nivel lógico**: ambos a 3.3V → No usar divisores ni conversores de nivel.
> **Baudios**: 115200 8N1.

## 3) Consideraciones
- No alimentar RX/TX a 5V.
- Cruza TX↔RX.
- Asegura alimentación estable de la celda de carga y del ESP32.
