"""
Entry point. Run with: uv run python main.py

uv handles the virtual env automatically; first run will install dependencies.
"""
import sys
from pathlib import Path

# Make src/ importable without installing the package.
# This is the simplest approach for a learning/dev project.
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent.loop import main

if __name__ == "__main__":
    main()
