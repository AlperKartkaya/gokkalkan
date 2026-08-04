"""AI HAT+ donanım keşfi için bağımlılıksız entegrasyon sınırı.

Bu modül model çıkarımı yaptığını iddia etmez. Hailo-8 donanımının işletim
sistemi tarafından görüldüğünü ve isteğe bağlı HEF model artefaktının mevcut
olduğunu ayrı ayrı raporlar. Gerçek detector/classifier, doğrulanmış model
artefaktı seçildiğinde bu sınırın arkasına bağlanacaktır.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any, Callable, Protocol


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


class AcceleratorProbe(Protocol):
    """Perception köprüsünün gerçek veya test sağlık sağlayıcısı sınırı."""

    def health(self, *, force: bool = False) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class AcceleratorHealth:
    accelerator: str
    chip: str
    tops: int
    hardware_ready: bool
    model_ready: bool
    inference_ready: bool
    model_path: str | None
    status: str
    detail: str
    checked_monotonic_s: float

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return {
            "accelerator": data["accelerator"],
            "chip": data["chip"],
            "tops": data["tops"],
            "hardwareReady": data["hardware_ready"],
            "modelReady": data["model_ready"],
            "inferenceReady": data["inference_ready"],
            "modelPath": data["model_path"],
            "status": data["status"],
            "detail": data["detail"],
            "checkedMonotonicS": data["checked_monotonic_s"],
        }


class Hailo8Accelerator:
    """Raspberry Pi AI HAT+ 26 TOPS (Hailo-8) sağlık probu.

    `hailortcli fw-control identify` çıktısı Hailo-8L yerine Hailo-8 olduğunu
    doğrular. Model yolu verilmişse HEF dosyasının varlığı ayrıca raporlanır;
    donanım sağlığı ile model hazırlığı birbirine karıştırılmaz.
    """

    def __init__(
        self,
        model_path: str | Path | None = None,
        *,
        runner: CommandRunner = subprocess.run,
        executable_resolver: Callable[[str], str | None] = shutil.which,
        cache_ttl_s: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.model_path = None if model_path is None else Path(model_path)
        self._runner = runner
        self._resolve = executable_resolver
        self._cache_ttl_s = max(0.0, cache_ttl_s)
        self._clock = clock
        self._cached: AcceleratorHealth | None = None

    def health(self, *, force: bool = False) -> dict[str, Any]:
        now = self._clock()
        if (
            not force
            and self._cached is not None
            and now - self._cached.checked_monotonic_s <= self._cache_ttl_s
        ):
            return self._cached.to_dict()

        model_ready = self.model_path is not None and self.model_path.is_file()
        executable = self._resolve("hailortcli")
        if executable is None:
            status = AcceleratorHealth(
                accelerator="Raspberry Pi AI HAT+ 26 TOPS",
                chip="Hailo-8",
                tops=26,
                hardware_ready=False,
                model_ready=model_ready,
                inference_ready=False,
                model_path=None if self.model_path is None else str(self.model_path),
                status="CLI_MISSING",
                detail="hailortcli bulunamadı; hailo-all kurulumu doğrulanmalı",
                checked_monotonic_s=now,
            )
            self._cached = status
            return status.to_dict()

        try:
            result = self._runner(
                [executable, "fw-control", "identify"],
                capture_output=True,
                text=True,
                check=False,
                timeout=5.0,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            status = AcceleratorHealth(
                accelerator="Raspberry Pi AI HAT+ 26 TOPS",
                chip="Hailo-8",
                tops=26,
                hardware_ready=False,
                model_ready=model_ready,
                inference_ready=False,
                model_path=None if self.model_path is None else str(self.model_path),
                status="PROBE_ERROR",
                detail=str(exc),
                checked_monotonic_s=now,
            )
            self._cached = status
            return status.to_dict()

        output = f"{result.stdout}\n{result.stderr}".upper()
        is_hailo8 = (
            result.returncode == 0
            and (
                "BOARD NAME: HAILO-8" in output
                or "DEVICE ARCHITECTURE: HAILO8" in output
            )
            and "HAILO-8L" not in output
            and "HAILO8L" not in output
        )
        status_name = "READY" if is_hailo8 else "WRONG_OR_MISSING_DEVICE"
        detail = (
            "Hailo-8 aygıtı doğrulandı"
            if is_hailo8
            else "26 TOPS Hailo-8 kimliği doğrulanamadı"
        )
        status = AcceleratorHealth(
            accelerator="Raspberry Pi AI HAT+ 26 TOPS",
            chip="Hailo-8",
            tops=26,
            hardware_ready=is_hailo8,
            model_ready=model_ready,
            inference_ready=is_hailo8 and model_ready,
            model_path=None if self.model_path is None else str(self.model_path),
            status=status_name,
            detail=detail,
            checked_monotonic_s=now,
        )
        self._cached = status
        return status.to_dict()
