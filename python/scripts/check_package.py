"""Builds the distributions and checks them the way users install them.

- the metadata and README render on PyPI (twine check);
- the wheel holds only the package, including its py.typed marker;
- scripts/smoke.py passes from the installed wheel without the dev dependencies, at the declared
  dependency floors on the oldest supported Python and at the latest releases on the newest.

Run `uv run scripts/check_package.py`.
"""

from __future__ import annotations

import re
import subprocess
import tempfile
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OLDEST_PYTHON = "3.11"
NEWEST_PYTHON = "3.14"


def floors() -> list[str]:
    """`httpx>=0.27,<1` becomes `httpx==0.27`."""
    project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    return [re.sub(r">=([^,]+).*", r"==\1", requirement) for requirement in project["dependencies"]]


def run(*command: str) -> None:
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> None:
    with tempfile.TemporaryDirectory() as out:
        run("uv", "build", "--quiet", "--out-dir", out)
        dists = sorted(str(path) for path in Path(out).glob("extralt-*"))
        run("uvx", "twine@6.2.0", "check", "--strict", *dists)

        wheel = next(dist for dist in dists if dist.endswith(".whl"))
        names = zipfile.ZipFile(wheel).namelist()
        assert "extralt/py.typed" in names, "the wheel must ship py.typed"
        stray = [name for name in names if not name.startswith(("extralt/", "extralt-"))]
        assert not stray, f"unexpected files in the wheel: {stray}"

        for python, pins in ((OLDEST_PYTHON, floors()), (NEWEST_PYTHON, [])):
            extras = [argument for pin in pins for argument in ("--with", pin)]
            run(
                "uv", "run", "--isolated", "--no-project", "--python", python,
                "--with", wheel, *extras,
                "python", "-I", str(ROOT / "scripts" / "smoke.py"),
            )  # fmt: skip


if __name__ == "__main__":
    main()
