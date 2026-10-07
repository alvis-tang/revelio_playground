"""Stage 01_clean: Deduplicate, quarantine, and join titles, lookups, and profiles.

Accepts the same options as run.py (except --stages).
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run import main  # noqa: E402

if __name__ == '__main__':
    sys.exit(main(['--stages', '01', *sys.argv[1:]]))
