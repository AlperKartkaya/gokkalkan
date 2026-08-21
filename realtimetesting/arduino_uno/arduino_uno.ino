/*
 * ============================================================================
 * Gökkalkan - Arduino Uno & DM542 Çift Motor Sürücü Firmware (v2.0)
 * ============================================================================
 * 
 * Pin Haritası (DM542 Sürücüler ile Test Edilmiş):
 *   - Pin 2 : 1. Motor (PAN)  PUL+ (Üzerinde 2 yazan klemens/delik)
 *   - Pin 3 : 1. Motor (PAN)  DIR+ (Üzerinde 3 yazan klemens/delik)
 *   - Pin 4 : 2. Motor (TILT) PUL+ (Üzerinde 4 yazan klemens/delik)
 *   - Pin 5 : 2. Motor (TILT) DIR+ (Üzerinde 5 yazan klemens/delik)
 *   - GND   : Her iki DM542'nin PUL- ve DIR- uçlarına (Ortak Katot)
 *   - ENA   : Boş bırakılmalıdır (Sürücü dahili olarak devrededir)
 * 
 * Desteklenen Protokol Komutları (115200 Baud):
 *   - STEP_PAN <steps> [delay_us] [CW/CCW]   -> Hassas Pan Adım Sürüşü (WASD için)
 *   - STEP_TILT <steps> [delay_us] [CW/CCW]  -> Hassas Tilt Adım Sürüşü (WASD için)
 *   - JOG_PAN [delay_us] [CW/CCW]            -> Kesintisiz Pan Sürüşü
 *   - JOG_TILT [delay_us] [CW/CCW]           -> Kesintisiz Tilt Sürüşü
 *   - RUN_PAN <sec> [delay_us] [CW/CCW]      -> Süreli Pan Çalıştırma
 *   - RUN_TILT <sec> [delay_us] [CW/CCW]     -> Süreli Tilt Çalıştırma
 *   - RUN <sec> [delay_us] [CW/CCW]          -> Her İki Motoru Birlikte Çalıştırma
 *   - STOP / 0 / S                           -> ACİL DURDUR (Tüm motorları anında kes)
 *   - PING                                   -> PONG yanıtı döner
 *   - STATUS                                 -> Anlık motor durumunu döner
 *   - 1 / 2 / 3 / 4 / 5                      -> Menü hızlı test komutları
 * ============================================================================
 */

#include <Arduino.h>

// ----------------------------------------------------------------------------
// Pin Tanımlamaları
// ----------------------------------------------------------------------------
const uint8_t PIN_M1_PUL = 2;  // 1. Motor (Pan) PUL+
const uint8_t PIN_M1_DIR = 3;  // 1. Motor (Pan) DIR+
const uint8_t PIN_M2_PUL = 4;  // 2. Motor (Tilt) PUL+
const uint8_t PIN_M2_DIR = 5;  // 2. Motor (Tilt) DIR+
const uint8_t PIN_LED_STATUS = 13;

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
uint32_t last_status_print_ms = 0;

const uint8_t CMD_BUFFER_SIZE = 64;
char cmd_buffer[CMD_BUFFER_SIZE];
uint8_t cmd_index = 0;

void printMenu();
void stopAllMotors();
void parseAndExecuteCommand(char* cmd);
void startMotion(bool enable_m1, bool enable_m2, uint32_t duration_sec, uint32_t delay_us, bool cw, const char* label);
void startStepMotion(bool enable_m1, bool enable_m2, uint32_t steps_m1, uint32_t steps_m2, uint32_t delay_us, bool cw_m1, bool cw_m2);
void startJogMotion(bool enable_m1, bool enable_m2, uint32_t delay_us, bool cw_m1, bool cw_m2);

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
    Serial.println(F("  --- WASD & Step Protokol Komutları Aktif ---"));
    Serial.println(F("  STEP_PAN <adim> [us] [CW/CCW] | STEP_TILT <adim>"));
    Serial.println(F("======================================================"));
    Serial.println(F("Seçiminizi veya komutunuzu yazıp Enter'a basın:"));
    Serial.println();
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

    if (run_duration_ms > 0 && (m1.mode == MODE_TIMED || m2.mode == MODE_TIMED)) {
        uint32_t elapsed = now_ms - run_start_ms;
        if (elapsed >= run_duration_ms) {
            stopAllMotors();
            Serial.println(F("\n[+] HAREKET TAMAMLANDI!"));
            Serial.println(F("OK COMPLETED"));
        } else if (now_ms - last_status_print_ms >= 2000) {
            last_status_print_ms = now_ms;
            uint32_t remaining = (run_duration_ms - elapsed) / 1000UL;
            Serial.print(F("[*] Calisiyor... Kalan Sure: "));
            Serial.print(remaining);
            Serial.println(F(" sn (Durdurmak icin 0 veya S)"));
        }
    }

    // ------------------------------------------------------------------------
    // 4. Seri Porttan Komut Okuma (Non-blocking)
    // ------------------------------------------------------------------------
    while (Serial.available() > 0) {
        char c = (char)Serial.read();

        if (c == '\n' || c == '\r') {
            if (cmd_index > 0) {
                cmd_buffer[cmd_index] = '\0';
                parseAndExecuteCommand(cmd_buffer);
                cmd_index = 0;
            }
        } else {
            if (cmd_index < CMD_BUFFER_SIZE - 1) {
                cmd_buffer[cmd_index++] = c;
            }
        }
    }
}

