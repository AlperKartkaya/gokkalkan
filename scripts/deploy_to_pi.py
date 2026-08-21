#!/usr/bin/env python3
"""Deploy Gökkalkan to a Raspberry Pi over SSH.

Cross-platform script that runs on Windows, macOS, and Linux.
It builds the frontend, packages the release tree, transfers it to the Pi,
runs the bootstrap process, and verifies persistent systemd services.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(__file__).resolve().parents[1]
REMOTE_RELEASE = "/tmp/gokkalkan-release"

RELEASE_PATHS = (
    "README.md",
    "pyproject.toml",
    "requirements/backend.lock",
    "backend",
    "config",
    "deploy",
    "docs",
    "firmware",
    "frontend/dist",
    "perception/assets",
    "perception/models",
    "perception/src",
    "release",
    "scripts",
    "realtimetesting",
)

EXCLUDE_EXTENSIONS = {".pyc", ".pyo"}
EXCLUDE_NAMES = {"__pycache__", ".DS_Store"}
TEXT_EXTENSIONS = {
    ".sh",
    ".py",
    ".service",
    ".target",
    ".toml",
    ".lock",
    ".md",
    ".txt",
    ".json",
    ".env",
    ".conf",
    ".ini",
    ".yaml",
    ".yml",
    ".html",
    ".css",
    ".js",
    ".svg",
}


def _add_file_to_tar(tar: tarfile.TarFile, file_path: Path, arcname: str) -> None:
    name = file_path.name
    if name in EXCLUDE_NAMES or any(name.endswith(ext) for ext in EXCLUDE_EXTENSIONS):
        return
    if ".egg-info" in arcname:
        return
    if arcname.startswith("perception/models/") and arcname.endswith(".hef"):
        return

    stat = file_path.stat()
    if arcname.startswith("scripts/") or arcname.endswith(".sh") or arcname.endswith(".py"):
        mode = 0o755
    else:
        mode = 0o644

    suffix = file_path.suffix.lower()
    if suffix in TEXT_EXTENSIONS or name in {"pyproject.toml", "README.md"}:
        try:
            content = file_path.read_bytes().replace(b"\r\n", b"\n")
            tarinfo = tarfile.TarInfo(name=arcname)
            tarinfo.size = len(content)
            tarinfo.mtime = int(stat.st_mtime)
            tarinfo.mode = mode
            tarinfo.type = tarfile.REGTYPE
            tar.addfile(tarinfo, io.BytesIO(content))
            return
        except Exception:
            pass

    tarinfo = tar.gettarinfo(str(file_path), arcname=arcname)
    tarinfo.mode = mode
    with open(file_path, "rb") as f:
        tar.addfile(tarinfo, f)


def _add_path_to_tar(tar: tarfile.TarFile, path: Path, arcname: str) -> None:
    if path.is_file():
        _add_file_to_tar(tar, path, arcname)
    elif path.is_dir():
        for child in sorted(path.iterdir()):
            child_arcname = f"{arcname}/{child.name}".strip("/")
            _add_path_to_tar(tar, child, child_arcname)


def verify_manifest() -> None:
    print("[1/5] Pi manifest kontrol ediliyor...")
    verifier = REPO_ROOT / "scripts" / "verify_pi_manifest.py"
    res = subprocess.run([sys.executable, str(verifier), "--manifest-only"], capture_output=True, text=True)
    if res.returncode != 0:
        print(f"HATA: Manifest doğrulaması başarısız:\n{res.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"  [OK] {res.stdout.strip()}")


def build_frontend(skip_build: bool) -> None:
    dist_index = REPO_ROOT / "frontend" / "dist" / "index.html"
    if skip_build:
        if not dist_index.is_file():
            print("HATA: --skip-build seçildi ancak frontend/dist/index.html bulunamadı.", file=sys.stderr)
            sys.exit(1)
        print("[2/5] Frontend derlemesi atlandı (--skip-build).")
        return

    print("[2/5] Frontend derleniyor (npm run build)...")
    npm_cmd = "npm.cmd" if sys.platform == "win32" else "npm"
    if not shutil.which(npm_cmd):
        npm_cmd = "npm"

    frontend_dir = REPO_ROOT / "frontend"
    ci_res = subprocess.run([npm_cmd, "ci"], cwd=str(frontend_dir), check=False)
    if ci_res.returncode != 0:
        print("UYARI: 'npm ci' başarısız oldu, 'npm install' deneniyor...", file=sys.stderr)
        subprocess.run([npm_cmd, "install"], cwd=str(frontend_dir), check=True)

    subprocess.run([npm_cmd, "run", "build"], cwd=str(frontend_dir), check=True)

    if not dist_index.is_file():
        print("HATA: frontend/dist/index.html oluşturulamadı!", file=sys.stderr)
        sys.exit(1)
    print("  [OK] Frontend başarıyla derlendi.")


def create_release_tarball() -> bytes:
    print("[3/5] Release paketi oluşturuluyor...")
    for rel_path in RELEASE_PATHS:
        full_path = REPO_ROOT / rel_path
        if not full_path.exists():
            print(f"HATA: Gerekli dosya/klasör eksik: {rel_path}", file=sys.stderr)
            sys.exit(1)

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
        for rel_path in RELEASE_PATHS:
            full_path = REPO_ROOT / rel_path
            _add_path_to_tar(tar, full_path, rel_path.replace("\\", "/"))

    tar_bytes = buffer.getvalue()
    size_mb = len(tar_bytes) / (1024 * 1024)
    print(f"  [OK] Release paketi hazırlandı (LF satır sonları normalize edildi): {size_mb:.2f} MB")
    return tar_bytes


def transfer_and_bootstrap(
    host: str,
    tar_bytes: bytes,
    identity: str | None = None,
    hef_path: str | None = None,
    runner_factory: str | None = None,
) -> None:
    print(f"[4/5] Paket SSH üzerinden {host} hedefine aktarılıyor...")
    ssh_base = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
    if identity:
        ssh_base.extend(["-i", identity])

    remote_unpack_cmd = f"mkdir -p '{REMOTE_RELEASE}' && tar -xzf - -C '{REMOTE_RELEASE}'"
    ssh_tar_cmd = [*ssh_base, host, remote_unpack_cmd]

    proc = subprocess.run(ssh_tar_cmd, input=tar_bytes, capture_output=True)
    if proc.returncode != 0:
        err_msg = proc.stderr.decode("utf-8", errors="replace")
        print(f"HATA: SSH aktarımı başarısız oldu:\n{err_msg}", file=sys.stderr)
        print("\nİpucu: Pi'ye SSH anahtarınız ile şifresiz bağlanabildiğinizden emin olun.", file=sys.stderr)
        print("  - Özel bir SSH anahtarınız varsa: --identity <anahtar_dosyasi>", file=sys.stderr)
        print("  - SSH anahtarınızı Pi'ye eklemek için: type ~/.ssh/id_rsa.pub | ssh pi@<ip> \"mkdir -p ~/.ssh && cat >> ~/.ssh/authorized_keys\"", file=sys.stderr)
        sys.exit(1)
    print("  [OK] Dosyalar Raspberry Pi'ye aktarıldı.")

    if hef_path:
        print(f"  -> HEF modeli aktarılıyor: {hef_path}")
        scp_base = ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
        if identity:
            scp_base.extend(["-i", identity])
        scp_cmd = [*scp_base, hef_path, f"{host}:{REMOTE_RELEASE}/perception/models/target_detector.hef"]
        scp_proc = subprocess.run(scp_cmd, capture_output=True)
        if scp_proc.returncode != 0:
            print(f"HATA: HEF modeli kopyalanamadı:\n{scp_proc.stderr.decode('utf-8', errors='replace')}", file=sys.stderr)
            sys.exit(1)
        print("  [OK] HEF modeli aktarıldı.")

    print("[5/5] Raspberry Pi üzerinde bootstrap ve servis kurulumu çalıştırılıyor...")
    remote_setup = f"cd '{REMOTE_RELEASE}' && sudo bash scripts/bootstrap_pi.sh --apply"
    if hef_path and runner_factory:
        remote_setup += (
            f" && printf 'GOKKALKAN_HAILO_BATCH_RUNNER_FACTORY={runner_factory}\\n' | sudo tee /etc/gokkalkan/perception.env >/dev/null"
            f" && sudo chmod 0640 /etc/gokkalkan/perception.env && sudo touch /etc/gokkalkan/enable-perception"
        )

    verify_remote = (
        f"{remote_setup} && "
        "sudo systemctl enable gokkalkan.target && "
        "sudo systemctl restart gokkalkan.target && "
        "curl --fail --silent http://127.0.0.1:8088/health >/dev/null && "
        "curl --fail --silent http://127.0.0.1:4173/healthz >/dev/null && "
        "systemctl is-enabled gokkalkan.target && systemctl is-active gokkalkan.target"
    )

    ssh_exec = ["ssh", "-t"]
    if identity:
        ssh_exec.extend(["-i", identity])
    ssh_exec.extend([host, verify_remote])

    res = subprocess.run(ssh_exec)
    if res.returncode != 0:
        print("HATA: Pi üzerinde bootstrap veya servis aktivasyonu başarısız oldu.", file=sys.stderr)
        sys.exit(res.returncode)

    print("\n=======================================================")
    print("[OK] DAGITIM BASARIYLA TAMAMLANDI!")
    print("Pi servisleri kalicidir; SSH baglantisi kapansa da calismaya devam eder.")
    print("Operator Arayuzu & Kamera Akisi SSH Tuneli:")
    print(f"  ssh -N -L 4173:127.0.0.1:4173 -L 8088:127.0.0.1:8088 -L 8090:127.0.0.1:8090 {host}")
    print("\nTuneli baslattiktan sonra tarayicinizda acin:")
    print("  http://127.0.0.1:4173")
    print("=======================================================")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deploy Gökkalkan workspace to Raspberry Pi")
    parser.add_argument("--host", required=True, help="Pi SSH host (e.g. pi@192.168.1.50)")
    parser.add_argument("--identity", "-i", default=None, help="SSH private key identity file")
    parser.add_argument("--skip-build", action="store_true", help="Skip local frontend build")
    parser.add_argument("--hef", default=None, help="Path to compiled Hailo HEF file")
    parser.add_argument("--runner-factory", default=None, help="Hailo runner factory (module:func)")

    args = parser.parse_args()

    if (args.hef and not args.runner_factory) or (args.runner_factory and not args.hef):
        print("HATA: --hef ve --runner-factory parametreleri birlikte verilmelidir.", file=sys.stderr)
        return 2

    if args.hef and not Path(args.hef).is_file():
        print(f"HATA: HEF dosyası bulunamadı: {args.hef}", file=sys.stderr)
        return 2

    if args.runner_factory and not re.match(r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_]*$", args.runner_factory):
        print(f"HATA: Geçersiz runner factory formatı. Beklenen: modul_adi:fonksiyon_adi", file=sys.stderr)
        return 2

    verify_manifest()
    build_frontend(skip_build=args.skip_build)
    tar_bytes = create_release_tarball()
    transfer_and_bootstrap(
        host=args.host,
        tar_bytes=tar_bytes,
        identity=args.identity,
        hef_path=args.hef,
        runner_factory=args.runner_factory,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
