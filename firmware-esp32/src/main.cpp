// firmware-esp32/src/main.cpp
//
// ESP32 + HX711 -> UART (Serial1) @ 115200
// Protocolo por línea: G:<gramos>,S:<0|1>
// Comandos desde la Pi: "T" (Tara) y "C:<peso>" (Calibrar con peso patrón en gramos)
//
// - Filtro: mediana (ventana N) + IIR (alpha)
// - Estabilidad: ventana temporal con umbral
// - Persistencia: factor de calibración y tara en NVS (Preferences)
//
// Pines por defecto (ajustables):
//   HX711_DOUT = GPIO 4
//   HX711_SCK  = GPIO 5
//   UART1_TX   = GPIO 17
//   UART1_RX   = GPIO 16
//
// Cableado con Raspberry Pi (3V3):
//   ESP32 TX (UART1_TX) -> Pi RX (GPIO15/pin10)
//   ESP32 RX (UART1_RX) -> Pi TX (GPIO14/pin8)
//   GND común
//
// Requisitos de librerías en el IDE de Arduino (ESP32):
//   - HX711 (Bogdan Necula / bogde): https://github.com/bogde/HX711
//   - Preferences (incluida con core ESP32)
//   - Core ESP32 para Arduino
//
// Compilación: Placa ESP32 (WROOM/DevKit, etc.)

#include <Arduino.h>
#include <HX711.h>
#include <Preferences.h>
#include <algorithm>  // std::sort para mediana
#include <math.h>     // fabsf

// ---------- CONFIGURACIÓN DE PINES ----------
#ifndef HX711_DOUT_PIN
#define HX711_DOUT_PIN 4
#endif

#ifndef HX711_SCK_PIN
#define HX711_SCK_PIN 5
#endif

#ifndef UART1_TX_PIN
#define UART1_TX_PIN 17
#endif

#ifndef UART1_RX_PIN
#define UART1_RX_PIN 16
#endif

// ---------- CONFIGURACIÓN SERIAL ----------
static const uint32_t BAUD = 115200;     // Protocolo UART (Serial1)
static const uint32_t BAUD_USB = 115200; // Consola debug (Serial)

// ---------- FILTROS Y ESTABILIDAD ----------
static const size_t MEDIAN_WINDOW = 15;     // Tamaño ventana mediana (impar recomendado)
static const float IIR_ALPHA = 0.20f;       // Filtro IIR (0-1): mayor = más reactivo
static const float STABLE_DELTA_G = 1.0f;   // Umbral en gramos para considerar estable
static const uint32_t STABLE_MS = 700;      // Tiempo manteniendo estabilidad (ms)
static const uint16_t LOOP_HZ = 50;         // Frecuencia de muestreo aprox. (Hz)

// ---------- NVS KEYS ----------
static const char* NVS_NAMESPACE  = "bascula";
static const char* KEY_CAL_FACTOR = "cal_f";  // float
static const char* KEY_TARE_OFFSET= "tare";   // int32_t (unidades HX711)

// ---------- OBJETOS GLOBALES ----------
HX711 scale;
Preferences prefs;

// ---------- ESTADO CALIBRACIÓN ----------
volatile float   g_calFactor = 1.0f;  // factor unidades->gramos
volatile int32_t g_tareOffset = 0;    // offset de tara (unidades crudas HX711)

// ---------- BUFFER PARA MEDIANA ----------
class RingBuffer {
public:
  explicit RingBuffer(size_t n) : N(n), idx(0), count(0) {
    buf = new long[N];
    for (size_t i = 0; i < N; ++i) buf[i] = 0;
  }
  ~RingBuffer() { delete[] buf; }

  void add(long v) {
    buf[idx] = v;
    idx = (idx + 1) % N;
    if (count < N) count++;
  }

  bool full() const { return count == N; }
  size_t size() const { return count; }

  long median() const {
    if (count == 0) return 0;
    long* tmp = new long[count];
    for (size_t i = 0; i < count; ++i) tmp[i] = buf[i];
    // Orden estable/rápido suficiente para N pequeño
    std::sort(tmp, tmp + count);
    // Mediana “clásica” (para N par devolveríamos el superior; usamos ventana impar)
    long m = tmp[count / 2];
    delete[] tmp;
    return m;
  }

private:
  long*  buf;
  size_t N;
  size_t idx;
  size_t count;
};

// ---------- UTILS ----------
static inline long readRaw() {
  // lectura cruda de HX711 (24-bit signed)
  return scale.read();
}

static inline float rawToGrams(long raw) {
  // Aplica tara y factor de calibración
  long raw_net = raw - g_tareOffset;
  return (float)raw_net * g_calFactor;
}

// ---------- PARSEO DE COMANDOS ----------
String cmdLine;

