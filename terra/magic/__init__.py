from terra.magic.terraform import TerraformMagic


def load_ipython_extension(ipython: object) -> None:
    """Register terra IPython magics. Called by %load_ext terra."""
    ipython.register_magics(TerraformMagic)  # type: ignore[union-attr]


__all__ = ["load_ipython_extension"]
