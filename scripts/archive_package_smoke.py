from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path


def _run(command: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> None:
    subprocess.run(command, cwd=cwd, env=env, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build, install, and import Lineage Lifeboat from a Git archive."
    )
    parser.add_argument(
        "--revision",
        default="HEAD",
        help="Committed Git revision to archive (default: HEAD).",
    )
    args = parser.parse_args()

    repository = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
        ).strip()
    )

    with tempfile.TemporaryDirectory(prefix="lineage-lifeboat-archive-") as temp:
        temp_root = Path(temp)
        archive_path = temp_root / "source.tar"
        source_dir = temp_root / "source"
        wheel_dir = temp_root / "wheel"
        install_dir = temp_root / "install"
        source_dir.mkdir()
        wheel_dir.mkdir()

        _run(
            [
                "git",
                "archive",
                "--format=tar",
                f"--output={archive_path}",
                args.revision,
            ],
            cwd=repository,
        )
        with tarfile.open(archive_path, mode="r") as archive:
            archive.extractall(source_dir, filter="data")

        # Match setuptools' strict README decoding before invoking the build backend.
        (source_dir / "README.md").read_text(encoding="utf-8", errors="strict")

        _run(
            [
                sys.executable,
                "-m",
                "pip",
                "wheel",
                "--no-deps",
                "--no-build-isolation",
                f"--wheel-dir={wheel_dir}",
                str(source_dir),
            ],
            cwd=source_dir,
        )
        wheels = tuple(wheel_dir.glob("lineage_lifeboat-*.whl"))
        if len(wheels) != 1:
            raise RuntimeError(f"expected one Lineage Lifeboat wheel, found {wheels}")

        _run(
            [
                sys.executable,
                "-m",
                "pip",
                "install",
                "--no-deps",
                "--no-index",
                f"--target={install_dir}",
                str(wheels[0]),
            ],
            cwd=source_dir,
        )
        import_env = os.environ.copy()
        import_env["PYTHONPATH"] = str(install_dir)
        _run(
            [
                sys.executable,
                "-c",
                (
                    "import pathlib, lineage_lifeboat; "
                    "module = pathlib.Path(lineage_lifeboat.__file__).resolve(); "
                    "target = pathlib.Path(r'%s').resolve(); "
                    "assert target in module.parents, (module, target); "
                    "print(f'archive-package-import-ok: {module}')"
                )
                % install_dir,
            ],
            cwd=temp_root,
            env=import_env,
        )


if __name__ == "__main__":
    main()
