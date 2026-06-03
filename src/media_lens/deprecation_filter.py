"""Suppress known deprecation warnings."""

import warnings

def suppress_gavel_ai_deprecations():
    """Suppress GoogleProvider deprecation warning from gavel-ai."""
    warnings.filterwarnings(
        "ignore",
        message=".*GoogleProvider.*with Google Cloud.*arguments.*deprecated.*"
    )

# Apply on import
suppress_gavel_ai_deprecations()
