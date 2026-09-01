/*
 * ============================================================================
 * Gökkalkan - Arduino Uno & DM542 Çift Motor Sürücü Firmware (R1)
 * ============================================================================
 * 
 * GOKKALKAN-LITE saha referansından gelen pin haritası:
 *   - Pin 2 : 1. Motor (PAN)  PUL+ (Üzerinde 2 yazan klemens/delik)
 *   - Pin 3 : 1. Motor (PAN)  DIR+ (Üzerinde 3 yazan klemens/delik)
 *   - Pin 4 : 2. Motor (TILT) PUL+ (Üzerinde 4 yazan klemens/delik)
 *   - Pin 5 : 2. Motor (TILT) DIR+ (Üzerinde 5 yazan klemens/delik)
 *   - GND   : Her iki DM542'nin PUL- ve DIR- uçlarına (Ortak Katot)
 *   - ENA   : Lite referansında boş; bu, fiziksel E-Stop/kontaktör yerine geçmez.
 * 
 * Desteklenen Protokol Komutları (115200 Baud):
 *   - STEP_PAN <steps> <half_period_us> <CW/CCW>  -> Sınırlı Pan adım sürüşü
 *   - STEP_TILT <steps> <half_period_us> <CW/CCW> -> Sınırlı Tilt adım sürüşü
 *   - JOG_PAN [half_period_us] [CW/CCW]           -> En çok 1 sn Pan bakım jog'u
 *   - JOG_TILT [half_period_us] [CW/CCW]          -> En çok 1 sn Tilt bakım jog'u
 *   - RUN_PAN <sec> <speed_hz> [CW/CCW]           -> En çok 15 sn Pan bakım testi
 *   - RUN_TILT <sec> <speed_hz> [CW/CCW]          -> En çok 15 sn Tilt bakım testi
 *   - RUN <sec> <speed_hz> [CW/CCW]               -> En çok 15 sn çift motor bakım testi
 *   - STOP / 0 / S                           -> ACİL DURDUR (Tüm motorları anında kes)
 *   - PING                                   -> PONG yanıtı döner
 *   - STATUS                                 -> Anlık motor durumunu döner
 *   - PROFILE                                -> Sabit saha profili kimliğini döner
 *   - 1 / 2 / 3 / 4 / 5                      -> Menü hızlı test komutları
 * ============================================================================
 */

#include <Arduino.h>
#include <stdlib.h>

// ----------------------------------------------------------------------------
// Pin Tanımlamaları
// ----------------------------------------------------------------------------
const uint8_t PIN_M1_PUL = 2;  // 1. Motor (Pan) PUL+
const uint8_t PIN_M1_DIR = 3;  // 1. Motor (Pan) DIR+
const uint8_t PIN_M2_PUL = 4;  // 2. Motor (Tilt) PUL+
const uint8_t PIN_M2_DIR = 5;  // 2. Motor (Tilt) DIR+
const uint8_t PIN_LED_STATUS = 13;

// Backend, fiziksel çıkıştan önce bu kimliği PING/PONG ile birlikte doğrular.
const char FIELD_PROFILE[] = "GKK-UNO-DM542-1600PPR-R1";
const uint32_t MIN_STEP_DELAY_US = 80;
const uint32_t MAX_STEP_DELAY_US = 1000000UL;
const uint32_t MAX_STEP_COUNT = 1600UL;
const uint32_t MAX_RUN_DURATION_SEC = 15UL;
const uint32_t MAX_RUN_SPEED_HZ = 1250UL;
const uint32_t JOG_TIMEOUT_MS = 1000UL;

// ----------------------------------------------------------------------------
// Motor Durum Yapısı
// ----------------------------------------------------------------------------
enum MotorMode {
    MODE_IDLE,
    MODE_TIMED,
    MODE_STEP_COUNT,
    MODE_CONTINUOUS_JOG
};

struct MotorState {
    MotorMode mode;
    uint32_t step_delay_us;  // Yarım periyot bekleme süresi (µs)
    uint32_t last_toggle_us;
    uint32_t steps_remaining;
    uint8_t pul_pin;
    uint8_t dir_pin;
    bool pul_level;
    bool dir_cw;
};

// Varsayılan: 800 us gecikme (1600us tam periyot -> 625 Hz adım frekansı)
MotorState m1 = { MODE_IDLE, 800, 0, 0, PIN_M1_PUL, PIN_M1_DIR, false, true };
MotorState m2 = { MODE_IDLE, 800, 0, 0, PIN_M2_PUL, PIN_M2_DIR, false, true };

