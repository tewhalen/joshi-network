"""Unit tests for the match tokenizer."""

import datetime

from bs4 import BeautifulSoup

from joshirank.cagematch.match_tokenizer import (
    DateToken,
    EventToken,
    MatchTypeToken,
    NamedTeamToken,
    ParenthesisToken,
    PromotionToken,
    SeparatorToken,
    TextToken,
    WrestlerToken,
    match_tokenizer,
)

# Sample HTML fixtures
SAMPLE_THREE_WAY_TAG = BeautifulSoup(
    """<tr class="TRow2">
    <td class="TCol AlignCenter TextLowlight">4</td>
    <td class="TCol TColSeparator">18.11.1996</td>
    <td class="TCol TColSeparator">
        <a href="?id=8&amp;nr=2">
            <img src="/site/main/img/ligen/normal/2_WCW Monday NITRO_1995-199903.gif" class="ImagePromotionLogoMini ImagePromotionLogo_mini" width="36" height="18" alt="World Championship Wrestling" title="World Championship Wrestling">
        </a></td>
    <td class="TCol TColSeparator">
        <span class="MatchType">Dark Three Way: </span>
        <span class="MatchCard">
            <a href="?id=2&amp;nr=1256&amp;name=Ciclope">Ciclope</a> &amp; <a href="?id=2&amp;nr=1007&amp;name=Galaxy">Galaxy</a> vs. <a href="?id=28&amp;nr=452&amp;name=High+Voltage">High Voltage</a> (<a href="?id=2&amp;nr=1681&amp;name=Kenny+Kaos">Kenny Kaos</a> &amp; <a href="?id=2&amp;nr=1682&amp;name=Robbie+Rage">Robbie Rage</a>) vs. <a href="?id=28&amp;nr=67&amp;name=The+Nasty+Boys">The Nasty Boys</a> (<a href="?id=2&amp;nr=633&amp;name=Brian+Knobbs">Brian Knobbs</a> &amp; <a href="?id=2&amp;nr=558&amp;name=Jerry+Sags">Jerry Sags</a>) - No Contest
        </span>
        <div class="MatchEventLine">
            <a href="?id=1&amp;nr=4091">WCW Monday NITRO #62</a> - Dark Match @ Civic Center in Florence, South Carolina, USA
        </div>
        </td></tr>""",
    "html.parser",
)

SAMPLE_CLUSTERFUCK = BeautifulSoup(
    """<tr class="TRow1 TRowPayPayView">
    <td class="TCol AlignCenter TextLowlight">1</td>
    <td class="TCol TColSeparator">19.04.2025</td><td class="TCol TColSeparator">
    <a href="?id=8&amp;nr=710">
    <img src="/site/main/img/ligen/normal/710.gif" class="ImagePromotionLogoMini ImagePromotionLogo_mini" width="36" height="18" alt="Game Changer Wrestling" title="Game Changer Wrestling"></a></td><td class="TCol TColSeparator">
<span class="MatchType">Clusterfuck Battle Royal: </span>
<span class="MatchCard"><a href="?id=2&amp;nr=31920&amp;name=Brodie+Lee+Jr.">Brodie Lee Jr.</a> defeats <a href="?id=2&amp;nr=20928&amp;name=1+Called+Manders">1 Called Manders</a> and <a href="?id=2&amp;nr=788&amp;name=2+Tuff+Tony">2 Tuff Tony</a> and Blanket Jackson and <a href="?id=2&amp;nr=22385&amp;name=Shreddy">Shreddy</a> and Sleepy Ed and <a href="?id=2&amp;nr=1168&amp;name=Snitsky">Snitsky</a></span><div class="MatchEventLine"><a href="?id=1&amp;nr=416736">GCW Joey Janela's Spring Break: Clusterfuck Forever 2025</a> - Pay Per View @ Pearl Theater At Palms Casino Resort in Las Vegas, Nevada, USA</div></td></tr>""",
    "html.parser",
)

