"""Watchdog installer output must supply its configured dashboard token."""
from argparse import Namespace


def test_systemd_unit_loads_the_project_env_file(tmp_path):
    from atulya.watchdog import generate_systemd_unit

    args = Namespace(
        cwd=str(tmp_path), url="http://127.0.0.1:8501/api/health", interval=30,
        timeout=5, max_failures=3, cmd="python -m atulya.sevak",
    )
    unit = generate_systemd_unit(args)

    assert f"EnvironmentFile=-{tmp_path.as_posix()}/.env" in unit.replace("\\", "/")
