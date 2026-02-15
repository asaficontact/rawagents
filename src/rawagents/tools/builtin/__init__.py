"""Built-in tools for RawAgents.

This module provides essential tools for building Claude Code-like agents:

- **fs**: File system tools (read, write, edit, list, glob, grep, etc.)
- **shell**: Shell/command execution tools (bash, bash_output, kill_shell)
- **web**: Web tools (web_search, web_fetch)
"""

from rawagents.tools.builtin import fs, shell, web


__all__ = ["fs", "shell", "web"]
