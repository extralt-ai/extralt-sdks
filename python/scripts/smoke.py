"""Exercises an installed `extralt` without the dev dependencies; run by check_package.py."""

from __future__ import annotations

import importlib.metadata
import importlib.resources

import extralt


def main() -> None:
    assert extralt.__version__ == importlib.metadata.version("extralt")
    assert importlib.resources.files("extralt").joinpath("py.typed").is_file()
    print(f"extralt {extralt.__version__} installs and imports")


if __name__ == "__main__":
    main()
