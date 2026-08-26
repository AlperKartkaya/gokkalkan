#!/usr/bin/env bash
# Gökkalkan — Tarihsel CAN regresyonları için sanal arayüz betiği
#
# Yalnız korunmuş CanMcuAdapter/dijital ikiz regresyonlarını çalıştırmak için
# sanal bir CAN ağ arayüzü (vcan0) oluşturur. Aktif Pi–Arduino runtime taşıması
# USB seri'dir; normal HIL için config/runtime/hil.toml içindeki loop:// kullanılır.
#
# Desteklenen platformlar:
#   Linux (Raspberry Pi OS, Ubuntu) — tam destek (vcan0)
#   macOS                           — vcan desteği yok; python-can "virtual" kullanın
#
# Kullanım:
#   bash scripts/setup_virtual_can.sh
#
# Gereksinimleri kaldırmak için:
#   bash scripts/setup_virtual_can.sh --teardown

set -euo pipefail

INTERFACE="vcan0"
TEARDOWN=false

if [[ "${1:-}" == "--teardown" ]]; then
  TEARDOWN=true
fi

# ---------------------------------------------------------------------------
# Platform kontrolü
# ---------------------------------------------------------------------------
if [[ "$(uname)" == "Darwin" ]]; then
  echo "╔══════════════════════════════════════════════════════╗"
  echo "║  macOS: vcan0 desteklenmiyor.                        ║"
  echo "║                                                      ║"
  echo "║  Bunun yerine python-can 'virtual' bus kullanın:     ║"
  echo "║    --channel test --bustype virtual                  ║"
  echo "║                                                      ║"
  echo "║  Simülatör:                                          ║"
  echo "║    python backend/hardware_mock/mcu_simulator.py \\   ║"
  echo "║      --channel test --bustype virtual                ║"
  echo "║                                                      ║"
  echo "║  Aktif USB HIL:                                      ║"
  echo "║    .venv/bin/gokkalkan operator-api --usb-loop      ║"
  echo "╚══════════════════════════════════════════════════════╝"
  exit 0
fi

# ---------------------------------------------------------------------------
# Linux teardown
# ---------------------------------------------------------------------------
if [[ "$TEARDOWN" == true ]]; then
  echo "▶ vcan0 kaldırılıyor..."
  sudo ip link set down "$INTERFACE" 2>/dev/null || true
  sudo ip link delete "$INTERFACE" type vcan 2>/dev/null || true
  echo "✓ $INTERFACE kaldırıldı."
  exit 0
fi

# ---------------------------------------------------------------------------
# Linux kurulum
# ---------------------------------------------------------------------------
echo "▶ vcan kernel modülü yükleniyor..."
if ! lsmod | grep -q "^vcan "; then
  sudo modprobe vcan
  echo "  ✓ vcan modülü yüklendi."
else
  echo "  ✓ vcan modülü zaten yüklü."
fi

echo "▶ $INTERFACE oluşturuluyor..."
if ip link show "$INTERFACE" &>/dev/null; then
  echo "  ✓ $INTERFACE zaten mevcut."
else
  sudo ip link add dev "$INTERFACE" type vcan
  echo "  ✓ $INTERFACE oluşturuldu."
fi

echo "▶ $INTERFACE aktif ediliyor..."
sudo ip link set up "$INTERFACE"
echo "  ✓ $INTERFACE UP."

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║  vcan0 hazır. Aşağıdaki komutlarla test edebilirsiniz:      ║"
echo "║                                                              ║"
echo "║  Terminal 1 — MCU Simülatörü:                               ║"
echo "║    python backend/hardware_mock/mcu_simulator.py \\           ║"
echo "║      --channel vcan0 --bustype socketcan                     ║"
echo "║                                                              ║"
echo "║  Terminal 2 — Tarihsel regresyon testi:                      ║"
echo "║    .venv/bin/python -m pytest tests/test_digital_twin.py      ║"
echo "║                                                              ║"
echo "║  Terminal 3 — İzleme (isteğe bağlı):                        ║"
echo "║    candump vcan0                                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
