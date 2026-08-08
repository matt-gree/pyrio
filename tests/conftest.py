"""pyrio's package_dir is the repo root, so put it on sys.path for tests."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