void startMotion(bool enable_m1, bool enable_m2, uint32_t duration_sec, uint32_t delay_us, bool cw, const char* label) {
    if (delay_us < 80) delay_us = 80;
    if (delay_us > 10000) delay_us = 10000;
    if (duration_sec < 1) duration_sec = 1;

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
    last_status_print_ms = now_ms;

    Serial.println();
    Serial.print(F(">>> BASLATILDI: "));
    Serial.println(label);
    Serial.print(F("    Sure: "));
    Serial.print(duration_sec);
    Serial.print(F(" sn | Gecikme: "));
    Serial.print(delay_us);
    Serial.println(F(" us"));
}

void startStepMotion(bool enable_m1, bool enable_m2, uint32_t steps_m1, uint32_t steps_m2, uint32_t delay_us, bool cw_m1, bool cw_m2) {
    if (delay_us < 80) delay_us = 80;
    if (delay_us > 10000) delay_us = 10000;

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
    delayMicroseconds(20);
}

void startJogMotion(bool enable_m1, bool enable_m2, uint32_t delay_us, bool cw_m1, bool cw_m2) {
    if (delay_us < 80) delay_us = 80;
    if (delay_us > 10000) delay_us = 10000;

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
    delayMicroseconds(20);
}

void stopAllMotors() {
    m1.mode = MODE_IDLE;
    m2.mode = MODE_IDLE;
    m1.steps_remaining = 0;
    m2.steps_remaining = 0;
    run_duration_ms = 0;

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
    char* token = strtok(cmd, " ");
    if (token == NULL) return;

    for (int i = 0; token[i]; i++) token[i] = toupper(token[i]);

    if (strcmp(token, "PING") == 0) {
        Serial.println(F("PONG"));
    }
    else if (strcmp(token, "STATUS") == 0) {
        bool m1_act = (m1.mode != MODE_IDLE);
        bool m2_act = (m2.mode != MODE_IDLE);
        if (m1_act || m2_act) {
            Serial.print(F("STATUS: RUNNING | M1="));
            Serial.print(m1_act ? "1" : "0");
            Serial.print(F(" (rem="));
            Serial.print(m1.steps_remaining);
            Serial.print(F(") M2="));
            Serial.print(m2_act ? "1" : "0");
            Serial.print(F(" (rem="));
            Serial.print(m2.steps_remaining);
            Serial.println(F(")"));
        } else {
            Serial.println(F("STATUS: IDLE"));
        }
    }
    // ------------------------------------------------------------------------
    // STEP_PAN <steps> [delay_us] [CW/CCW]
    // ------------------------------------------------------------------------
    else if (strcmp(token, "STEP_PAN") == 0) {
        uint32_t steps = 50;
        uint32_t delay_us = 800;
        bool cw = true;

        char* p_steps = strtok(NULL, " ");
        char* p_spd = strtok(NULL, " ");
        char* p_dir = strtok(NULL, " ");

        if (p_steps != NULL) steps = atol(p_steps);
        if (p_spd != NULL) delay_us = atol(p_spd);
        if (p_dir != NULL) {
            for (int i = 0; p_dir[i]; i++) p_dir[i] = toupper(p_dir[i]);
            if (strcmp(p_dir, "CCW") == 0) cw = false;
        }

        startStepMotion(true, false, steps, 0, delay_us, cw, true);
        Serial.print(F("OK STEP_PAN "));
        Serial.print(steps);
        Serial.print(F(" "));
        Serial.print(delay_us);
        Serial.print(F("us "));
        Serial.println(cw ? F("CW") : F("CCW"));
    }
    // ------------------------------------------------------------------------
    // STEP_TILT <steps> [delay_us] [CW/CCW]
    // ------------------------------------------------------------------------
    else if (strcmp(token, "STEP_TILT") == 0) {
        uint32_t steps = 50;
        uint32_t delay_us = 800;
        bool cw = true;

        char* p_steps = strtok(NULL, " ");
        char* p_spd = strtok(NULL, " ");
        char* p_dir = strtok(NULL, " ");

        if (p_steps != NULL) steps = atol(p_steps);
        if (p_spd != NULL) delay_us = atol(p_spd);
        if (p_dir != NULL) {
            for (int i = 0; p_dir[i]; i++) p_dir[i] = toupper(p_dir[i]);
            if (strcmp(p_dir, "CCW") == 0) cw = false;
        }

        startStepMotion(false, true, 0, steps, delay_us, true, cw);
        Serial.print(F("OK STEP_TILT "));
        Serial.print(steps);
        Serial.print(F(" "));
        Serial.print(delay_us);
        Serial.print(F("us "));
        Serial.println(cw ? F("CW") : F("CCW"));
    }
    // ------------------------------------------------------------------------
    // JOG_PAN [delay_us] [CW/CCW]
    // ------------------------------------------------------------------------
    else if (strcmp(token, "JOG_PAN") == 0) {
        uint32_t delay_us = 800;
        bool cw = true;

        char* p_spd = strtok(NULL, " ");
        char* p_dir = strtok(NULL, " ");

        if (p_spd != NULL) delay_us = atol(p_spd);
        if (p_dir != NULL) {
            for (int i = 0; p_dir[i]; i++) p_dir[i] = toupper(p_dir[i]);
            if (strcmp(p_dir, "CCW") == 0) cw = false;
        }

        startJogMotion(true, false, delay_us, cw, true);
        Serial.print(F("OK JOG_PAN "));
        Serial.print(delay_us);
        Serial.print(F("us "));
        Serial.println(cw ? F("CW") : F("CCW"));
    }
    // ------------------------------------------------------------------------
    // JOG_TILT [delay_us] [CW/CCW]
    // ------------------------------------------------------------------------
    else if (strcmp(token, "JOG_TILT") == 0) {
        uint32_t delay_us = 800;
        bool cw = true;

        char* p_spd = strtok(NULL, " ");
        char* p_dir = strtok(NULL, " ");

        if (p_spd != NULL) delay_us = atol(p_spd);
        if (p_dir != NULL) {
            for (int i = 0; p_dir[i]; i++) p_dir[i] = toupper(p_dir[i]);
            if (strcmp(p_dir, "CCW") == 0) cw = false;
        }

        startJogMotion(false, true, delay_us, true, cw);
        Serial.print(F("OK JOG_TILT "));
        Serial.print(delay_us);
        Serial.print(F("us "));
        Serial.println(cw ? F("CW") : F("CCW"));
    }
    // ------------------------------------------------------------------------
    // RUN / RUN_PAN / RUN_TILT <sec> [delay_us/speed] [CW/CCW]
    // ------------------------------------------------------------------------
    else if (strcmp(token, "RUN") == 0 || strcmp(token, "RUN_PAN") == 0 || strcmp(token, "RUN_TILT") == 0) {
        bool enable_m1 = (strcmp(token, "RUN") == 0 || strcmp(token, "RUN_PAN") == 0);
        bool enable_m2 = (strcmp(token, "RUN") == 0 || strcmp(token, "RUN_TILT") == 0);

        uint32_t duration = 15;
        uint32_t delay_us = 800;
        bool cw = true;

        char* p_dur = strtok(NULL, " ");
        char* p_spd = strtok(NULL, " ");
        char* p_dir = strtok(NULL, " ");

        if (p_dur != NULL) duration = atol(p_dur);
        if (p_spd != NULL) {
            uint32_t val = atol(p_spd);
            if (val > 10 && val < 5000) {
                delay_us = 1000000UL / (2UL * val);
            } else if (val >= 80 && val <= 10000) {
                delay_us = val;
            }
        }
        if (p_dir != NULL) {
            for (int i = 0; p_dir[i]; i++) p_dir[i] = toupper(p_dir[i]);
            if (strcmp(p_dir, "CCW") == 0) cw = false;
        }

        const char* lbl = enable_m1 && enable_m2 ? "HER İKİ MOTOR" : (enable_m1 ? "1. MOTOR (PAN)" : "2. MOTOR (TILT)");
        startMotion(enable_m1, enable_m2, duration, delay_us, cw, lbl);

        Serial.print(F("OK RUNNING "));
        if (enable_m1 && enable_m2) Serial.print(F("BOTH"));
        else if (enable_m1) Serial.print(F("PAN"));
        else Serial.print(F("TILT"));

        Serial.print(F(" "));
        Serial.print(duration);
        Serial.print(F("s "));
        Serial.print(delay_us);
        Serial.print(F("us "));
        Serial.println(cw ? F("CW") : F("CCW"));
    }
    else {
        Serial.print(F("ERR: Gecersiz komut ("));
        Serial.print(token);
        Serial.println(F(")"));
    }
}
