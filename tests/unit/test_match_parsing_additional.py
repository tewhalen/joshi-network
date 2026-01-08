"""Additional edge case tests for match parsing."""

from bs4 import BeautifulSoup

from joshirank.cagematch.cm_match import parse_match


def test_singles_draw():
    """Test a simple 1v1 draw (vs.)"""
    sample_html = """<tr class="TRow1"><td class="TCol TColSeparator">01.01.2025</td><td class="TCol TColSeparator">
<span class="MatchCard"><a href="?id=2&amp;nr=4629">Emi Sakura</a> vs. <a href="?id=2&amp;nr=9462">Mei Suruga</a> - Time Limit Draw</span></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    
    assert match["is_victory"] is False
    assert len(match["sides"]) == 2
    assert set(match["sides"][0]["wrestlers"]) == {4629}
    assert set(match["sides"][1]["wrestlers"]) == {9462}
    assert match["sides"][0]["is_winner"] is False
    assert match["sides"][1]["is_winner"] is False


def test_tag_draw():
    """Test a simple 2v2 draw (vs.)"""
    sample_html = """<tr class="TRow1"><td class="TCol TColSeparator">01.01.2025</td><td class="TCol TColSeparator">
<span class="MatchCard"><a href="?id=2&amp;nr=4629">Emi Sakura</a> &amp; <a href="?id=2&amp;nr=9462">Mei Suruga</a> vs. <a href="?id=2&amp;nr=10402">Yuna Mizumori</a> &amp; <a href="?id=2&amp;nr=9434">Baliyan Akki</a> - Double Count Out</span></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    
    assert match["is_victory"] is False
    assert len(match["sides"]) == 2
    assert set(match["sides"][0]["wrestlers"]) == {4629, 9462}
    assert set(match["sides"][1]["wrestlers"]) == {9434, 10402}


def test_singles_with_unlinked_loser():
    """Test singles match where the loser has no CageMatch profile."""
    sample_html = """<tr class="TRow1"><td class="TCol TColSeparator">01.01.2025</td><td class="TCol TColSeparator">
<span class="MatchCard"><a href="?id=2&amp;nr=828">Aja Kong</a> defeats Unknown Wrestler</span></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    
    assert match["is_victory"] is True
    assert len(match["sides"]) == 2
    assert set(match["sides"][0]["wrestlers"]) == {828}
    assert set(match["sides"][1]["wrestlers"]) == {-1}


def test_singles_both_unlinked():
    """Test singles match where both wrestlers have no CageMatch profiles."""
    sample_html = """<tr class="TRow1"><td class="TCol TColSeparator">01.01.2025</td><td class="TCol TColSeparator">
<span class="MatchCard">Unknown Wrestler A defeats Unknown Wrestler B</span></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    
    assert match["is_victory"] is True
    assert len(match["sides"]) == 2
    assert set(match["sides"][0]["wrestlers"]) == {-1}
    assert set(match["sides"][1]["wrestlers"]) == {-1}


def test_four_way_match():
    """Test a fatal 4-way singles match."""
    sample_html = """<tr class="TRow1"><td class="TCol TColSeparator">01.01.2025</td><td class="TCol TColSeparator">
<span class="MatchType">Fatal 4-Way: </span><span class="MatchCard"><a href="?id=2&amp;nr=19353">Maki Itoh</a> defeats <a href="?id=2&amp;nr=18539">Yuki Kamifuku</a> and <a href="?id=2&amp;nr=14219">Mizuki</a> and <a href="?id=2&amp;nr=22930">Pom Harajuku</a></span></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    
    assert match["is_victory"] is True
    assert match["is_multi_sided"] is True
    assert len(match["sides"]) == 4
    assert set(match["sides"][0]["wrestlers"]) == {19353}
    assert match["sides"][0]["is_winner"] is True
    assert set(match["sides"][1]["wrestlers"]) == {18539}
    assert match["sides"][1]["is_winner"] is False
    assert set(match["sides"][2]["wrestlers"]) == {14219}
    assert match["sides"][2]["is_winner"] is False
    assert set(match["sides"][3]["wrestlers"]) == {22930}
    assert match["sides"][3]["is_winner"] is False


def test_team_name_extraction():
    """Test that team names are properly extracted and attached to sides."""
    sample_html = """<tr class="TRow1"><td class="TCol TColSeparator">01.01.2025</td><td class="TCol TColSeparator">
<span class="MatchCard"><a href="?id=28&amp;nr=10833">Kyoraku Kyomei</a> (<a href="?id=2&amp;nr=16613">Hyper Misao</a> &amp; <a href="?id=2&amp;nr=15712">Shoko Nakajima</a>) defeat <a href="?id=2&amp;nr=19649">Miu Watanabe</a> &amp; <a href="?id=2&amp;nr=16650">Rika Tatsumi</a></span></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    
    assert len(match["sides"]) == 2
    # Winner side should have team info
    winner_side = match["sides"][0]
    assert set(winner_side["wrestlers"]) == {16613, 15712}
    assert "team_id" in winner_side
    assert winner_side["team_id"] == 10833
    assert winner_side["team_name"] == "Kyoraku Kyomei"
    assert winner_side["team_type"] == "tag_team"


def test_match_has_version_field():
    """Test that all parsed matches include version=2."""
    sample_html = """<tr class="TRow1"><td class="TCol TColSeparator">01.01.2025</td><td class="TCol TColSeparator">
<span class="MatchCard"><a href="?id=2&amp;nr=4629">Emi Sakura</a> defeats <a href="?id=2&amp;nr=9462">Mei Suruga</a></span></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    
    assert "version" in match
    assert match["version"] == 2


def test_triple_threat_draw():
    """Test a three-way draw (no winner)."""
    sample_html = """<tr class="TRow1"><td class="TCol TColSeparator">01.01.2025</td><td class="TCol TColSeparator">
<span class="MatchType">Triple Threat: </span><span class="MatchCard"><a href="?id=2&amp;nr=4629">Emi Sakura</a> vs. <a href="?id=2&amp;nr=9462">Mei Suruga</a> vs. <a href="?id=2&amp;nr=10402">Yuna Mizumori</a> - No Contest</span></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    
    assert match["is_victory"] is False
    assert match["is_multi_sided"] is True
    assert len(match["sides"]) == 3
    # All sides should be marked as not winning in a draw
    for side in match["sides"]:
        assert side["is_winner"] is False


def test_tag_with_multiple_unlinked_on_same_side():
    """Test tag match where multiple wrestlers on the same side are unlinked."""
    sample_html = """<tr class="TRow1"><td class="TCol TColSeparator">01.01.2025</td><td class="TCol TColSeparator">
<span class="MatchCard">Unknown A &amp; Unknown B defeat <a href="?id=2&amp;nr=828">Aja Kong</a> &amp; <a href="?id=2&amp;nr=4629">Emi Sakura</a></span></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    
    assert match["is_victory"] is True
    assert len(match["sides"]) == 2
    # Winner side should have two -1 sentinels
    assert match["sides"][0]["wrestlers"] == (-1, -1)
    assert set(match["sides"][1]["wrestlers"]) == {828, 4629}