uint32_t run_duration_ms = 0;
uint32_t run_start_ms = 0;
uint32_t jog_deadline_ms = 0;

const uint8_t CMD_BUFFER_SIZE = 64;
char cmd_buffer[CMD_BUFFER_SIZE];
uint8_t cmd_index = 0;
bool cmd_overflow = false;

void printMenu();
void stopAllMotors();
void parseAndExecuteCommand(char* cmd);
void startMotion(bool enable_m1, bool enable_m2, uint32_t duration_sec, uint32_t delay_us, bool cw, const char* label);
void startStepMotion(bool enable_m1, bool enable_m2, uint32_t steps_m1, uint32_t steps_m2, uint32_t delay_us, bool cw_m1, bool cw_m2);
void startJogMotion(bool enable_m1, bool enable_m2, uint32_t delay_us, bool cw_m1, bool cw_m2);
bool parseBoundedUnsigned(const char* value, uint32_t minimum, uint32_t maximum, uint32_t* output);
bool parseDirection(char* value, bool* cw);
bool timeReached(uint32_t now, uint32_t deadline);

void printMenu() {
    Serial.println();
    Serial.println(F("======================================================"));
    Serial.println(F("    GÖKKALKAN - ARDUINO UNO ÇİFT MOTOR KONTROLÜ (v2)  "));
    Serial.println(F("======================================================"));
    Serial.println(F("  [1] -> 1. Motoru Oynat (PAN  - Pin 2/3) [15 sn, CW]"));
    Serial.println(F("  [2] -> 2. Motoru Oynat (TILT - Pin 4/5) [15 sn, CW]"));
    Serial.println(F("  [3] -> İki Motoru Birlikte Oynat        [15 sn, CW]"));
    Serial.println(F("  [4] -> 1. Motor Ters Yön                [15 sn, CCW]"));
    Serial.println(F("  [5] -> 2. Motor Ters Yön                [15 sn, CCW]"));
    Serial.println(F("  [0] veya [S] -> ACİL DURDUR (STOP)"));
    Serial.println(F("  [M] -> Menüyü Tekrar Göster"));
    Serial.println(F("  --- Sınırlı bakım protokolü aktif ---"));
    Serial.println(F("  STEP_PAN <adim> <us> <CW/CCW> | STEP_TILT <adim> <us> <CW/CCW>"));
    Serial.println(F("  PROFILE -> Gerekli saha profili kimliğini gösterir"));
    Serial.println(F("======================================================"));
    Serial.println(F("Seçiminizi veya komutunuzu yazıp Enter'a basın:"));
    Serial.println();
}

bool parseBoundedUnsigned(const char* value, uint32_t minimum, uint32_t maximum, uint32_t* output) {
    if (value == NULL || *value == '\0' || *value == '-') return false;

    char* end = NULL;
    unsigned long parsed = strtoul(value, &end, 10);
    if (end == value || *end != '\0' || parsed < minimum || parsed > maximum) {
        return false;
    }
    *output = (uint32_t)parsed;
    return true;
}

bool parseDirection(char* value, bool* cw) {
    if (value == NULL) return true;
    for (int i = 0; value[i]; i++) value[i] = toupper(value[i]);
    if (strcmp(value, "CW") == 0) {
        *cw = true;
        return true;
    }
    if (strcmp(value, "CCW") == 0) {
        *cw = false;
        return true;
    }
    return false;
}

bool timeReached(uint32_t now, uint32_t deadline) {
    return (int32_t)(now - deadline) >= 0;
}

void setup() {
    pinMode(PIN_M1_PUL, OUTPUT);
    pinMode(PIN_M1_DIR, OUTPUT);
    pinMode(PIN_M2_PUL, OUTPUT);
    pinMode(PIN_M2_DIR, OUTPUT);
    pinMode(PIN_LED_STATUS, OUTPUT);

    digitalWrite(PIN_M1_PUL, LOW);
    digitalWrite(PIN_M1_DIR, LOW);
    digitalWrite(PIN_M2_PUL, LOW);
    digitalWrite(PIN_M2_DIR, LOW);
    digitalWrite(PIN_LED_STATUS, LOW);

    Serial.begin(115200);
    delay(200);
    Serial.print(F("INIT_GOKKALKAN_UNO "));
    Serial.println(FIELD_PROFILE);
    printMenu();
}

