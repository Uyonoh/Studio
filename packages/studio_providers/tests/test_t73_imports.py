"""Production-import guard for the providers package (T7.3).

The contract suite is test-only and imports pytest. It must stay out of the
package's import graph so the API/worker images (which do not install dev
dependencies) can boot.
"""

from __future__ import annotations

import subprocess
import sys

from studio_providers.contract import ProviderContractSuite


def test_importing_package_does_not_require_pytest() -> None:
    code = (
        "import sys; sys.modules['pytest'] = None; "
        "import studio_providers; print(studio_providers.__version__)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


def test_contract_suite_remains_importable_for_tests() -> None:
    assert ProviderContractSuite.__name__ == "ProviderContractSuite"
