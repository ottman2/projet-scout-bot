from src.core.veto_analyzer import analyze_veto, recommend_ban, recommend_bans, recommend_pick


def stats(**maps):
    return {"segments": [
        {"mode": "5v5", "label": name, "stats": values}
        for name, values in maps.items()
    ]}


def by_map(analysis, name):
    return next(item for item in analysis if item["map"] == name)


def test_clear_advantage_is_favorable():
    result = analyze_veto(stats(Nuke={"Matches": "100", "Win Rate %": "60"}),
                          stats(Nuke={"Matches": "100", "Win Rate %": "45"}))
    assert by_map(result, "Nuke")["classification"] == "favorable"


def test_clear_disadvantage_is_unfavorable():
    result = analyze_veto(stats(Cache={"Matches": "100", "Win Rate %": "45"}),
                          stats(Cache={"Matches": "100", "Win Rate %": "60"}))
    assert by_map(result, "Cache")["classification"] == "unfavorable"


def test_close_winrates_are_neutral():
    result = analyze_veto(stats(Inferno={"Win Rate %": "55"}), stats(Inferno={"Win Rate %": "54"}))
    assert by_map(result, "Inferno")["classification"] == "neutral"


def test_confidence_tracks_low_and_high_volume():
    result = analyze_veto(
        stats(Cache={"Matches": "5", "Win Rate %": "75"}, Dust2={"Matches": "166", "Win Rate %": "56"}),
        stats(Cache={"Matches": "5", "Win Rate %": "75"}, Dust2={"Matches": "166", "Win Rate %": "56"}),
    )
    confidence = {item["map"]: item["confidence"] for item in result}
    assert confidence["D2"] == "élevée"
    assert confidence["Cache"] == "faible"


def test_missing_map_is_insufficient_not_zero():
    result = analyze_veto(stats(), stats(Cache={"Matches": "50", "Win Rate %": "61"}))
    cache = by_map(result, "Cache")
    assert cache["classification"] == "insufficient_data"
    assert cache["our"] is None
    assert cache["score"] is None


def test_kd_is_optional_and_only_used_when_both_sides_have_it():
    without = analyze_veto(stats(Nuke={"Matches": 100, "Win Rate %": 55}),
                           stats(Nuke={"Matches": 100, "Win Rate %": 50}))
    with_kd = analyze_veto(
        stats(Nuke={"Matches": 100, "Win Rate %": 55, "Average K/D Ratio": "1.2"}),
        stats(Nuke={"Matches": 100, "Win Rate %": 50, "Average K/D Ratio": "1.0"}),
    )
    assert by_map(without, "Nuke")["score"] == 5
    assert by_map(with_kd, "Nuke")["score"] == 6


def test_pick_uses_relative_advantage_not_absolute_wr():
    ours = stats(Nuke={"Matches": 100, "Win Rate %": 55}, Dust2={"Matches": 100, "Win Rate %": 62})
    theirs = stats(Nuke={"Matches": 100, "Win Rate %": 43}, Dust2={"Matches": 100, "Win Rate %": 61})
    assert recommend_pick(analyze_veto(ours, theirs))["map"] == "Nuke"


def test_ban_uses_largest_reliable_relative_disadvantage():
    ours = stats(Cache={"Matches": 100, "Win Rate %": 45}, Nuke={"Matches": 100, "Win Rate %": 50})
    theirs = stats(Cache={"Matches": 100, "Win Rate %": 63}, Nuke={"Matches": 100, "Win Rate %": 52})
    assert recommend_ban(analyze_veto(ours, theirs))["map"] == "Cache"


def test_invalid_or_missing_winrate_never_becomes_zero():
    result = analyze_veto(stats(Nuke={"Matches": 100}), stats(Nuke={"Matches": 100, "Win Rate %": "bad"}))
    nuke = by_map(result, "Nuke")
    assert nuke["classification"] == "insufficient_data"
    assert nuke["our"]["winrate"] is None
    assert nuke["opponent"]["winrate"] is None