SAMPLE_TAG_WITH_UNLINKED = BeautifulSoup(
    """<tr class="TRow1 TRowPayPayView"><td class="TCol AlignCenter TextLowlight">1</td><td class="TCol TColSeparator">03.01.2026</td><td class="TCol TColSeparator"><a href="?id=8&amp;nr=710"><img src="/site/main/img/ligen/normal/710.gif" class="ImagePromotionLogoMini ImagePromotionLogo_mini" width="36" height="18" alt="Game Changer Wrestling" title="Game Changer Wrestling"></a></td><td class="TCol TColSeparator">
<span class="MatchCard"><a href="?id=28&amp;nr=9524&amp;name=Bang+and+Matthews">Bang and Matthews</a> (<a href="?id=2&amp;nr=26444&amp;name=August+Matthews">August Matthews</a> &amp; <a href="?id=2&amp;nr=23302&amp;name=Davey+Bang">Davey Bang</a>) defeat <a href="?id=2&amp;nr=25905&amp;name=Anakin+Murphy">Anakin Murphy</a> &amp; Logan Cavazos (9:51)</span><div class="MatchEventLine"><a href="?id=1&amp;nr=439072">GCW One Night Only 2026</a> - Pay Per View @ Berwyn Eagles Club in Berwyn, Illinois, USA</div></td></tr>
""",
    "html.parser",
)


def test_tokenizer_extracts_date():
    """Test that dates are properly extracted."""
    tokens = match_tokenizer(SAMPLE_THREE_WAY_TAG)
    date_tokens = [t for t in tokens if isinstance(t, DateToken)]

    assert len(date_tokens) == 1
    assert date_tokens[0].text == "18.11.1996"


def test_tokenizer_extracts_match_type():
    """Test that match types are properly extracted."""
    tokens = match_tokenizer(SAMPLE_THREE_WAY_TAG)
    match_type_tokens = [t for t in tokens if isinstance(t, MatchTypeToken)]

    assert len(match_type_tokens) == 1
    assert "Dark Three Way" in match_type_tokens[0].match_type


def test_tokenizer_extracts_wrestlers():
    """Test that wrestler links are properly extracted."""
    tokens = match_tokenizer(SAMPLE_THREE_WAY_TAG)
    wrestler_tokens = [t for t in tokens if isinstance(t, WrestlerToken)]

    wrestler_names = [t.name for t in wrestler_tokens]
    assert "Ciclope" in wrestler_names
    assert "Galaxy" in wrestler_names
    assert "Kenny Kaos" in wrestler_names
    assert "Robbie Rage" in wrestler_names
    assert "Brian Knobbs" in wrestler_names
    assert "Jerry Sags" in wrestler_names


def test_tokenizer_extracts_named_teams():
    """Test that named tag teams are properly extracted."""
    tokens = match_tokenizer(SAMPLE_THREE_WAY_TAG)
    team_tokens = [t for t in tokens if isinstance(t, NamedTeamToken)]

    team_names = [t.team_name for t in team_tokens]
    assert "High Voltage" in team_names
    assert "The Nasty Boys" in team_names

    # Check team types
    for team in team_tokens:
        assert team.team_type == "tag_team"


def test_tokenizer_extracts_separators():
    """Test that match separators are properly identified."""
    tokens = match_tokenizer(SAMPLE_THREE_WAY_TAG)
    separator_tokens = [t for t in tokens if isinstance(t, SeparatorToken)]

    # Should have team_join (&) and versus (vs.) separators
    separators = [t.separator for t in separator_tokens]
    assert "team_join" in separators
    assert "versus" in separators


def test_tokenizer_extracts_parentheses():
    """Test that parentheses are properly tokenized."""
    tokens = match_tokenizer(SAMPLE_THREE_WAY_TAG)
    paren_tokens = [t for t in tokens if isinstance(t, ParenthesisToken)]

    # Named teams have parenthesized member lists
    assert len(paren_tokens) >= 4  # Two teams, each with ( and )
    assert any(t.paren == "(" for t in paren_tokens)
    assert any(t.paren == ")" for t in paren_tokens)


def test_tokenizer_extracts_promotion():
    """Test that promotion links are properly extracted."""
    tokens = match_tokenizer(SAMPLE_THREE_WAY_TAG)
    promotion_tokens = [t for t in tokens if isinstance(t, PromotionToken)]

    assert len(promotion_tokens) == 1
    assert promotion_tokens[0].promotion_id == 2


def test_tokenizer_extracts_event():
    """Test that event links are properly extracted."""
    tokens = match_tokenizer(SAMPLE_THREE_WAY_TAG)
    event_tokens = [t for t in tokens if isinstance(t, EventToken)]

    assert len(event_tokens) == 1
    assert event_tokens[0].event_id == 4091
    assert "WCW Monday NITRO" in event_tokens[0].event_name


