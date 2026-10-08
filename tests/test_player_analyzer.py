import pytest

from src.core.player_analyzer import chunk_lines, extract_esea_season, normalize_esea_history


@pytest.mark.parametrize("name", [
    "ESEA Season 59",
    "ESEA League Season 59",
    "ESEA Advanced Season 59",
    "ESEA S59",
    "ESEA Season 59 Europe",
])
def test_recognizes_explicit_esea_season_forms(name):
    assert extract_esea_season(name) == 59


@pytest.mark.parametrize("name", [
    "Season 59",
    "ESL Season 59",
    "Random Tournament 59",
    "ESEA Random Tournament 59",
])
def test_does_not_infer_season_from_unrelated_names(name):
    assert extract_esea_season(name) is None


def test_recognizes_faceit_esea_division_and_organizer_qualified_name():
    assert extract_esea_season("S59 EU Open10 A - Regular Season") == 59
    assert extract_esea_season("Season 58", "ESEA") == 58
    assert extract_esea_season("Season 58", "ESL") is None


def test_normalizes_and_deduplicates_seasons_from_history_and_tournaments():
    seasons = normalize_esea_history(
        ["🏆 ESEA Season 59 Europe", "ESEA Season 58"],
        [{"name": "Season 59", "organizer_id": "esea"}],
        {"esea": "ESEA"},
    )
    assert [item["season"] for item in seasons] == [59, 58]
    assert len(seasons[0]["sources"]) == 2


def test_chunks_page_sized_content_without_losing_data():
    assert chunk_lines(["map 1", "map 2"], max_chars=20) == ["map 1\nmap 2"]
    lines = ["x" * 12, "y" * 12, "z" * 12]
    pages = chunk_lines(lines, max_chars=20)
    assert len(pages) == 3
    assert [len(page) for page in pages] == [12, 12, 12]
    long_line = "a" * 45
    split_pages = chunk_lines([long_line], max_chars=20)
    assert len(split_pages) == 3
    assert "".join(split_pages) == long_line
