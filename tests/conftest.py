import sys
from pathlib import Path

# clipboard.py lives at the repo root, not in a package, so it isn't importable
# by name until the repo root is on sys.path. Doing this in conftest.py means
# every test file gets it automatically, with no per-file boilerplate.
sys.path.insert(0, str(Path(__file__).parent.parent))
