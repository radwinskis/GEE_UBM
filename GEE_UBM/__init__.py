# GEE_UBM/__init__.py

# 1. Expose the Data Factory
from .InputCollections import InputCollections

from .SnowMelt import SnowMeltCollection

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

# def __getattr__(name):
#     """Lazy load modules only when accessed."""
#     if name == "InputCollections":
#         # from .InputCollections import InputCollections
#         # return InputCollections
#         # import GEE_UBM.InputCollections
#         # return GEE_UBM.InputCollections.InputCollections
#         from . import InputCollections as module
#         return module.InputCollections
#     elif name == "build_model_ready_collection":
#         from .helpers import build_model_ready_collection
#         return build_model_ready_collection
#     elif name == "check_merged_collection":
#         from .helpers import check_merged_collection
#         return check_merged_collection
#     elif name == "harmonize_to_target":
#         from .helpers import harmonize_to_target
#         return harmonize_to_target
#     elif name == "OriginalUBMRun":
#         from .OriginalUBM import OriginalUBMRun
#         return OriginalUBMRun
#     elif name == "ModifiedUBM1Run":
#         from .ModifiedUBM1 import ModifiedUBM1Run
#         return ModifiedUBM1Run
#     elif name == "ModifiedUBM2Run":
#         from .ModifiedUBM2 import ModifiedUBM2Run
#         return ModifiedUBM2Run
#     raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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