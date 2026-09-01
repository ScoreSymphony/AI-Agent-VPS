from __future__ import annotations

from pathlib import Path
from shutil import copy2

from setuptools import setup
from setuptools.command.build_py import build_py


class BuildPyWithContracts(build_py):
    def run(self) -> None:
        super().run()
        source = Path(__file__).parent / "platform" / "contracts" / "v1"
        target = Path(self.build_lib) / "scoresymphony_contracts" / "schemas" / "v1"
        target.mkdir(parents=True, exist_ok=True)
        for name in ("command.schema.json", "event.schema.json"):
            copy2(source / name, target / name)


setup(cmdclass={"build_py": BuildPyWithContracts})
