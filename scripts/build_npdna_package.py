#!/usr/bin/env python3
"""Build a standalone npdna PyPI package from the tantra/npdna/ source.

Usage:
    python scripts/build_npdna_package.py          # builds wheel only
    python scripts/build_npdna_package.py --upload  # builds + uploads to PyPI

Requires: build, twine, and a PyPI API token configured.
"""

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE = REPO_ROOT / "tantra" / "npdna"
PACKAGE_NAME = "npdna"
VERSION = "0.4.1"

# Files to exclude from the PyPI package
EXCLUDE = {"__pycache__", "*.pyc", ".pytest_cache"}

PYPROJECT_TOML = f"""[build-system]
requires = ["setuptools>=64.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{PACKAGE_NAME}"
version = "{VERSION}"
description = "NP-DNA — genome-inspired neural networks with plasticity and strand growth"
readme = "README.md"
license = {{text = "MIT"}}
authors = [{{name = "Atulya AI"}}]
keywords = ["neural-network", "neuroevolution", "plasticity", "deep-learning", "genome"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Science/Research",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Topic :: Scientific/Engineering :: Artificial Intelligence",
]
requires-python = ">=3.10"
dependencies = [
    "torch>=2.0",
    "numpy>=1.24",
    "psutil>=5.9",
    "cryptography>=42.0",
    "croniter>=2.0",
]

[project.urls]
Homepage = "https://github.com/atulya-ai/atulya-tantra"
Repository = "https://github.com/atulya-ai/atulya-tantra"
Documentation = "https://github.com/atulya-ai/atulya-tantra/tree/main/docs"

[tool.setuptools.packages.find]
include = ["{PACKAGE_NAME}", "{PACKAGE_NAME}.*"]
"""

README_MD = """# NP-DNA

**NeuroPlastic DNA Network** — a genome-inspired neural network architecture with plasticity, sparse routing, and strand growth.

> `pip install npdna`

## Quick Start

```python
from npdna import NpDnaCore, NpDnaConfig, CONFIGS

# Load a pretrained config
core = NpDnaCore.from_config("atulya_seed")

# Encode / decode
ids = core.encode("Hello, world!")
text = core.decode(ids)

# Generate
output = core.generate("Once upon a time")
print(output)

# Forward pass
import torch
logits, loss = core.model(torch.tensor([ids]))
```

## Key Concepts

| Concept | What it does |
|---------|-------------|
| **Genome** | Compact DNA-like seeds generate strand weights |
| **Mesh** | Sparse top-k router activates only specialist strands per token |
| **Cortex** | External vector memory for facts and retrieval |
| **Plasticity** | Dead-strand recovery, vocabulary pressure, and growth hooks |
| **Strands** | Specialist groups: `main`, `sentiment`, `bias`, `security`, `cortex` |

## Configurations

```python
from npdna import CONFIGS

# Built-in presets
print(list(CONFIGS.keys()))
# → seed (2 layers, 4 strands), nano (2,6), micro (3,12),
#   small (4,8), medium (6,12)
```

## License

MIT
"""


def build_package():
    """Copy source into a clean build dir and build the wheel."""
    build_dir = REPO_ROOT / "build" / "npdna_pkg"
    pkg_dir = build_dir / PACKAGE_NAME

    # Clean previous build
    if build_dir.exists():
        shutil.rmtree(build_dir)

    # Copy source files
    shutil.copytree(SOURCE, pkg_dir, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    # Write pyproject.toml
    (build_dir / "pyproject.toml").write_text(PYPROJECT_TOML, encoding="utf-8")

    # Write README
    (build_dir / "README.md").write_text(README_MD, encoding="utf-8")

    # Build
    result = subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(REPO_ROOT / "dist")],
        cwd=str(build_dir),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("BUILD FAILED")
        print(result.stdout)
        print(result.stderr)
        return False

    # Find the built wheel
    import glob
    wheels = list((REPO_ROOT / "dist").glob(f"{PACKAGE_NAME}-{VERSION}-*.whl"))
    if wheels:
        print(f"✅ Built: {wheels[0].name}")
        print(f"   {wheels[0]}")
    else:
        print("⚠️  Wheel not found — check dist/")
        return False

    return True


def upload():
    """Upload to PyPI with twine."""
    result = subprocess.run(
        [sys.executable, "-m", "twine", "upload", str(REPO_ROOT / "dist" / f"{PACKAGE_NAME}-{VERSION}-*.whl")],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr)
    if result.returncode == 0:
        print(f"✅ Uploaded {PACKAGE_NAME} v{VERSION} to PyPI!")
        print(f"   https://pypi.org/project/{PACKAGE_NAME}/")
        return True
    return False


if __name__ == "__main__":
    upload_flag = "--upload" in sys.argv

    if not build_package():
        sys.exit(1)

    if upload_flag:
        upload()
    else:
        print(f"\n📦 Wheel is ready at dist/. Run with --upload to push to PyPI.")
        print(f"   You'll need a PyPI API token first:")
        print(f"   1. Create account at https://pypi.org/")
        print(f"   2. Go to Account Settings → API tokens → Add")
        print(f"   3. Run: python -m twine upload dist/{PACKAGE_NAME}-{VERSION}*")