void handleCommand(const String& line) {
  // Comandos:
  // "T"           -> Tara (guarda offset)
  // "C:<peso>"    -> Calibrar con peso patrón en gramos (float/entero)
  if (line.length() == 0) return;

  if (line == "T" || line == "t") {
    // TARA: fijamos el offset actual
    long r = readRaw();
    g_tareOffset = r;
    prefs.putInt(KEY_TARE_OFFSET, g_tareOffset);
    Serial.println(F("[NVS] Tara guardada"));
    Serial1.println(F("ACK:T"));
    return;
  }

  if (line.startsWith("C:") || line.startsWith("c:")) {
    String w = line.substring(2);
    w.trim();
    float peso_ref = w.toFloat(); // admite "500", "500.0"
    if (peso_ref <= 0.0f) {
      Serial1.println(F("ERR:CAL:weight"));
      return;
    }
    // Leemos promedio de varias muestras para robustez
    const int N = 20;
    long acc = 0;
    for (int i = 0; i < N; ++i) {
      acc += readRaw();
      delay(5);
    }
    long r_mean = acc / N;
    long r_net  = r_mean - g_tareOffset;
    if (r_net == 0) {
      Serial1.println(F("ERR:CAL:zero"));
      return;
    }
    g_calFactor = (float)peso_ref / (float)r_net; // factor g por unidad cruda
    prefs.putFloat(KEY_CAL_FACTOR, g_calFactor);
    Serial.print(F("[NVS] Calibración guardada. Factor: "));
    Serial.println(g_calFactor, 8);
    Serial1.print(F("ACK:C:"));
    Serial1.println(g_calFactor, 8);
    return;
  }

  // Comando desconocido:
  Serial1.println(F("ERR:UNKNOWN_CMD"));
}

// ---------- SETUP ----------
void setup() {
  // Consola USB para debug
  Serial.begin(BAUD_USB);
  delay(200);

  // UART1 para protocolo hacia la Pi
  Serial1.begin(BAUD, SERIAL_8N1, UART1_RX_PIN, UART1_TX_PIN);
  delay(100);

  Serial.println();
  Serial.println(F("== Bascula ESP32 + HX711 @ UART =="));
  Serial.print(F("UART1 TX=")); Serial.print(UART1_TX_PIN);
  Serial.print(F(" RX=")); Serial.println(UART1_RX_PIN);

  // HX711 init
  scale.begin(HX711_DOUT_PIN, HX711_SCK_PIN);
  delay(50);

  // NVS
  prefs.begin(NVS_NAMESPACE, false);
  g_calFactor  = prefs.getFloat(KEY_CAL_FACTOR, 1.0f);
  g_tareOffset = prefs.getInt(KEY_TARE_OFFSET, 0);

  Serial.print(F("CalFactor: ")); Serial.println(g_calFactor, 8);
  Serial.print(F("TareOffset: ")); Serial.println(g_tareOffset);

  // Mensaje inicial
  Serial1.println(F("HELLO:ESP32-HX711"));
}

// ---------- LOOP ----------
void loop() {
  static RingBuffer rb(MEDIAN_WINDOW);
  static bool first = true;
  static float iir_value = 0.0f;
  static uint32_t lastStableRefMs = 0;
  static bool stable = false;

  // 1) Leer crudo y alimentar mediana
  long raw = readRaw();
  rb.add(raw);

  // 2) Derivar gramos (mediana + IIR)
  float grams;
  if (rb.size() >= 3) {
    long med = rb.median();
    float g  = rawToGrams(med);
    if (first) {
      iir_value = g;
      first = false;
    } else {
      iir_value = (1.0f - IIR_ALPHA) * iir_value + IIR_ALPHA * g;
    }
    grams = iir_value;
  } else {
    grams = rawToGrams(raw);
  }

  // 3) Estabilidad: variación respecto a última referencia durante STABLE_MS
  static float last_grams = 0.0f;
  float delta = fabsf(grams - last_grams);
  uint32_t now = millis();

  if (delta <= STABLE_DELTA_G) {
    // Si ya llevamos tiempo cumpliendo umbral -> estable
    if ((now - lastStableRefMs) >= STABLE_MS) {
      stable = true;
    }
  } else {
    // Se rompe la estabilidad; reinicia referencia temporal
    stable = false;
    lastStableRefMs = now;
  }
  last_grams = grams;

  // 4) Emitir trama única: "G:<valor>,S:<0|1>"
  char out[64];
  snprintf(out, sizeof(out), "G:%.2f,S:%d", grams, stable ? 1 : 0);
  Serial1.println(out);

  // 5) Leer comandos de la Pi (Serial1)
  while (Serial1.available()) {
    char c = (char)Serial1.read();
    if (c == '\r' || c == '\n') {
      cmdLine.trim();
      if (cmdLine.length() > 0) {
        handleCommand(cmdLine);
      }
      cmdLine = "";
    } else {
      if (cmdLine.length() < 80) cmdLine += c;
    }
  }

  // 6) Ritmo del bucle
  delay(1000 / LOOP_HZ);
}
