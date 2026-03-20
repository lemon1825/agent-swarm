"""Safety Guards for Agent Swarm.

Inspired by gstack careful/freeze/guard patterns.
Detects and blocks destructive operations before execution.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class GuardAction(Enum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"


@dataclass
class GuardResult:
    action: GuardAction
    reason: str = ""
    matched_pattern: str = ""
    guard_name: str = ""


class CarefulGuard:
    """Detects destructive commands and operations."""

    # Patterns that indicate destructive operations
    DESTRUCTIVE_PATTERNS = [
        (r'\brm\s+-rf\b', "Recursive force delete"),
        (r'\brm\s+-r\b', "Recursive delete"),
        (r'\bDROP\s+TABLE\b', "SQL table drop"),
        (r'\bDROP\s+DATABASE\b', "SQL database drop"),
        (r'\bTRUNCATE\b', "SQL truncate"),
        (r'\bDELETE\s+FROM\b(?!.*WHERE)', "SQL delete without WHERE"),
        (r'\bgit\s+push\s+.*--force\b', "Git force push"),
        (r'\bgit\s+push\s+-f\b', "Git force push"),
        (r'\bgit\s+reset\s+--hard\b', "Git hard reset"),
        (r'\bgit\s+clean\s+-fd\b', "Git clean forced"),
        (r'\bchmod\s+777\b', "Overly permissive chmod"),
        (r'\b:>\s*/', "File truncation"),
        (r'\bmkfs\b', "Filesystem format"),
        (r'\bdd\s+if=', "Raw disk write"),
        (r'\bkill\s+-9\b', "Force kill process"),
        (r'\bsudo\s+rm\b', "Sudo remove"),
        (r'\bformat\s+[A-Z]:', "Disk format"),
    ]

    def __init__(self, extra_patterns: Optional[List[tuple]] = None, action: GuardAction = GuardAction.WARN):
        self._patterns = list(self.DESTRUCTIVE_PATTERNS)
        if extra_patterns:
            self._patterns.extend(extra_patterns)
        self._compiled = [(re.compile(p, re.IGNORECASE), desc) for p, desc in self._patterns]
        self._default_action = action

    def check(self, content: str) -> GuardResult:
        """Check content for destructive patterns."""
        for pattern, description in self._compiled:
            match = pattern.search(content)
            if match:
                return GuardResult(
                    action=self._default_action,
                    reason=f"Destructive operation detected: {description}",
                    matched_pattern=match.group(),
                    guard_name="CarefulGuard",
                )
        return GuardResult(action=GuardAction.ALLOW, guard_name="CarefulGuard")


class FreezeGuard:
    """Prevents modifications to frozen directories/paths."""

    def __init__(self, frozen_paths: Optional[List[str]] = None):
        self._frozen: Set[str] = set(frozen_paths or [])

    def freeze(self, path: str) -> None:
        self._frozen.add(path)

    def unfreeze(self, path: str) -> None:
        self._frozen.discard(path)

    @property
    def frozen_paths(self) -> Set[str]:
        return set(self._frozen)

    def check(self, content: str) -> GuardResult:
        """Check if content references frozen paths."""
        for frozen_path in self._frozen:
            if frozen_path in content:
                return GuardResult(
                    action=GuardAction.BLOCK,
                    reason=f"Path is frozen: {frozen_path}",
                    matched_pattern=frozen_path,
                    guard_name="FreezeGuard",
                )
        return GuardResult(action=GuardAction.ALLOW, guard_name="FreezeGuard")


class GuardChain:
    """Combines multiple guards. Returns the most restrictive result."""

    ACTION_SEVERITY = {GuardAction.ALLOW: 0, GuardAction.WARN: 1, GuardAction.BLOCK: 2}

    def __init__(self, guards: Optional[List[Any]] = None):
        self._guards = list(guards or [])

    def add(self, guard: Any) -> "GuardChain":
        return GuardChain(self._guards + [guard])

    def check(self, content: str) -> GuardResult:
        """Run all guards, return most restrictive result."""
        worst = GuardResult(action=GuardAction.ALLOW, guard_name="GuardChain")
        for guard in self._guards:
            result = guard.check(content)
            if self.ACTION_SEVERITY.get(result.action, 0) > self.ACTION_SEVERITY.get(worst.action, 0):
                worst = result
        return worst

    def check_all(self, content: str) -> List[GuardResult]:
        """Run all guards, return all results."""
        return [guard.check(content) for guard in self._guards]
