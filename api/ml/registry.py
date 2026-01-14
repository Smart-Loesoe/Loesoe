from __future__ import annotations

"""
ML module registry (Fase 23.4)

- Registry is in-memory (stateless, no side effects)
- Default registrations are optional and safe (import guarded)
- This file MUST NOT do DB writes or network calls
"""

from typing import Dict, Callable

from .interfaces import MLModule

_registry: Dict[str, MLModule] = {}


def register(module: MLModule) -> None:
    """Register a module instance by its unique name."""
    name = getattr(module, "name", None)
    if not name or not isinstance(name, str):
        raise ValueError("MLModule must have a non-empty 'name' attribute")
    _registry[name] = module


def get_registry() -> Dict[str, MLModule]:
    """Return a shallow copy of the registry."""
    return dict(_registry)


def _try_register(factory: Callable[[], MLModule]) -> None:
    """
    Helper: probeer 1 module te registreren.
    Nooit crashen tijdens skeleton-fase.
    """
    try:
        module = factory()
        register(module)
    except Exception:
        # bewust stil: skeleton moet altijd booten
        return


def _safe_default_register() -> None:
    """
    Register default modules if they exist.

    Guarded imports keep the skeleton stable even if modules
    are not present yet.
    """
    # 1) Dummy module (altijd veilig)
    try:
        from .modules.dummy_score import DummyScoreModule  # type: ignore
        _try_register(DummyScoreModule)
    except Exception:
        pass

    # 2) Explain preference score (deterministische score o.b.v. learning_patterns)
    try:
        from .modules.explain_preference_score import ExplainPreferenceScore  # type: ignore
        _try_register(ExplainPreferenceScore)
    except Exception:
        pass

    # 3) Patterns volume anomaly (2e deterministische module)
    try:
        from .modules.patterns_volume_anomaly import PatternsVolumeAnomaly  # type: ignore
        _try_register(PatternsVolumeAnomaly)
    except Exception:
        pass


# Run safe default registration at import time (in-memory only)
_safe_default_register()
