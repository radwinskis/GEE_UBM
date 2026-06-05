### GEE_UBM/__init__.py

# Expose the Data Prep Modules
from .InputCollections import InputCollections

from .SnowMelt import SnowMeltCollection

# Expose the Workflow Helpers
from .helpers import (
    build_model_ready_collection,
    check_merged_collection,
    harmonize_to_target
)

# Expose the Model Runners
from .OriginalUBM import OriginalUBMRun
from .ModifiedUBM1 import ModifiedUBM1Run
from .ModifiedUBM2 import ModifiedUBM2Run

# Define what gets imported with "from GEE_UBM import *"
__all__ = [
    "InputCollections",
    "build_model_ready_collection",
    "check_merged_collection",
    "harmonize_to_target",
    "OriginalUBMRun",
    "ModifiedUBM1Run",
    "ModifiedUBM2Run",
    "SnowMeltCollection"
]

__version__ = "1.0.0"