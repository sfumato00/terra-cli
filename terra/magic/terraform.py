from __future__ import annotations

import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from IPython.core.magic import Magics, cell_magic, magics_class

from terra.load.local import plan as terra_load_plan

if TYPE_CHECKING:
    from terra.schema.plan import Plan


@magics_class
class TerraformMagic(Magics):  # type: ignore[misc]
    """IPython cell magic that runs terraform commands and binds the result Plan."""

    def _parse_line(self, line: str) -> tuple[str, list[str]]:
        """Return (var_name, remaining_terraform_args) from the magic line."""
        parts = shlex.split(line)
        var_name = "_plan"
        remaining: list[str] = []
        i = 0
        while i < len(parts):
            if parts[i] == "--var" and i + 1 < len(parts):
                var_name = parts[i + 1]
                i += 2
            else:
                remaining.append(parts[i])
                i += 1
        return var_name, remaining

    @cell_magic
    def terraform(self, line: str, cell: str) -> None:  # noqa: ARG002
        var_name, args = self._parse_line(line)

        if not shutil.which("terraform"):
            print("Error: 'terraform' not found on PATH", file=sys.stderr)
            return

        is_plan = bool(args) and args[0] == "plan"

        out_path: Path | None = None
        for arg in args:
            if arg.startswith("-out="):
                out_path = Path(arg[5:])
            elif arg.startswith("--out="):
                out_path = Path(arg[6:])

        cmd = ["terraform"] + args
        print(f"$ {' '.join(cmd)}")

        result = subprocess.run(cmd, capture_output=True, text=True)

        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr, file=sys.stderr)

        if result.returncode != 0:
            return

        if is_plan and out_path is not None:
            try:
                plan: Plan = terra_load_plan(out_path)
                if self.shell is not None:
                    self.shell.user_ns[var_name] = plan
                    print(f"Plan object bound to '{var_name}'")
            except Exception as exc:  # noqa: BLE001
                print(f"Warning: could not parse plan: {exc}", file=sys.stderr)
