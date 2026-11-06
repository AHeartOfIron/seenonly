"""seenonly: give an LLM only the text a person can see on a page."""
from .core import Finding, Result, clean, clean_text, stylesheet_links
from .phrases import detect

__all__ = ["clean", "clean_text", "detect", "stylesheet_links", "Result", "Finding"]
__version__ = "0.1.1"