def test_tokenizer_preserves_unlinked_wrestlers():
    """Test that unlinked wrestler names are preserved as TextTokens."""
    tokens = match_tokenizer(SAMPLE_CLUSTERFUCK)

    # Find text tokens that are wrestler names
    text_tokens = [t for t in tokens if isinstance(t, TextToken)]
    text_values = [t.text for t in text_tokens]

    # These wrestlers have no CageMatch links
    assert "Blanket Jackson" in text_values
    assert "Sleepy Ed" in text_values


def test_tokenizer_splits_text_on_separators():
    """Test that text containing separators is properly split."""
    tokens = match_tokenizer(SAMPLE_CLUSTERFUCK)

    # The sequence "and Sleepy Ed and" should be split into:
    # SeparatorToken('and'), TextToken('Sleepy Ed'), SeparatorToken('and')
    found_sequence = False
    for i, token in enumerate(tokens):
        if (
            isinstance(token, SeparatorToken)
            and token.separator == "side_join"
            and i + 2 < len(tokens)
            and isinstance(tokens[i + 1], TextToken)
            and tokens[i + 1].text == "Sleepy Ed"
            and isinstance(tokens[i + 2], SeparatorToken)
            and tokens[i + 2].separator == "side_join"
        ):
            found_sequence = True
            break

    assert found_sequence, (
        "Expected 'and Sleepy Ed and' to be split into separate tokens"
    )


def test_tokenizer_handles_victory_separator():
    """Test that 'defeats' is recognized as a victory separator."""
    tokens = match_tokenizer(SAMPLE_CLUSTERFUCK)
    separator_tokens = [t for t in tokens if isinstance(t, SeparatorToken)]

    victory_separators = [t for t in separator_tokens if t.separator == "victory"]
    assert len(victory_separators) >= 1


def test_tokenizer_handles_unlinked_in_tag_team():
    """Test that unlinked wrestler in tag team is preserved."""
    tokens = match_tokenizer(SAMPLE_TAG_WITH_UNLINKED)

    # Find the sequence: Anakin Murphy & Logan Cavazos
    wrestler_tokens = [t for t in tokens if isinstance(t, WrestlerToken)]
    text_tokens = [t for t in tokens if isinstance(t, TextToken)]

    # Anakin Murphy should be a WrestlerToken
    assert any(t.name == "Anakin Murphy" for t in wrestler_tokens)

    # Logan Cavazos should be a TextToken (unlinked)
    assert any(t.text == "Logan Cavazos" for t in text_tokens)


def test_tokenizer_preserves_match_time():
    """Test that match time in parentheses is preserved."""
    tokens = match_tokenizer(SAMPLE_TAG_WITH_UNLINKED)

    # Match time (9:51) should be preserved
    text_tokens = [t for t in tokens if isinstance(t, TextToken)]
    assert any(t.text == "9:51" for t in text_tokens)


def test_tokenizer_handles_team_with_word_and():
    """Test that team name containing 'and' is not split."""
    tokens = match_tokenizer(SAMPLE_TAG_WITH_UNLINKED)
    team_tokens = [t for t in tokens if isinstance(t, NamedTeamToken)]

    # "Bang and Matthews" should be one team token, not split on "and"
    assert any(t.team_name == "Bang and Matthews" for t in team_tokens)


def test_tokenizer_handles_parentheses_with_text():
    """Test that text with embedded parentheses is properly split."""
    tokens = match_tokenizer(SAMPLE_TAG_WITH_UNLINKED)

    # "Logan Cavazos (9:51)" should become:
    # TextToken("Logan Cavazos"), ParenthesisToken("("), TextToken("9:51"), ParenthesisToken(")")
    found_sequence = False
    for i, token in enumerate(tokens):
        if (
            isinstance(token, TextToken)
            and token.text == "Logan Cavazos"
            and i + 3 < len(tokens)
            and isinstance(tokens[i + 1], ParenthesisToken)
            and tokens[i + 1].paren == "("
            and isinstance(tokens[i + 2], TextToken)
            and tokens[i + 2].text == "9:51"
            and isinstance(tokens[i + 3], ParenthesisToken)
            and tokens[i + 3].paren == ")"
        ):
            found_sequence = True
            break

    assert found_sequence, "Expected 'Logan Cavazos (9:51)' to be properly tokenized"


