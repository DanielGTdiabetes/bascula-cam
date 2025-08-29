// firmware-esp32/src/main.cpp
//
// ESP32 + HX711 -> UART (Serial1) @ 115200
// Protocolo por línea: G:<gramos>,S:<0|1>
// Comandos desde la Pi: "T" (Tara) y "C:<peso>" (Calibrar con peso patrón en gramos)
//
// - Filtro: mediana (ventana N) + IIR (alpha)
// - Estabilidad: delta temporal y (opcional) desviación estándar
// - Persistencia: factor de calibración y tara en NVS (Preferences)
// - Protección: límite de longitud de comando y error si se excede
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
// Requisitos de librerías (Arduino IDE):
//   - HX711 (bogde): https://github.com/bogde/HX711
//   - Preferences (core ESP32)
//   - Core ESP32 de Espressif

#include <Arduino.h>
#include <HX711.h>
#include <Preferences.h>
#include <algorithm>  // std::sort
#include <math.h>     // fabsf

// ===================== AJUSTES ANTI-BAILE =====================

// Ventana de mediana más grande (impar)
static const size_t  MEDIAN_WINDOW   = 21;

// Filtro IIR más suave (menor alpha = más suavizado)
static const float   IIR_ALPHA       = 0.08f;

// Estabilidad por delta durante un tiempo
static const float    STABLE_DELTA_G = 3.0f;   // tolerancia de variación [g]
static const uint32_t STABLE_MS      = 1500;   // ms manteniendo variación baja

// (OPCIONAL) Estabilidad reforzada: desviación estándar de últimas N lecturas
#define USE_STDDEV_STABILITY 1
static const size_t  SD_WINDOW   = 25;   // nº lecturas para stddev (post-filtro)
static const float   SD_THRESH_G = 1.5f; // umbral de sigma [g]

// (OPCIONAL) Deadband de salida: si S=1 y el cambio es pequeño, no actualizar
#define USE_DEADBAND 1
static const float   DEAD_BAND_G = 0.20f; // histéresis de salida [g]

// ===================== CONFIG PINES Y SERIAL =====================

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

static const uint32_t BAUD     = 115200;   // Serial1 (a la Pi)
static const uint32_t BAUD_USB = 115200;   // Serial (debug USB)

// ===================== NVS =====================

static const char* NVS_NAMESPACE   = "bascula";
static const char* KEY_CAL_FACTOR  = "cal_f";
static const char* KEY_TARE_OFFSET = "tare";

// ===================== COMANDOS =====================

static const size_t CMD_MAX_LEN = 80;     // límite seguro para líneas de comando

// ===================== OBJETOS GLOBALES =====================

HX711      scale;
Preferences prefs;

// Estado de calibración
volatile float   g_calFactor  = 1.0f;  // unidades crudas -> gramos
volatile int32_t g_tareOffset = 0;     // offset de tara (unidades crudas)

// ===================== ESTRUCTURAS DE FILTRADO =====================

class RingBufferRaw {
public:
  explicit RingBufferRaw(size_t n) : N(n), idx(0), count(0) {
    buf = new long[N];
    for (size_t i = 0; i < N; ++i) buf[i] = 0;
  }
  ~RingBufferRaw() { delete[] buf; }

  void add(long v) {
    buf[idx] = v;
    idx = (idx + 1) % N;
    if (count < N) count++;
  }

  size_t size() const { return count; }

  long median() const {
    if (count == 0) return 0;
    long* tmp = new long[count];
    for (size_t i = 0; i < count; ++i) tmp[i] = buf[i];
    std::sort(tmp, tmp + count);
    long m = tmp[count / 2]; // usar ventana impar
    delete[] tmp;
    return m;
  }

private:
  long*  buf;
  size_t N;
  size_t idx;
  size_t count;
};

class RingBufferFloat {
public:
  explicit RingBufferFloat(size_t n) : N(n), idx(0), count(0) {
    buf = new float[N];
    for (size_t i = 0; i < N; ++i) buf[i] = 0.0f;
  }
  ~RingBufferFloat() { delete[] buf; }

  void add(float v) {
    buf[idx] = v;
    idx = (idx + 1) % N;
    if (count < N) count++;
  }

  size_t size() const { return count; }

  float mean() const {
    if (count == 0) return 0.0f;
    double acc = 0.0;
    for (size_t i = 0; i < count; ++i) acc += buf[i];
    return (float)(acc / (double)count);
  }

  float stddev() const {
    if (count == 0) return 0.0f;
    float mu = mean();
    double acc = 0.0;
    for (size_t i = 0; i < count; ++i) {
      double d = (double)buf[i] - (double)mu;
      acc += d * d;
    }
    return (float)sqrt(acc / (double)count);
  }

private:
  float* buf;
  size_t N;
  size_t idx;
  size_t count;
};

// ===================== UTILS =====================

static inline long readRaw() {
  return scale.read(); // 24-bit signed
}

static inline float rawToGrams(long raw) {
  long raw_net = raw - g_tareOffset;
  return (float)raw_net * g_calFactor;
}

