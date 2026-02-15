"""Search providers for RawAgents web tools.

Only BraveSearchProvider is built-in. For other providers,
implement the SearchProvider Protocol -- see _types.py for examples.
"""

from rawagents.tools.builtin.web.providers.brave import BraveSearchProvider


__all__ = ["BraveSearchProvider"]
