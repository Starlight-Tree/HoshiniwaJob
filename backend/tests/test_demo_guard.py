import subprocess
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("module, extra", [("app.seed_demo", []), ("app.seed_images", ["--source-dir", "/nonexistent"])])
def test_demo_seeds_refuse_to_run_without_demo_data_allow(module, extra):
    """DEMO_DATA=allow が無いと、DB に繋ぐ前に止まる（本番の環境で、ダミーデータを誤って入れないため）。"""
    env = {"PATH": "/usr/bin:/bin", "DATABASE_URL": "postgresql://nobody@127.0.0.1:1/none"}  # 繋げない宛先。繋ごうとしたら別のエラーで分かる
    result = subprocess.run([sys.executable, "-m", module, *extra], cwd=BACKEND, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode != 0
    assert "DEMO_DATA=allow" in result.stderr or "DEMO_DATA=allow" in result.stdout
