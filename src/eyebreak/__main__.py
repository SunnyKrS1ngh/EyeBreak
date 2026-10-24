"""Module entry point."""
import sys
from pathlib import Path

try:
    from eyebreak.app import main
except ImportError:
    # Fallback if executed as a standalone script outside package context
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from eyebreak.app import main

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
