from musictagstudio.library_audit.models import (
    LibraryAuditSummary,
    LibraryIssue,
)


def test_library_health_score():
    summary = LibraryAuditSummary(
        checked_files=10,
        checked_albums=1,
        issues=(
            LibraryIssue(
                category="Test",
                severity="error",
                message="Fehler",
            ),
            LibraryIssue(
                category="Test",
                severity="warning",
                message="Warnung",
            ),
            LibraryIssue(
                category="Test",
                severity="info",
                message="Info",
            ),
        ),
    )

    assert summary.error_count == 1
    assert summary.warning_count == 1
    assert summary.info_count == 1
    assert summary.health_score == 91