void loop() {
    uint32_t now_us = micros();
    uint32_t now_ms = millis();

    // ------------------------------------------------------------------------
    // 1. Motor 1 (PAN - Pin 2/3) Pals Üretimi
    // ------------------------------------------------------------------------
    if (m1.mode != MODE_IDLE) {
        if (now_us - m1.last_toggle_us >= m1.step_delay_us) {
            m1.last_toggle_us = now_us;
            m1.pul_level = !m1.pul_level;
            digitalWrite(PIN_M1_PUL, m1.pul_level ? HIGH : LOW);

            // Adım saymalı modda, her düşen kenarda (tam adımda) sayacı azalt
            if (m1.mode == MODE_STEP_COUNT && !m1.pul_level) {
                if (m1.steps_remaining > 0) {
                    m1.steps_remaining--;
                    if (m1.steps_remaining == 0) {
                        m1.mode = MODE_IDLE;
                        digitalWrite(PIN_M1_PUL, LOW);
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------------
    // 2. Motor 2 (TILT - Pin 4/5) Pals Üretimi
    // ------------------------------------------------------------------------
    if (m2.mode != MODE_IDLE) {
        if (now_us - m2.last_toggle_us >= m2.step_delay_us) {
            m2.last_toggle_us = now_us;
            m2.pul_level = !m2.pul_level;
            digitalWrite(PIN_M2_PUL, m2.pul_level ? HIGH : LOW);

            // Adım saymalı modda, her düşen kenarda (tam adımda) sayacı azalt
            if (m2.mode == MODE_STEP_COUNT && !m2.pul_level) {
                if (m2.steps_remaining > 0) {
                    m2.steps_remaining--;
                    if (m2.steps_remaining == 0) {
                        m2.mode = MODE_IDLE;
                        digitalWrite(PIN_M2_PUL, LOW);
                    }
                }
            }
        }
    }

    // ------------------------------------------------------------------------
    // 3. LED Durumu & Süreli Mod Zaman Aşımı Kontrolü
    // ------------------------------------------------------------------------
    bool is_active = (m1.mode != MODE_IDLE) || (m2.mode != MODE_IDLE);
    digitalWrite(PIN_LED_STATUS, is_active ? HIGH : LOW);

    if (
        jog_deadline_ms > 0
        && (m1.mode == MODE_CONTINUOUS_JOG || m2.mode == MODE_CONTINUOUS_JOG)
        && timeReached(now_ms, jog_deadline_ms)
    ) {
        stopAllMotors();
        Serial.println(F("ERR JOG_TIMEOUT_STOPPED"));
    }

    if (run_duration_ms > 0 && (m1.mode == MODE_TIMED || m2.mode == MODE_TIMED)) {
        uint32_t elapsed = now_ms - run_start_ms;
        if (elapsed >= run_duration_ms) {
            stopAllMotors();
            Serial.println(F("OK COMPLETED"));
        }
    }

    // ------------------------------------------------------------------------
    // 4. Seri Porttan Komut Okuma (Non-blocking)
    // ------------------------------------------------------------------------
    while (Serial.available() > 0) {
        char c = (char)Serial.read();

        if (c == '\n' || c == '\r') {
            if (cmd_overflow) {
                Serial.println(F("ERR CMD_TOO_LONG"));
                cmd_overflow = false;
                cmd_index = 0;
            } else if (cmd_index > 0) {
                cmd_buffer[cmd_index] = '\0';
                parseAndExecuteCommand(cmd_buffer);
                cmd_index = 0;
            }
        } else {
            if (cmd_index < CMD_BUFFER_SIZE - 1) {
                cmd_buffer[cmd_index++] = c;
            } else {
                cmd_overflow = true;
            }
        }
    }
}

void startMotion(bool enable_m1, bool enable_m2, uint32_t duration_sec, uint32_t delay_us, bool cw, const char* label) {
    (void)label;  // İnsan-okur menü etiketi; protokol yanıtına yazılmaz.
    if (delay_us < MIN_STEP_DELAY_US) delay_us = MIN_STEP_DELAY_US;
    if (delay_us > MAX_STEP_DELAY_US) delay_us = MAX_STEP_DELAY_US;
    if (duration_sec < 1) duration_sec = 1;
    if (duration_sec > MAX_RUN_DURATION_SEC) duration_sec = MAX_RUN_DURATION_SEC;

    uint32_t now_us = micros();
    uint32_t now_ms = millis();

    if (enable_m1) {
        m1.mode = MODE_TIMED;
        m1.step_delay_us = delay_us;
        m1.last_toggle_us = now_us;
        m1.pul_level = false;
        m1.dir_cw = cw;
        digitalWrite(PIN_M1_DIR, cw ? HIGH : LOW);
        digitalWrite(PIN_M1_PUL, LOW);
    } else {
        m1.mode = MODE_IDLE;
        digitalWrite(PIN_M1_PUL, LOW);
    }

    if (enable_m2) {
        m2.mode = MODE_TIMED;
        m2.step_delay_us = delay_us;
        m2.last_toggle_us = now_us;
        m2.pul_level = false;
        m2.dir_cw = cw;
        digitalWrite(PIN_M2_DIR, cw ? HIGH : LOW);
        digitalWrite(PIN_M2_PUL, LOW);
    } else {
        m2.mode = MODE_IDLE;
        digitalWrite(PIN_M2_PUL, LOW);
    }

    delayMicroseconds(20);

    run_duration_ms = duration_sec * 1000UL;
    run_start_ms = now_ms;
    jog_deadline_ms = 0;
}

void startStepMotion(bool enable_m1, bool enable_m2, uint32_t steps_m1, uint32_t steps_m2, uint32_t delay_us, bool cw_m1, bool cw_m2) {
    if (delay_us < MIN_STEP_DELAY_US) delay_us = MIN_STEP_DELAY_US;
    if (delay_us > MAX_STEP_DELAY_US) delay_us = MAX_STEP_DELAY_US;

    uint32_t now_us = micros();

    if (enable_m1 && steps_m1 > 0) {
        m1.mode = MODE_STEP_COUNT;
        m1.steps_remaining = steps_m1;
        m1.step_delay_us = delay_us;
        m1.last_toggle_us = now_us;
        m1.pul_level = false;
        m1.dir_cw = cw_m1;
        digitalWrite(PIN_M1_DIR, cw_m1 ? HIGH : LOW);
        digitalWrite(PIN_M1_PUL, LOW);
    } else {
        m1.mode = MODE_IDLE;
        digitalWrite(PIN_M1_PUL, LOW);
    }

    if (enable_m2 && steps_m2 > 0) {
        m2.mode = MODE_STEP_COUNT;
        m2.steps_remaining = steps_m2;
        m2.step_delay_us = delay_us;
        m2.last_toggle_us = now_us;
        m2.pul_level = false;
        m2.dir_cw = cw_m2;
        digitalWrite(PIN_M2_DIR, cw_m2 ? HIGH : LOW);
        digitalWrite(PIN_M2_PUL, LOW);
    } else {
        m2.mode = MODE_IDLE;
        digitalWrite(PIN_M2_PUL, LOW);
    }

    run_duration_ms = 0;
    jog_deadline_ms = 0;
    delayMicroseconds(20);
}

void startJogMotion(bool enable_m1, bool enable_m2, uint32_t delay_us, bool cw_m1, bool cw_m2) {
    if (delay_us < MIN_STEP_DELAY_US) delay_us = MIN_STEP_DELAY_US;
    if (delay_us > MAX_STEP_DELAY_US) delay_us = MAX_STEP_DELAY_US;

    uint32_t now_us = micros();

    if (enable_m1) {
        m1.mode = MODE_CONTINUOUS_JOG;
        m1.step_delay_us = delay_us;
        m1.last_toggle_us = now_us;
        m1.pul_level = false;
        m1.dir_cw = cw_m1;
        digitalWrite(PIN_M1_DIR, cw_m1 ? HIGH : LOW);
        digitalWrite(PIN_M1_PUL, LOW);
    } else {
        m1.mode = MODE_IDLE;
        digitalWrite(PIN_M1_PUL, LOW);
    }

    if (enable_m2) {
        m2.mode = MODE_CONTINUOUS_JOG;
        m2.step_delay_us = delay_us;
        m2.last_toggle_us = now_us;
        m2.pul_level = false;
        m2.dir_cw = cw_m2;
        digitalWrite(PIN_M2_DIR, cw_m2 ? HIGH : LOW);
        digitalWrite(PIN_M2_PUL, LOW);
    } else {
        m2.mode = MODE_IDLE;
        digitalWrite(PIN_M2_PUL, LOW);
    }

    run_duration_ms = 0;
    jog_deadline_ms = millis() + JOG_TIMEOUT_MS;
    delayMicroseconds(20);
}

void stopAllMotors() {
    m1.mode = MODE_IDLE;
    m2.mode = MODE_IDLE;
    m1.steps_remaining = 0;
    m2.steps_remaining = 0;
    run_duration_ms = 0;
    jog_deadline_ms = 0;

    digitalWrite(PIN_M1_PUL, LOW);
    digitalWrite(PIN_M2_PUL, LOW);
    digitalWrite(PIN_LED_STATUS, LOW);
}

void parseAndExecuteCommand(char* cmd) {
    while (*cmd == ' ' || *cmd == '\t') cmd++;
    if (*cmd == '\0') return;

    // --- TEK TUŞLU MENÜ SEÇİMLERİ ---
    if (strcmp(cmd, "1") == 0) {
        startMotion(true, false, 15, 800, true, "1. MOTOR (PAN - Pin 2/3)");
        Serial.println(F("OK RUNNING PAN 15s 800us CW"));
        return;
    }
    if (strcmp(cmd, "2") == 0) {
        startMotion(false, true, 15, 800, true, "2. MOTOR (TILT - Pin 4/5)");
        Serial.println(F("OK RUNNING TILT 15s 800us CW"));
        return;
    }
    if (strcmp(cmd, "3") == 0) {
        startMotion(true, true, 15, 800, true, "HER İKİ MOTOR (1. ve 2.)");
        Serial.println(F("OK RUNNING BOTH 15s 800us CW"));
        return;
    }
    if (strcmp(cmd, "4") == 0) {
        startMotion(true, false, 15, 800, false, "1. MOTOR TERS YÖN (PAN CCW)");
        Serial.println(F("OK RUNNING PAN 15s 800us CCW"));
        return;
    }
    if (strcmp(cmd, "5") == 0) {
        startMotion(false, true, 15, 800, false, "2. MOTOR TERS YÖN (TILT CCW)");
        Serial.println(F("OK RUNNING TILT 15s 800us CCW"));
        return;
    }
    if (strcmp(cmd, "0") == 0 || strcasecmp(cmd, "S") == 0 || strcasecmp(cmd, "STOP") == 0 || strcasecmp(cmd, "HALT") == 0) {
        stopAllMotors();
        Serial.println(F("\n[!] ACİL DURDURULDU (STOP)"));
        Serial.println(F("OK STOPPED"));
        return;
    }
    if (strcasecmp(cmd, "M") == 0 || strcasecmp(cmd, "MENU") == 0 || strcmp(cmd, "?") == 0) {
        printMenu();
        return;
    }

    // --- PROTOKOL KOMUTLARI ---
    char* token = strtok(cmd, " \t");
    if (token == NULL) return;

    for (int i = 0; token[i]; i++) token[i] = toupper(token[i]);

    if (strcmp(token, "PING") == 0) {
        if (strtok(NULL, " \t") != NULL) {
            Serial.println(F("ERR PING_ARGUMENTS"));
        } else {
            Serial.println(F("PONG"));
        }
        return;
    }

    if (strcmp(token, "PROFILE") == 0) {
        if (strtok(NULL, " \t") != NULL) {
            Serial.println(F("ERR PROFILE_ARGUMENTS"));
        } else {
            Serial.print(F("PROFILE "));
            Serial.println(FIELD_PROFILE);
        }
        return;
    }

    if (strcmp(token, "STATUS") == 0) {
        if (strtok(NULL, " \t") != NULL) {
            Serial.println(F("ERR STATUS_ARGUMENTS"));
            return;
        }
        bool m1_act = (m1.mode != MODE_IDLE);
        bool m2_act = (m2.mode != MODE_IDLE);
        if (m1_act || m2_act) {
            Serial.print(F("STATUS RUNNING PROFILE="));
            Serial.print(FIELD_PROFILE);
            Serial.print(F(" M1="));
            Serial.print(m1_act ? "1" : "0");
            Serial.print(F(" M2="));
            Serial.println(m2_act ? "1" : "0");
        } else {
            Serial.print(F("STATUS IDLE PROFILE="));
            Serial.println(FIELD_PROFILE);
        }
        return;
    }

    bool is_step_pan = strcmp(token, "STEP_PAN") == 0;
    bool is_step_tilt = strcmp(token, "STEP_TILT") == 0;
    if (is_step_pan || is_step_tilt) {
        char* p_steps = strtok(NULL, " \t");
        char* p_delay = strtok(NULL, " \t");
        char* p_dir = strtok(NULL, " \t");
        if (
            p_steps == NULL || p_delay == NULL || p_dir == NULL || strtok(NULL, " \t") != NULL
        ) {
            Serial.println(F("ERR STEP_ARGUMENTS"));
            return;
        }

        uint32_t steps;
        uint32_t delay_us;
        bool cw;
        if (
            !parseBoundedUnsigned(p_steps, 1, MAX_STEP_COUNT, &steps)
            || !parseBoundedUnsigned(p_delay, MIN_STEP_DELAY_US, MAX_STEP_DELAY_US, &delay_us)
            || !parseDirection(p_dir, &cw)
        ) {
            Serial.println(F("ERR STEP_RANGE_OR_DIRECTION"));
            return;
        }

        startStepMotion(is_step_pan, is_step_tilt, is_step_pan ? steps : 0, is_step_tilt ? steps : 0, delay_us, cw, cw);
        Serial.print(F("OK "));
        Serial.print(is_step_pan ? F("STEP_PAN ") : F("STEP_TILT "));
        Serial.print(steps);
        Serial.print(F(" "));
        Serial.print(delay_us);
        Serial.print(F("us "));
        Serial.println(cw ? F("CW") : F("CCW"));
        return;
    }

    bool is_jog_pan = strcmp(token, "JOG_PAN") == 0;
    bool is_jog_tilt = strcmp(token, "JOG_TILT") == 0;
    if (is_jog_pan || is_jog_tilt) {
        char* p_delay = strtok(NULL, " \t");
        char* p_dir = strtok(NULL, " \t");
        if (strtok(NULL, " \t") != NULL) {
            Serial.println(F("ERR JOG_ARGUMENTS"));
            return;
        }

        uint32_t delay_us = 800;
        bool cw = true;
        if (
            (p_delay != NULL && !parseBoundedUnsigned(p_delay, MIN_STEP_DELAY_US, MAX_STEP_DELAY_US, &delay_us))
            || !parseDirection(p_dir, &cw)
        ) {
            Serial.println(F("ERR JOG_RANGE_OR_DIRECTION"));
            return;
        }

        startJogMotion(is_jog_pan, is_jog_tilt, delay_us, cw, cw);
        Serial.print(F("OK "));
        Serial.print(is_jog_pan ? F("JOG_PAN ") : F("JOG_TILT "));
        Serial.print(delay_us);
        Serial.print(F("us "));
        Serial.print(cw ? F("CW") : F("CCW"));
        Serial.print(F(" WATCHDOG_MS="));
        Serial.println(JOG_TIMEOUT_MS);
        return;
    }

    bool is_run = strcmp(token, "RUN") == 0;
    bool is_run_pan = strcmp(token, "RUN_PAN") == 0;
    bool is_run_tilt = strcmp(token, "RUN_TILT") == 0;
    if (is_run || is_run_pan || is_run_tilt) {
        char* p_duration = strtok(NULL, " \t");
        char* p_speed = strtok(NULL, " \t");
        char* p_dir = strtok(NULL, " \t");
        if (
            p_duration == NULL || p_speed == NULL || (p_dir != NULL && strtok(NULL, " \t") != NULL)
        ) {
            Serial.println(F("ERR RUN_ARGUMENTS"));
            return;
        }

        uint32_t duration_sec;
        uint32_t speed_hz;
        bool cw = true;
        if (
            !parseBoundedUnsigned(p_duration, 1, MAX_RUN_DURATION_SEC, &duration_sec)
            || !parseBoundedUnsigned(p_speed, 1, MAX_RUN_SPEED_HZ, &speed_hz)
            || !parseDirection(p_dir, &cw)
        ) {
            Serial.println(F("ERR RUN_RANGE_OR_DIRECTION"));
            return;
        }

        uint32_t delay_us = 1000000UL / (2UL * speed_hz);
        const bool enable_m1 = is_run || is_run_pan;
        const bool enable_m2 = is_run || is_run_tilt;
        const char* label = enable_m1 && enable_m2 ? "HER İKİ MOTOR" : (enable_m1 ? "1. MOTOR (PAN)" : "2. MOTOR (TILT)");
        startMotion(enable_m1, enable_m2, duration_sec, delay_us, cw, label);

        Serial.print(F("OK RUNNING "));
        if (enable_m1 && enable_m2) Serial.print(F("BOTH"));
        else if (enable_m1) Serial.print(F("PAN"));
        else Serial.print(F("TILT"));
        Serial.print(F(" "));
        Serial.print(duration_sec);
        Serial.print(F("s "));
        Serial.print(speed_hz);
        Serial.print(F("Hz "));
        Serial.println(cw ? F("CW") : F("CCW"));
        return;
    }

    Serial.print(F("ERR UNKNOWN_COMMAND "));
    Serial.println(token);
}
