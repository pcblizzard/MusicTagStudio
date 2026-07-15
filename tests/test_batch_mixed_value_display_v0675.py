from musictagstudio.batch_comparison_logic import (
    _format_value_distribution,
)


def test_missing_values_are_described_without_leer():
    result = _format_value_distribution(
        [
            "Fenster zum Hof",
            "Fenster zum Hof",
            "",
        ]
    )

    assert "<leer>" not in result
    assert result == (
        "Fenster zum Hof (2×) · "
        "fehlt bei 1 Titel"
    )


def test_all_missing_values_remain_blank():
    assert (
        _format_value_distribution(
            ["", ""]
        )
        == ""
    )
