"""Back-compat shim: stat-file parsing now lives in the stat_file subpackage."""
from .stat_file import (  # noqa: F401
    ErrorChecker, StatObj, EventSearch, EventObj, HudObj, RunnerObj,
    load_stat_file, iter_stat_files,
)
