"""Regression checks for production operational artifacts."""

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def test_backup_manifest_is_verified_from_its_own_directory() -> None:
    """Manifest entries are relative, so verification must run inside the snapshot."""
    script = (REPOSITORY_ROOT / "infra" / "backup" / "backup.sh").read_text()

    assert '(cd "$STAMP" && sha256sum -c SHA256SUMS >/dev/null)' in script
    assert 'sha256sum -c "$STAMP/SHA256SUMS"' not in script
