"""Add src/ to sys.path so tests import directly from the source packages."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