def test_official_maps_are_analyzed_but_pick_is_limited_to_gandalt_pool():
    ours = stats(Mirage={"Matches": 100, "Win Rate %": 100},
                 Inferno={"Matches": 30, "Win Rate %": 55},
                 Nuke={"Matches": 30, "Win Rate %": 55},
                 Dust2={"Matches": 30, "Win Rate %": 55},
                 Cache={"Matches": 30, "Win Rate %": 55},
                 Anubis={"Matches": 30, "Win Rate %": 55},
                 Ancient={"Matches": 30, "Win Rate %": 55})
    theirs = stats(Mirage={"Matches": 100, "Win Rate %": 0},
                   Inferno={"Matches": 30, "Win Rate %": 55},
                   Nuke={"Matches": 30, "Win Rate %": 55},
                   Dust2={"Matches": 30, "Win Rate %": 55},
                   Cache={"Matches": 30, "Win Rate %": 55},
                   Anubis={"Matches": 30, "Win Rate %": 55},
                   Ancient={"Matches": 30, "Win Rate %": 55})
    result = analyze_veto(ours, theirs)
    assert [item["map"] for item in result] == ["D2", "Nuke", "Inferno", "Cache", "Anubis", "Ancient", "Mirage"]
    assert next(item for item in result if item["map"] == "Mirage")["classification"] == "favorable"
    assert recommend_pick(result) is None


def test_out_of_pool_map_can_still_be_recommended_as_ban():
    ours = stats(Mirage={"Matches": 100, "Win Rate %": 40})
    theirs = stats(Mirage={"Matches": 100, "Win Rate %": 65})
    assert recommend_ban(analyze_veto(ours, theirs))["map"] == "Mirage"


def test_ban_shortlist_ranks_three_candidates_and_skips_missing_data():
    ours = stats(Dust2={"Matches": 50, "Win Rate %": 40},
                 Nuke={"Matches": 50, "Win Rate %": 45},
                 Inferno={"Matches": 50, "Win Rate %": 50},
                 Cache={"Matches": 50, "Win Rate %": 60},
                 Mirage={"Matches": 50, "Win Rate %": 65})
    theirs = stats(Dust2={"Matches": 50, "Win Rate %": 70},
                   Nuke={"Matches": 50, "Win Rate %": 65},
                   Inferno={"Matches": 50, "Win Rate %": 60},
                   Cache={"Matches": 50, "Win Rate %": 60},
                   Mirage={"Matches": 50, "Win Rate %": 30})
    result = analyze_veto(ours, theirs)
    assert [item["map"] for item in recommend_bans(result)] == ["Mirage", "Anubis", "Ancient"]


def test_ban_shortlist_keeps_official_maps_even_without_comparable_data():
    result = analyze_veto(stats(), stats(Dust2={"Matches": 50, "Win Rate %": 70}))
    assert len(result) == 7
    assert [item["map"] for item in recommend_bans(result)] == ["Anubis", "Ancient", "Mirage"]
    assert all(item["score"] is None for item in recommend_bans(result))


def test_maps_outside_official_pool_are_ignored():
    ours = stats(Train={"Matches": 100, "Win Rate %": 10},
                 Overpass={"Matches": 100, "Win Rate %": 10},
                 Dust2={"Matches": 30, "Win Rate %": 50})
    theirs = stats(Train={"Matches": 100, "Win Rate %": 90},
                   Overpass={"Matches": 100, "Win Rate %": 90},
                   Dust2={"Matches": 30, "Win Rate %": 50})
    result = analyze_veto(ours, theirs)
    assert len(result) == 7
    assert all(item["map"] not in {"Train", "Overpass"} for item in result)


def test_map_pool_order_breaks_equal_recommendation_ties():
    ours = stats(Nuke={"Matches": 30, "Win Rate %": 70}, Dust2={"Matches": 30, "Win Rate %": 70})
    theirs = stats(Nuke={"Matches": 30, "Win Rate %": 50}, Dust2={"Matches": 30, "Win Rate %": 50})
    assert recommend_pick(analyze_veto(ours, theirs))["map"] == "D2"
