# Package mod/bl4ss/ as dist/bl4ss.sdkmod — a zip with a single root folder named like the module (the SDK's loader
# requires exactly one root folder, with no dots in its name, and the file name must match it). Also writes the
# upload archive for Nexus Mods, which only accepts .zip/.7z/.rar/...: dist/bl4ss-<version>-nexus.zip containing
# sdk_mods/bl4ss.sdkmod, so extracting it into the game folder puts the mod in place. Runs on the host Python.
#   python tools\build_sdkmod.py

import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "mod" / "bl4ss"
DIST = ROOT / "dist"
SKIP_DIRS = {"__pycache__"}
SKIP_SUFFIXES = {".pyc", ".pyo"}


def main() -> None:
    DIST.mkdir(exist_ok=True)
    target = DIST / f"{SOURCE.name}.sdkmod"
    files = sorted(p for p in SOURCE.rglob("*")
                   if p.is_file() and not SKIP_DIRS.intersection(p.parts) and p.suffix not in SKIP_SUFFIXES)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for path in files:
            z.write(path, Path(SOURCE.name) / path.relative_to(SOURCE))
    print(f"{target} ({target.stat().st_size} bytes, {len(files)} files)")
    for path in files:
        print(f"  {SOURCE.name}/{path.relative_to(SOURCE).as_posix()}")

    version = tomllib.loads((SOURCE / "pyproject.toml").read_text(encoding="utf-8"))["project"]["version"]
    upload = DIST / f"{SOURCE.name}-{version}-nexus.zip"
    with zipfile.ZipFile(upload, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(target, f"sdk_mods/{target.name}")
    print(f"{upload} ({upload.stat().st_size} bytes): sdk_mods/{target.name}")


if __name__ == "__main__":
    main()
