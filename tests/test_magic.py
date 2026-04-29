from __future__ import annotations

from unittest.mock import patch

import pytest

from terra.magic.terraform import TerraformMagic


@pytest.fixture(scope="module")
def ip():
    """Minimal IPython shell instance for magic testing."""
    from IPython.testing.globalipapp import get_ipython

    return get_ipython()


class TestLoadExtension:
    def test_registers_magics(self):
        from unittest.mock import MagicMock

        from terra.magic import load_ipython_extension

        mock_ipython = MagicMock()
        load_ipython_extension(mock_ipython)
        mock_ipython.register_magics.assert_called_once_with(TerraformMagic)


class TestParseLine:
    def _magic(self) -> TerraformMagic:
        return TerraformMagic(shell=None)

    def test_default_var_name(self):
        var_name, args = self._magic()._parse_line("plan -out=tfplan")
        assert var_name == "_plan"
        assert args == ["plan", "-out=tfplan"]

    def test_custom_var_name(self):
        var_name, args = self._magic()._parse_line("plan --var my_plan -out=tfplan")
        assert var_name == "my_plan"
        assert args == ["plan", "-out=tfplan"]

    def test_empty_line(self):
        var_name, args = self._magic()._parse_line("")
        assert var_name == "_plan"
        assert args == []

    def test_subcmd_only(self):
        var_name, args = self._magic()._parse_line("apply tfplan")
        assert var_name == "_plan"
        assert args == ["apply", "tfplan"]


class TestTerraformCellMagic:
    def test_no_terraform_binary_does_not_raise(self):
        magic = TerraformMagic(shell=None)
        with patch("terra.magic.terraform.shutil.which", return_value=None):
            magic.terraform("plan -out=tfplan", "")

    def test_no_terraform_binary_does_not_bind_plan(self, ip):
        ip.user_ns.pop("_plan", None)
        magic = TerraformMagic(shell=ip)
        with patch("terra.magic.terraform.shutil.which", return_value=None):
            magic.terraform("plan -out=tfplan", "")
        assert "_plan" not in ip.user_ns

    def test_failed_terraform_run_does_not_bind_plan(self, ip, tmp_path):
        ip.user_ns.pop("_plan", None)
        magic = TerraformMagic(shell=ip)
        plan_file = tmp_path / "tfplan.bin"
        with (
            patch("terra.magic.terraform.shutil.which", return_value="/usr/bin/terraform"),
            patch("terra.magic.terraform.subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "Error: no configuration files"
            magic.terraform(f"plan -out={plan_file}", "")
        assert "_plan" not in ip.user_ns

    def test_successful_plan_binds_to_default_var(self, ip, tmp_path):
        from terra.schema.plan import Plan

        ip.user_ns.pop("_plan", None)
        magic = TerraformMagic(shell=ip)
        plan_file = tmp_path / "tfplan.bin"
        fake_plan = Plan(format_version="1.2")

        with (
            patch("terra.magic.terraform.shutil.which", return_value="/usr/bin/terraform"),
            patch("terra.magic.terraform.subprocess.run") as mock_run,
            patch("terra.magic.terraform.terra_load_plan", return_value=fake_plan),
        ):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "Plan: 1 to add."
            mock_run.return_value.stderr = ""
            magic.terraform(f"plan -out={plan_file}", "")

        assert ip.user_ns.get("_plan") is fake_plan

    def test_successful_plan_binds_to_custom_var(self, ip, tmp_path):
        from terra.schema.plan import Plan

        ip.user_ns.pop("prod_plan", None)
        magic = TerraformMagic(shell=ip)
        plan_file = tmp_path / "tfplan.bin"
        fake_plan = Plan(format_version="1.2")

        with (
            patch("terra.magic.terraform.shutil.which", return_value="/usr/bin/terraform"),
            patch("terra.magic.terraform.subprocess.run") as mock_run,
            patch("terra.magic.terraform.terra_load_plan", return_value=fake_plan),
        ):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = ""
            magic.terraform(f"plan --var prod_plan -out={plan_file}", "")

        assert ip.user_ns.get("prod_plan") is fake_plan

    def test_non_plan_subcommand_does_not_bind(self, ip):
        ip.user_ns.pop("_plan", None)
        magic = TerraformMagic(shell=ip)
        with (
            patch("terra.magic.terraform.shutil.which", return_value="/usr/bin/terraform"),
            patch("terra.magic.terraform.subprocess.run") as mock_run,
        ):
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "Apply complete!"
            mock_run.return_value.stderr = ""
            magic.terraform("apply tfplan", "")
        assert "_plan" not in ip.user_ns