// ===================== PARSEO DE COMANDOS =====================

String cmdLine;
bool   cmdOverflow = false;

void handleCommand(const String& line) {
  // "T"         -> Tara (guardar offset actual)
  // "C:<peso>"  -> Calibrar con peso patrón en gramos
  if (line.length() == 0) return;

  if (line == "T" || line == "t") {
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
    float peso_ref = w.toFloat();
    if (peso_ref <= 0.0f) {
      Serial1.println(F("ERR:CAL:weight"));
      return;
    }
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
    g_calFactor = (float)peso_ref / (float)r_net;
    prefs.putFloat(KEY_CAL_FACTOR, g_calFactor);
    Serial.print(F("[NVS] Calibración guardada. Factor: "));
    Serial.println(g_calFactor, 8);
    Serial1.print(F("ACK:C:"));
    Serial1.println(g_calFactor, 8);
    return;
  }

  Serial1.println(F("ERR:UNKNOWN_CMD"));
}

// ===================== SETUP =====================

void setup() {
  Serial.begin(BAUD_USB);
  delay(150);

  Serial1.begin(BAUD, SERIAL_8N1, UART1_RX_PIN, UART1_TX_PIN);
  delay(100);

  Serial.println();
  Serial.println(F("== Bascula ESP32 + HX711 @ UART =="));
  Serial.print(F("UART1 TX=")); Serial.print(UART1_TX_PIN);
  Serial.print(F(" RX=")); Serial.println(UART1_RX_PIN);

  scale.begin(HX711_DOUT_PIN, HX711_SCK_PIN);
  delay(50);

  prefs.begin(NVS_NAMESPACE, false);
  g_calFactor  = prefs.getFloat(KEY_CAL_FACTOR, 1.0f);
  g_tareOffset = prefs.getInt(KEY_TARE_OFFSET, 0);

  Serial.print(F("CalFactor: ")); Serial.println(g_calFactor, 8);
  Serial.print(F("TareOffset: ")); Serial.println(g_tareOffset);

  Serial1.println(F("HELLO:ESP32-HX711"));
}

// ===================== LOOP =====================

void loop() {
  static RingBufferRaw   rb(MEDIAN_WINDOW);
  static RingBufferFloat rb_g(SD_WINDOW);     // para stddev sobre grams (post-filtro)
  static bool   first = true;
  static float  iir_value = 0.0f;
  static uint32_t lastStableRefMs = 0;
  static bool   stable = false;

  // 1) Leer crudo y alimentar mediana
  long raw = readRaw();
  rb.add(raw);

  // 2) Mediana + IIR
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

  // 3) Alimentar buffer de grams para stddev (si activo)
  #if USE_STDDEV_STABILITY
    rb_g.add(grams);
  #endif

  // 4) Estabilidad por delta temporal (+ opcional stddev)
  static float last_grams_for_delta = 0.0f;
  float delta = fabsf(grams - last_grams_for_delta);
  uint32_t now = millis();

  bool cond_delta = (delta <= STABLE_DELTA_G);
  bool cond_time  = ((now - lastStableRefMs) >= STABLE_MS);

  bool cond_stddev = true;
  #if USE_STDDEV_STABILITY
    if (rb_g.size() >= SD_WINDOW / 2) {
      float sd = rb_g.stddev();
      cond_stddev = (sd <= SD_THRESH_G);
    }
  #endif

  if (cond_delta && cond_stddev) {
    if (cond_time) {
      stable = true;
    }
  } else {
    stable = false;
    lastStableRefMs = now;
    last_grams_for_delta = grams; // actualizar referencia al romper estabilidad
  }

  // 5) Deadband de salida (si estable y cambio pequeño, “congelar” valor)
  static float last_output = 0.0f;
  float out_grams = grams;
  #if USE_DEADBAND
    if (stable) {
      float odelta = fabsf(grams - last_output);
      if (odelta < DEAD_BAND_G) {
        out_grams = last_output; // congela salida mientras el cambio sea pequeño
      }
    }
  #endif

  // 6) Emitir trama única: "G:<valor>,S:<0|1>"
  char out[64];
  snprintf(out, sizeof(out), "G:%.2f,S:%d", out_grams, stable ? 1 : 0);
  Serial1.println(out);
  last_output = out_grams;

  // 7) Leer comandos de la Pi con control de longitud
  while (Serial1.available()) {
    char c = (char)Serial1.read();
    if (c == '\r' || c == '\n') {
      if (cmdOverflow) {
        Serial1.println(F("ERR:CMDLEN"));
      } else {
        cmdLine.trim();
        if (cmdLine.length() > 0) {
          handleCommand(cmdLine);
        }
      }
      cmdLine = "";
      cmdOverflow = false;
    } else {
      if (!cmdOverflow) {
        if (cmdLine.length() < CMD_MAX_LEN) {
          cmdLine += c;
        } else {
          cmdOverflow = true; // descartar hasta fin de línea
        }
      }
    }
  }

  // 8) Ritmo del bucle
  const uint16_t LOOP_HZ = 50;
  delay(1000 / LOOP_HZ);
}
