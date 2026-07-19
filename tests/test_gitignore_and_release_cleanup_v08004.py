from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_gitignore_excludes_generated_python_files():
    text = (
        ROOT
        / ".gitignore"
    ).read_text(
        encoding="utf-8"
    )

    assert "__pycache__/" in text
    assert "*.py[cod]" in text
    assert ".pytest_cache/" in text
    assert "*.egg-info/" in text


def test_release_check_cleans_generated_files():
    text = (
        ROOT
        / "scripts"
        / "release_check.py"
    ).read_text(
        encoding="utf-8"
    )

    assert "def clean_generated_files" in text
    assert '"__pycache__"' in text
    assert '"*.pyc"' in text
