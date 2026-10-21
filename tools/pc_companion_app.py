"""Entry point for the standalone Windows companion executable."""
import json
from pathlib import Path
import sys

from tools.companion_setup import main as setup
from tools.device_companion import main as run_companion, execute
from tools.companion_paths import connection_directory


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        # No network, credentials, device actions or GUI: verify bundled imports/runtime.
        output = Path(sys.argv[sys.argv.index("--self-test") + 1])
        output.write_text(json.dumps({"ok": "companion active" in execute("ping", ""),
                                      "packaged": bool(getattr(sys, "frozen", False))}), encoding="utf-8")
    elif "--run-companion" in sys.argv:
        sys.argv.remove("--run-companion")
        directory = connection_directory(); directory.mkdir(parents=True, exist_ok=True)
        with (directory / "companion.log").open("a", encoding="utf-8", buffering=1) as log:
            sys.stdout = sys.stderr = log
            run_companion()
    else:
        setup()
