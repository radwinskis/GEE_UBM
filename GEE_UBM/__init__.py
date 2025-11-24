# GEE_UBM/__init__.py

# 1. Expose the Data Factory
from .InputCollections import InputCollections

# 2. Expose the Workflow Helpers
from .helpers import (
    build_model_ready_collection,
    check_merged_collection,
    harmonize_to_target
)

# 3. Expose the Model Runners
from .OriginalUBM import OriginalUBMRun
from .ModifiedUBM1 import ModifiedUBM1Run
from .ModifiedUBM2 import ModifiedUBM2Run

# 4. Define what gets imported with "from GEE_UBM import *"
__all__ = [
    "InputCollections",
    "build_model_ready_collection",
    "check_merged_collection",
    "harmonize_to_target",
    "OriginalUBMRun",
    "ModifiedUBM1Run",
    "ModifiedUBM2Run",
]

# Optional: Package Version
__version__ = "0.1.0"