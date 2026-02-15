"""Tests for the diagnostics provider protocol."""

from __future__ import annotations

from pathlib import Path

import pytest

from rawagents.tools.builtin.fs._diagnostics import (
    Diagnostic,
    DiagnosticSeverity,
    DiagnosticsProvider,
)
from rawagents.tools.builtin.fs._security import SecurityContext


class TestDiagnostic:
    """Test the Diagnostic dataclass."""

    def test_create_diagnostic(self) -> None:
        """All fields should be populated correctly."""
        d = Diagnostic(
            file_path="/project/main.py",
            line=10,
            column=5,
            severity=DiagnosticSeverity.ERROR,
            message="Undefined variable 'x'",
            source="pyright",
            code="reportUndefinedVariable",
        )
        assert d.file_path == "/project/main.py"
        assert d.line == 10
        assert d.column == 5
        assert d.severity == DiagnosticSeverity.ERROR
        assert d.message == "Undefined variable 'x'"
        assert d.source == "pyright"
        assert d.code == "reportUndefinedVariable"

    def test_default_code_empty(self) -> None:
        """Code should default to empty string."""
        d = Diagnostic(
            file_path="/test.py",
            line=1,
            column=1,
            severity=DiagnosticSeverity.WARNING,
            message="test",
            source="ruff",
        )
        assert d.code == ""


class TestDiagnosticSeverity:
    """Test severity enum values."""

    def test_severity_values(self) -> None:
        """All severity levels should have correct string values."""
        assert DiagnosticSeverity.ERROR.value == "error"
        assert DiagnosticSeverity.WARNING.value == "warning"
        assert DiagnosticSeverity.INFO.value == "info"
        assert DiagnosticSeverity.HINT.value == "hint"


class TestDiagnosticsProviderProtocol:
    """Test the DiagnosticsProvider protocol."""

    def test_protocol_isinstance_check(self) -> None:
        """A conforming class should pass isinstance check."""

        class MockProvider:
            async def get_diagnostics(self, file_path: str) -> list[Diagnostic]:
                return []

        provider = MockProvider()
        assert isinstance(provider, DiagnosticsProvider)

    def test_non_provider_fails_isinstance(self) -> None:
        """A non-conforming class should fail isinstance check."""

        class NotAProvider:
            def something_else(self) -> None:
                pass

        obj = NotAProvider()
        assert not isinstance(obj, DiagnosticsProvider)

    @pytest.mark.asyncio
    async def test_mock_provider_returns_diagnostics(self) -> None:
        """A mock provider should return diagnostics."""

        class MockProvider:
            async def get_diagnostics(self, file_path: str) -> list[Diagnostic]:
                return [
                    Diagnostic(
                        file_path=file_path,
                        line=1,
                        column=1,
                        severity=DiagnosticSeverity.ERROR,
                        message="syntax error",
                        source="mock",
                    ),
                    Diagnostic(
                        file_path=file_path,
                        line=5,
                        column=10,
                        severity=DiagnosticSeverity.WARNING,
                        message="unused variable",
                        source="mock",
                    ),
                ]

        provider = MockProvider()
        diagnostics = await provider.get_diagnostics("/test.py")
        assert len(diagnostics) == 2
        assert diagnostics[0].severity == DiagnosticSeverity.ERROR
        assert diagnostics[1].severity == DiagnosticSeverity.WARNING


class TestSecurityContextDiagnostics:
    """Test diagnostics_provider field on SecurityContext."""

    def test_defaults_to_none(self, tmp_path: Path) -> None:
        """diagnostics_provider should default to None."""
        ctx = SecurityContext(workspace=str(tmp_path))
        assert ctx.diagnostics_provider is None

    def test_accepts_provider(self, tmp_path: Path) -> None:
        """SecurityContext should accept a diagnostics provider."""

        class MockProvider:
            async def get_diagnostics(self, file_path: str) -> list[Diagnostic]:
                return []

        provider = MockProvider()
        ctx = SecurityContext(
            workspace=str(tmp_path),
            diagnostics_provider=provider,
        )
        assert ctx.diagnostics_provider is provider
