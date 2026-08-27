"""Validación del motor contra verdad terreno."""

from botdetector.validation import curves, sampling
from botdetector.validation.curves import CurvePoint, sweep, to_markdown
from botdetector.validation.synthetic import SyntheticAudience, generate, score_detection

__all__ = [
    "CurvePoint",
    "SyntheticAudience",
    "curves",
    "generate",
    "sampling",
    "score_detection",
    "sweep",
    "to_markdown",
]
