import subprocess
import sys


def test_module_entrypoint() -> None:
    """Check that the installed package can start without credentials or network access."""
    result = subprocess.run(
        [sys.executable, "-m", "agent_runtime"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "Hello from agent-runtime!" in result.stdout
if __name__ == "__main__":
    test_module_entrypoint()