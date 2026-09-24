"""Legacy compatibility module for canonical model registration."""

from app.models.registry import MODEL_REGISTRY, get_model, load_models


def import_all_models():
    """Import and return every canonical mapped model."""
    return load_models()


__all__ = ['MODEL_REGISTRY', 'get_model', 'import_all_models', 'load_models']
