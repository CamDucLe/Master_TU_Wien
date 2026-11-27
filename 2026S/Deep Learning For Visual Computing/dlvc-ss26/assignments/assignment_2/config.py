"""
Central configuration for machine-dependent paths used in assignment scripts.

Students should adapt these paths to their local setup.
"""

from pathlib import Path


# Path to OxfordIIITPet dataset
OXFORD_PETS_DIR = Path("data/oxford_pets")

# Path to Cityscapes dataset
CITYSCAPES_DIR = Path("data/cityscapes")

# Optional logging directory (for wandb/tensorboard/custom logs)
LOG_DIR = Path("logs")

# Directory where trained model checkpoints are stored
MODEL_SAVE_DIR = Path("saved_models")
