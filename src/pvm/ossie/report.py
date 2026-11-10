"""Validation issue and report types for the PVM Ossie extension validator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["error", "warning"]


@dataclass(frozen=True)
class Issue:
    """A single validation finding."""

    code: str
    severity: Severity
    path: str
    message: str


@dataclass(frozen=True)
class ValidationReport:
    """The collected outcome of validating a document."""

    issues: list[Issue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Return True when the report has no error-severity issues."""
        return not any(issue.severity == "error" for issue in self.issues)

    def raise_for_errors(self) -> None:
        """Raise ValueError listing error issues, if any."""
        errors = [issue for issue in self.issues if issue.severity == "error"]
        if errors:
            summary = "; ".join(f"{issue.code} ({issue.path}): {issue.message}" for issue in errors)
            msg = f"PVM extension validation failed: {summary}"
            raise ValueError(msg)