def test_tokenizer_finds_date():
    """Test that date token is found and correct."""
    tokens = match_tokenizer(SAMPLE_THREE_WAY_TAG)
    date_tokens = [t for t in tokens if isinstance(t, DateToken)]

    assert len(date_tokens) == 1
    assert date_tokens[0].text == "18.11.1996"
    assert date_tokens[0].date == datetime.date(1996, 11, 18)


def test_tokenizer_finds_partial_date():
    """Test that a partial date token is found and correct."""
    modified_html = BeautifulSoup(
        str(SAMPLE_THREE_WAY_TAG).replace("18.11.1996", "11.1996"),
        "html.parser",
    )
    tokens = match_tokenizer(modified_html)
    date_tokens = [t for t in tokens if isinstance(t, DateToken)]

    assert len(date_tokens) == 1
    assert date_tokens[0].text == "11.1996"
    assert date_tokens[0].date == datetime.date(1996, 11, 1)


def test_tokenizer_dates():
    sample_html = '<tr class="TRow1 TRowOnlineStream"><td class="TCol AlignCenter TextLowlight">1</td><td class="TCol TColSeparator">31.12.2025</td><td class="TCol TColSeparator"><a href="?id=8&amp;nr=2143"><img alt="ChocoPro" class="ImagePromotionLogoMini ImagePromotionLogo_mini" height="18" src="/site/main/img/ligen/normal/2143__20241006-.gif" title="ChocoPro" width="36"/></a></td><td class="TCol TColSeparator">\n<span class="MatchCard"><a href="?id=2&amp;nr=21376&amp;name=Chie+Koishikawa">Chie Koishikawa</a>, <a href="?id=2&amp;nr=4629&amp;name=Emi+Sakura">Emi Sakura</a>, <a href="?id=2&amp;nr=21423&amp;name=Sayaka">Sayaka</a> &amp; <a href="?id=2&amp;nr=21426&amp;name=Tokiko+Kirihara">Tokiko Kirihara</a> defeat <a href="?id=2&amp;nr=29562&amp;name=Erii+Kanae">Erii Kanae</a>, <a href="?id=2&amp;nr=30089&amp;name=Hiyori+Yawata">Hiyori Yawata</a>, <a href="?id=2&amp;nr=31375&amp;name=Kaho+Hiromi">Kaho Hiromi</a> &amp; <a href="?id=2&amp;nr=19811&amp;name=Mei+Suruga">Mei Suruga</a> (17:50)</span><div class="MatchEventLine"><a href="?id=1&amp;nr=443207">ChocoPro #497</a> - Online Stream @ Ichigaya Chocolate Hiroba in Tokyo, Japan</div></td></tr>'
    soup = BeautifulSoup(sample_html, "html.parser")
    tokens = match_tokenizer(soup)
    date_tokens = [t for t in tokens if isinstance(t, DateToken)]
    assert len(date_tokens) == 1
    assert date_tokens[0].text == "31.12.2025"
    assert date_tokens[0].date == datetime.date(2025, 12, 31)


def test_multiple_promotion():
    """Turns out that some matches have multiple promotion links."""
    sample_html = """<tr class="TRow1 TRowTVShow">
    <td class="TCol AlignCenter TextLowlight">5</td>
    <td class="TCol TColSeparator">29.11.1949</td>
    <td class="TCol TColSeparator"><a href="?id=8&amp;nr=208">
      <img src="/site/main/img/ligen/normal/208.gif" class="ImagePromotionLogoMini ImagePromotionLogo_mini" width="36" height="18" alt="Central States Wrestling" title="Central States Wrestling"></a>
      <a href="?id=8&amp;nr=9"><img src="/site/main/img/ligen/normal/9.gif" class="ImagePromotionLogoMini ImagePromotionLogo_mini" width="36" height="18" alt="National Wrestling Alliance" title="National Wrestling Alliance"></a></td>
    <td class="TCol TColSeparator">
<span class="MatchType">World Women's  Title Best Two Out Of Three Falls: </span><span class="MatchCard"><a href="?id=2&amp;nr=3145&amp;name=Mildred+Burke">Mildred Burke</a> (c) defeats Marie McFarland [2:0]</span><div class="MatchEventLine"><a href="?id=1&amp;nr=145585">CSW TV</a> - TV-Show @ World War II Memorial Building in Kansas City, Missouri, USA</div></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")

    tokens = match_tokenizer(soup)
    promotion_tokens = [t for t in tokens if isinstance(t, PromotionToken)]
    assert len(promotion_tokens) == 2
