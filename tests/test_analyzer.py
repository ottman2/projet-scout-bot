from src.core.analyzer import get_player_map_stats, get_sorted_map_stats


def test_sorts_five_v_five_maps_by_match_count():
    data = {"segments": [
        {"mode": "5v5", "label": "Inferno", "stats": {"Matches": "3", "Win Rate %": "50"}},
        {"mode": "5v5", "label": "Nuke", "stats": {"Matches": "8", "Win Rate %": "62"}},
        {"mode": "1v1", "label": "Aim", "stats": {"Matches": "99", "Win Rate %": "80"}},
    ]}
    assert [item["map"] for item in get_sorted_map_stats(data)] == ["Nuke", "Inferno"]


def test_empty_and_missing_data():
    assert get_sorted_map_stats(None) == []
    assert get_sorted_map_stats({}) == []
    assert get_sorted_map_stats({"segments": None}) == []


def test_keeps_low_volume_map_for_caller_threshold():
    data = {"segments": [{"mode": "5v5", "label": "Vertigo", "stats": {"Matches": "1"}}]}
    assert get_sorted_map_stats(data)[0]["matches"] == 1


def test_skips_invalid_segments_and_counts():
    data = {"segments": [
        None,
        {"mode": "5v5", "stats": {"Matches": "unknown"}},
        {"mode": "5v5", "label": "Mirage", "stats": {"Matches": "4", "Win Rate %": "bad"}},
    ]}
    assert get_sorted_map_stats(data) == [{"map": "Mirage", "matches": 4, "winrate": 0}]


def test_normalizes_player_maps_in_descending_order():
    stats = {"segments": [
        {"mode": "5v5", "type": "Map", "label": "de_nuke", "stats": {"Matches": "2", "Win Rate %": "50"}},
        {"mode": "5v5", "type": "Map", "label": "de_mirage", "stats": {"Matches": "5", "Win Rate %": "60"}},
        {"mode": "5v5", "type": "Lifetime", "label": "Lifetime", "stats": {"Matches": "50"}},
    ]}
    assert [item["name"] for item in get_player_map_stats(stats)] == ["Mirage", "Nuke"]


def test_player_map_ties_sort_by_winrate_without_dropping_maps():
    stats = {"segments": [
        {"mode": "5v5", "type": "Map", "label": "de_inferno", "stats": {"Matches": "4", "Win Rate %": "45"}},
        {"mode": "5v5", "type": "Map", "label": "de_ancient", "stats": {"Matches": "4", "Win Rate %": "70"}},
        {"mode": "5v5", "type": "Map", "label": "de_dust2", "stats": {"Matches": "1", "Win Rate %": "10"}},
    ]}
    result = get_player_map_stats(stats)
    assert [item["name"] for item in result] == ["Ancient", "Inferno", "Dust2"]


def test_missing_player_maps_returns_empty_list():
    assert get_player_map_stats({"lifetime": {"Matches": "10"}}) == []


def test_player_map_kd_is_only_returned_when_api_segment_contains_it():
    stats = {"segments": [
        {"mode": "5v5", "type": "Map", "label": "de_nuke", "stats": {"Matches": "3", "Win Rate %": "50"}},
        {"mode": "5v5", "type": "Map", "label": "de_mirage", "stats": {
            "Matches": "3", "Win Rate %": "50", "Average K/D Ratio": "1.25"
        }},
    ]}
    maps = {item["name"]: item for item in get_player_map_stats(stats)}
    assert "kd" not in maps["Nuke"]
    assert maps["Mirage"]["kd"] == "1.25"
