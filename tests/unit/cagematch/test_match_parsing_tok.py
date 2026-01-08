"""Unit tests for match list parsing."""

from bs4 import BeautifulSoup

from joshirank.cagematch.cm_match import extract_match_data_from_match_page
from joshirank.cagematch.cm_match_token import parse_match


def test_parse_match_list(sample_matches_html):
    """Test parsing Emi Sakura's 2025 match list."""
    matches = list(extract_match_data_from_match_page(sample_matches_html))

    assert len(matches) > 0, "Should parse at least one match"

    # Check first match structure
    first_match = matches[0]
    assert "date" in first_match
    assert "wrestlers" in first_match
    assert "side_a" in first_match
    assert "side_b" in first_match
    assert "is_victory" in first_match
    assert "match_type" in first_match

    # Emi Sakura's ID should appear in wrestlers
    for match in matches:
        assert 4629 in match["wrestlers"], (
            "Emi Sakura (4629) should be in all her matches"
        )


def test_match_has_valid_dates(sample_matches_html):
    """Test that parsed matches have valid date formats."""
    matches = list(extract_match_data_from_match_page(sample_matches_html))

    for match in matches:
        date = match["date"]
        # Date should be ISO format YYYY-MM-DD or "Unknown"
        if date != "Unknown":
            assert len(date) == 10, f"Date should be YYYY-MM-DD format: {date}"
            assert date[4] == "-" and date[7] == "-"


def test_match_sides_are_lists(sample_matches_html):
    """Test that match sides are properly structured."""
    matches = list(extract_match_data_from_match_page(sample_matches_html))

    for match in matches:
        # Match parser returns tuples for sides
        assert isinstance(match["side_a"], (list, tuple))
        assert isinstance(match["side_b"], (list, tuple))
        assert len(match["side_a"]) > 0
        assert len(match["side_b"]) > 0

        # All IDs should be integers
        for wrestler_id in list(match["side_a"]) + list(match["side_b"]):
            assert isinstance(wrestler_id, int)


def test_parsing_of_tag_match_with_unknowns():
    sample_html = '<tr class="TRow2"><td class="TCol AlignCenter TextLowlight">296</td><td class="TCol TColSeparator">29.08.2001</td><td class="TCol TColSeparator"><a href="?id=8&amp;nr=1647"><img alt="Apocalypse Wrestling Federation" class="ImagePromotionLogoMini ImagePromotionLogo_mini" height="18" src="/site/main/img/ligen/normal/1647.gif" title="Apocalypse Wrestling Federation" width="36"/></a></td><td class="TCol TColSeparator">\n<span class="MatchCard">Danny Dynamic &amp; <a href="?id=2&amp;nr=233&amp;name=Miss+Tracy">Miss Tracy</a> defeat <a href="?id=2&amp;nr=1078&amp;name=La+Felina">La Felina</a> &amp; Vladimir Urkov</span><div class="MatchEventLine"><a href="?id=1&amp;nr=145779">AWF Proving Ground II - Tag 13</a> - Event @ Canadian National Exhibition in  Toronto, Ontario, Canada</div></td></tr>'
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    assert match["is_victory"] is True
    assert match["sides"][0] == (-1, 233)
    assert match["sides"][1] == (-1, 1078)
    assert match["country"] == "Canada"


def test_parsing_of_clusterfuck():
    sample_html = """<tr class="TRow1 TRowPayPayView">
    <td class="TCol AlignCenter TextLowlight">1</td>
    <td class="TCol TColSeparator">19.04.2025</td><td class="TCol TColSeparator">
    <a href="?id=8&amp;nr=710">
    <img src="/site/main/img/ligen/normal/710.gif" class="ImagePromotionLogoMini ImagePromotionLogo_mini" width="36" height="18" alt="Game Changer Wrestling" title="Game Changer Wrestling"></a></td><td class="TCol TColSeparator">
<span class="MatchType">Clusterfuck Battle Royal: </span>
<span class="MatchCard"><a href="?id=2&amp;nr=31920&amp;name=Brodie+Lee+Jr.">Brodie Lee Jr.</a> defeats <a href="?id=2&amp;nr=20928&amp;name=1+Called+Manders">1 Called Manders</a> and <a href="?id=2&amp;nr=788&amp;name=2+Tuff+Tony">2 Tuff Tony</a> and <a href="?id=2&amp;nr=13284&amp;name=Aerial+Van+Go">Aerial Van Go</a> and <a href="?id=2&amp;nr=23043&amp;name=Alec+Price">Alec Price</a> and <a href="?id=2&amp;nr=17169&amp;name=Ashley+Vox">Ashley Vox</a> and <a href="?id=2&amp;nr=23904&amp;name=B3CCA">B3CCA</a> and <a href="?id=2&amp;nr=17173&amp;name=Bam+Sullivan">Bam Sullivan</a> and <a href="?id=2&amp;nr=5538&amp;name=Big+F'n+Joe">Big F'n Joe</a> and Blanket Jackson and <a href="?id=2&amp;nr=21419&amp;name=Bobby+Flaco">Bobby Flaco</a> and <a href="?id=2&amp;nr=27510&amp;name=Bodhi+Young+Prodigy">Bodhi Young Prodigy</a> and <a href="?id=2&amp;nr=27492&amp;name=Brad+Baylor">Brad Baylor</a> and <a href="?id=2&amp;nr=27512&amp;name=Brayden+Toon">Brayden Toon</a> and <a href="?id=2&amp;nr=26801&amp;name=Brittnie+Brooks">Brittnie Brooks</a> and <a href="?id=2&amp;nr=17340&amp;name=Channing+Decker">Channing Decker</a> and <a href="?id=2&amp;nr=13278&amp;name=Cheeseburger">Cheeseburger</a> and <a href="?id=2&amp;nr=17541&amp;name=CPA">CPA</a> and <a href="?id=2&amp;nr=2675&amp;name=Dan+Barry">Dan Barry</a> and <a href="?id=2&amp;nr=15267&amp;name=Dani+Mo">Dani Mo</a> and <a href="?id=2&amp;nr=16500&amp;name=Dan+The+Dad">Dan The Dad</a> and <a href="?id=2&amp;nr=23302&amp;name=Davey+Bang">Davey Bang</a> and <a href="?id=2&amp;nr=15929&amp;name=Dr.+Redacted">Dr. Redacted</a> and <a href="?id=2&amp;nr=29673&amp;name=Dustin+Thomas+">Dustin Thomas</a> and <a href="?id=2&amp;nr=17673&amp;name=Effy">Effy</a> and <a href="?id=2&amp;nr=27578&amp;name=Frankie+B">Frankie B</a> and <a href="?id=2&amp;nr=27803&amp;name=Frank+The+Clown">Frank The Clown</a> and <a href="?id=2&amp;nr=9507&amp;name=Harlon+Abbott">Harlon Abbott</a> and <a href="?id=2&amp;nr=1386&amp;name=Human+Tornado">Human Tornado</a> and <a href="?id=2&amp;nr=24644&amp;name=Jack+Cartwheel">Jack Cartwheel</a> and <a href="?id=2&amp;nr=26929&amp;name=Jackson+Drake">Jackson Drake</a> and <a href="?id=2&amp;nr=24629&amp;name=Jai+Vidal">Jai Vidal</a> and <a href="?id=2&amp;nr=29873&amp;name=Jay+Lucas">Jay Lucas</a> and <a href="?id=2&amp;nr=25604&amp;name=Jeffrey+John">Jeffrey John</a> and <a href="?id=2&amp;nr=15787&amp;name=JGeorge">JGeorge</a> and <a href="?id=2&amp;nr=10271&amp;name=Joey+Janela">Joey Janela</a> and <a href="?id=2&amp;nr=8208&amp;name=John+Wayne+Murdoch">John Wayne Murdoch</a> and <a href="?id=2&amp;nr=19622&amp;name=JP+Grayson">JP Grayson</a> and <a href="?id=2&amp;nr=739&amp;name=Juventud+Guerrera">Juventud Guerrera</a> and <a href="?id=2&amp;nr=25610&amp;name=Kerry+Morton">Kerry Morton</a> and <a href="?id=2&amp;nr=25383&amp;name=Kidd+Bandit">Kidd Bandit</a> and Lady KillJoy and <a href="?id=2&amp;nr=20330&amp;name=Lena+Kross">Lena Kross</a> and <a href="?id=2&amp;nr=27338&amp;name=Lou+Nixon">Lou Nixon</a> and <a href="?id=2&amp;nr=21981&amp;name=Man+Like+DeReiss">Man Like DeReiss</a> and <a href="?id=2&amp;nr=15536&amp;name=Manny+Lemons">Manny Lemons</a> and <a href="?id=2&amp;nr=22290&amp;name=Masha+Slamovich">Masha Slamovich</a> and <a href="?id=2&amp;nr=11074&amp;name=Matt+Tremont">Matt Tremont</a> and <a href="?id=2&amp;nr=19878&amp;name=MBM">MBM</a> and MBM's Friend (<a href="?id=2&amp;nr=20604&amp;name=Ultima+Sombra++">Ultima Sombra</a>) and <a href="?id=2&amp;nr=10084&amp;name=Megan+Bayne">Megan Bayne</a> and <a href="?id=2&amp;nr=1118&amp;name=Mickie+Knuckles">Mickie Knuckles</a> and <a href="?id=2&amp;nr=19351&amp;name=Microman">Microman</a> and <a href="?id=2&amp;nr=6800&amp;name=Mike+Jackson">Mike Jackson</a> and <a href="?id=2&amp;nr=19649&amp;name=Miu+Watanabe">Miu Watanabe</a> and <a href="?id=2&amp;nr=521&amp;name=Nate+Webb">Nate Webb</a> and New Roy (Nasty Leroy) and <a href="?id=2&amp;nr=18892&amp;name=Parrow">Parrow</a> and <a href="?id=2&amp;nr=972&amp;name=Paul+London">Paul London</a> and <a href="?id=2&amp;nr=19664&amp;name=Raku">Raku</a> and <a href="?id=2&amp;nr=4002&amp;name=Randy+Myers">Randy Myers</a> and <a href="?id=2&amp;nr=31270&amp;name=Rhys+Maddox">Rhys Maddox</a> and <a href="?id=2&amp;nr=24430&amp;name=Ricky+Smokes">Ricky Smokes</a> and <a href="?id=2&amp;nr=15012&amp;name=Ruffo+The+Clown">Ruffo The Clown</a> and <a href="?id=2&amp;nr=27281&amp;name=Sam+Holloway">Sam Holloway</a> and <a href="?id=2&amp;nr=27544&amp;name=Santana+Jackson">Santana Jackson</a> and <a href="?id=2&amp;nr=27259&amp;name=Shino+Suzuki">Shino Suzuki</a> and <a href="?id=2&amp;nr=22385&amp;name=Shreddy">Shreddy</a>
 and Sleepy Ed and <a href="?id=2&amp;nr=1168&amp;name=Snitsky">Snitsky</a> and <a href="?id=2&amp;nr=20177&amp;name=Sonico+++">Sonico</a> and <a href="?id=2&amp;nr=17540&amp;name=Sonny+Kiss">Sonny Kiss</a> and <a href="?id=2&amp;nr=23219&amp;name=Starboy+Charlie">Starboy Charlie</a> and <a href="?id=2&amp;nr=30170&amp;name=Steven+Crowe">Steven Crowe</a> and <a href="?id=2&amp;nr=164&amp;name=Super+Crazy">Super Crazy</a> and <a href="?id=2&amp;nr=29380&amp;name=Tara+Zep">Tara Zep</a> and <a href="?id=2&amp;nr=25580&amp;name=Terry+Yaki">Terry Yaki</a> and The Invisible Man and <a href="?id=2&amp;nr=1480&amp;name=The+Warlord">The Warlord</a> and <a href="?id=2&amp;nr=15169&amp;name=Thomas+Shire">Thomas Shire</a> and Tombstone Jesus and <a href="?id=2&amp;nr=19965&amp;name=Tommy+Grayson">Tommy Grayson</a> and <a href="?id=2&amp;nr=30859&amp;name=Tommy+Invincible">Tommy Invincible</a> and <a href="?id=2&amp;nr=20534&amp;name=Unagi+Sayaka">Unagi Sayaka</a> and <a href="?id=2&amp;nr=24075&amp;name=Vipress">Vipress</a> and <a href="?id=2&amp;nr=21054&amp;name=Viva+Van">Viva Van</a> and <a href="?id=2&amp;nr=18103&amp;name=Yabo+The+Clown">Yabo The Clown</a> and <a href="?id=2&amp;nr=32145&amp;name=Yoshihiko">Yoshihiko</a> and <a href="?id=2&amp;nr=27789&amp;name=Zayda+Steel">Zayda Steel</a> (139:45)</span><div class="MatchEventLine"><a href="?id=1&amp;nr=416736">GCW Joey Janela's Spring Break: Clusterfuck Forever 2025</a> - Pay Per View @ Pearl Theater At Palms Casino Resort in Las Vegas, Nevada, USA</div></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    print(match["sides"])
    assert match["is_victory"] is True
    assert -1 in match["wrestlers"]  # many unknown wrestlers
    assert match["country"] == "USA"


def test_parsing_of_three_way_tag():
    sample_html = """<tr class="TRow1 TRowPayPayView"><td class="TCol AlignCenter TextLowlight">3</td><td class="TCol TColSeparator">24.11.1996</td><td class="TCol TColSeparator"><a href="?id=8&amp;nr=2"><img src="/site/main/img/ligen/normal/2__1988-199903.gif" class="ImagePromotionLogoMini ImagePromotionLogo_mini" width="36" height="18" alt="World Championship Wrestling" title="World Championship Wrestling"></a></td><td class="TCol TColSeparator">
<span class="MatchType"><a href="?id=5&amp;nr=59">WCW World Tag Team Title</a> Triangle: </span><span class="MatchCard"><a href="?id=28&amp;nr=71&amp;name=The+Outsiders">The Outsiders</a> (<a href="?id=2&amp;nr=429&amp;name=Kevin+Nash">Kevin Nash</a> &amp; <a href="?id=2&amp;nr=807&amp;name=Scott+Hall">Scott Hall</a>) (c) defeat <a href="?id=28&amp;nr=356&amp;name=The+Faces+Of+Fear">The Faces Of Fear</a> (<a href="?id=2&amp;nr=694&amp;name=Meng">Meng</a> &amp; <a href="?id=2&amp;nr=413&amp;name=The+Barbarian">The Barbarian</a>) and <a href="?id=28&amp;nr=67&amp;name=The+Nasty+Boys">The Nasty Boys</a> (<a href="?id=2&amp;nr=633&amp;name=Brian+Knobbs">Brian Knobbs</a> &amp; <a href="?id=2&amp;nr=558&amp;name=Jerry+Sags">Jerry Sags</a>) (16:08)</span><div class="MatchEventLine"><a href="?id=1&amp;nr=1625">WCW World War 3 1996</a> - Pay Per View @ Norfolk Scope in Norfolk, Virginia, USA</div></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    sides = match["sides"]
    print(match["sides"])
    assert match["is_victory"] is True
    assert len(sides) == 3
    assert set(sides[0]) == {429, 807}
    # Winner is first side (is_victory + position determines winner)
    assert 71 in match["teams"]  # The Outsiders team ID
    assert match["teams"][71]["team_name"] == "The Outsiders"
    assert set(match["teams"][71]["members"]) == {429, 807}
    assert set(sides[1]) == {694, 413}
    assert set(sides[2]) == {633, 558}
    assert match["country"] == "USA"


def test_parsing_of_three_way_tag_nc():
    """This is a real match from WCW in 1996 with a three-way tag team match that ended in a no contest."""
    sample_html = """<tr class="TRow2"><td class="TCol AlignCenter TextLowlight">4</td><td class="TCol TColSeparator">18.11.1996</td><td class="TCol TColSeparator"><a href="?id=8&amp;nr=2"><img src="/site/main/img/ligen/normal/2_WCW Monday NITRO_1995-199903.gif" class="ImagePromotionLogoMini ImagePromotionLogo_mini" width="36" height="18" alt="World Championship Wrestling" title="World Championship Wrestling"></a></td><td class="TCol TColSeparator">
<span class="MatchType">Dark Three Way: </span><span class="MatchCard"><a href="?id=2&amp;nr=1256&amp;name=Ciclope">Ciclope</a> &amp; <a href="?id=2&amp;nr=1007&amp;name=Galaxy">Galaxy</a> vs. <a href="?id=28&amp;nr=452&amp;name=High+Voltage">High Voltage</a> (<a href="?id=2&amp;nr=1681&amp;name=Kenny+Kaos">Kenny Kaos</a> &amp; <a href="?id=2&amp;nr=1682&amp;name=Robbie+Rage">Robbie Rage</a>) vs. <a href="?id=28&amp;nr=67&amp;name=The+Nasty+Boys">The Nasty Boys</a> (<a href="?id=2&amp;nr=633&amp;name=Brian+Knobbs">Brian Knobbs</a> &amp; <a href="?id=2&amp;nr=558&amp;name=Jerry+Sags">Jerry Sags</a>) - No Contest</span><div class="MatchEventLine"><a href="?id=1&amp;nr=4091">WCW Monday NITRO #62</a> - Dark Match @ Civic Center in Florence, South Carolina, USA</div></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    sides = match["sides"]
    print(match["sides"])
    assert match["is_victory"] is False
    assert len(sides) == 3
    assert set(sides[0]) == {1256, 1007}
    assert set(sides[1]) == {1681, 1682}
    assert set(sides[2]) == {633, 558}
    assert match["country"] == "USA"


def test_parsing_of_three_way_tag_with_missing():
    """this is a modified version of the above with one unknown wrestler"""
    sample_html = """<tr class="TRow2"><td class="TCol AlignCenter TextLowlight">4</td><td class="TCol TColSeparator">18.11.1996</td><td class="TCol TColSeparator"><a href="?id=8&amp;nr=2"><img src="/site/main/img/ligen/normal/2_WCW Monday NITRO_1995-199903.gif" class="ImagePromotionLogoMini ImagePromotionLogo_mini" width="36" height="18" alt="World Championship Wrestling" title="World Championship Wrestling"></a></td><td class="TCol TColSeparator">
<span class="MatchType">Dark Three Way: </span><span class="MatchCard"><a href="?id=2&amp;nr=1256&amp;name=Ciclope">Ciclope</a> &amp; <a href="?id=2&amp;nr=1007&amp;name=Galaxy">Galaxy</a> vs. <a href="?id=28&amp;nr=452&amp;name=High+Voltage">High Voltage</a> (Kenny Kaos &amp; <a href="?id=2&amp;nr=1682&amp;name=Robbie+Rage">Robbie Rage</a>) vs. <a href="?id=28&amp;nr=67&amp;name=The+Nasty+Boys">The Nasty Boys</a> (<a href="?id=2&amp;nr=633&amp;name=Brian+Knobbs">Brian Knobbs</a> &amp; <a href="?id=2&amp;nr=558&amp;name=Jerry+Sags">Jerry Sags</a>) - No Contest</span><div class="MatchEventLine"><a href="?id=1&amp;nr=4091">WCW Monday NITRO #62</a> - Dark Match @ Civic Center in Florence, South Carolina, USA</div></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    sides = match["sides"]
    print(match["sides"])
    assert match["is_victory"] is False
    assert len(sides) == 3
    assert set(sides[0]) == {1256, 1007}
    assert set(sides[1]) == {-1, 1682}
    assert set(sides[2]) == {633, 558}
    assert match["country"] == "USA"


def test_standard_tag_team():
    sample_html = """<tr class="TRow1 TRowOnlineStream"><td class="TCol AlignCenter TextLowlight">1</td><td class="TCol TColSeparator">04.01.2026</td><td class="TCol TColSeparator"><a href="?id=8&amp;nr=1467"><img src="/site/main/img/ligen/normal/1467__20220828-.gif" class="ImagePromotionLogoMini ImagePromotionLogo_mini" width="36" height="18" alt="Tokyo Joshi Pro-Wrestling" title="Tokyo Joshi Pro-Wrestling"></a></td><td class="TCol TColSeparator">
<span class="MatchCard"><a href="?id=2&amp;nr=27181&amp;name=Toga">Toga</a> &amp; <a href="?id=2&amp;nr=14328&amp;name=Yuna+Manase">Yuna Manase</a> defeat <a href="?id=2&amp;nr=26772&amp;name=HIMAWARI">HIMAWARI</a> &amp; <a href="?id=2&amp;nr=29260&amp;name=Kira+Summer">Kira Summer</a> (9:27)</span><div class="MatchEventLine"><a href="?id=1&amp;nr=439092">TJPW Tokyo Joshi Pro '26</a> - Online Stream @ Korakuen Hall in Tokyo, Japan</div></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    sides = match["sides"]
    print(match["sides"])
    assert match["is_victory"] is True
    assert len(sides) == 2
    assert set(sides[0]) == {27181, 14328}
    assert set(sides[1]) == {26772, 29260}


def test_trios_with_named_tag_subsets():
    sample_html = """<tr class="TRow2 TRowOnlineStream"><td class="TCol AlignCenter TextLowlight">28</td><td class="TCol TColSeparator">08.07.2025</td><td class="TCol TColSeparator"><a href="?id=8&amp;nr=1467"><img src="/site/main/img/ligen/normal/1467__20220828-.gif" class="ImagePromotionLogoMini ImagePromotionLogo_mini" width="36" height="18" alt="Tokyo Joshi Pro-Wrestling" title="Tokyo Joshi Pro-Wrestling"></a></td><td class="TCol TColSeparator">
<span class="MatchCard"><a href="?id=28&amp;nr=10833&amp;name=Kyoraku+Kyomei">Kyoraku Kyomei</a> (<a href="?id=2&amp;nr=16613&amp;name=Hyper+Misao">Hyper Misao</a> &amp; <a href="?id=2&amp;nr=15712&amp;name=Shoko+Nakajima">Shoko Nakajima</a>) &amp; <a href="?id=2&amp;nr=19837&amp;name=Yuki+Aino">Yuki Aino</a> defeat <a href="?id=28&amp;nr=9865&amp;name=Hakuchumu">Hakuchumu</a> (<a href="?id=2&amp;nr=19649&amp;name=Miu+Watanabe">Miu Watanabe</a> &amp; <a href="?id=2&amp;nr=16650&amp;name=Rika+Tatsumi">Rika Tatsumi</a>) &amp; <a href="?id=2&amp;nr=27181&amp;name=Toga">Toga</a> (11:12)</span><div class="MatchEventLine"><a href="?id=1&amp;nr=429720">TJPW Yoshiko Hasegawa Graduation - NonfictioN</a> - Online Stream @ Shinjuku FACE in Tokyo, Japan</div></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    sides = match["sides"]
    print(match["sides"])
    print(match["teams"])
    assert match["is_victory"] is True
    assert len(sides) == 2
    assert set(sides[0]) == {16613, 15712, 19837}

    # Check that we have team data
    assert len(match["teams"]) == 2
    # Kyoraku Kyomei team (ID 10833)
    assert 10833 in match["teams"]
    assert match["teams"][10833]["team_name"] == "Kyoraku Kyomei"
    assert set(match["teams"][10833]["members"]) == {16613, 15712}
    # Hakuchumu team (ID 9865)
    assert 9865 in match["teams"]
    assert match["teams"][9865]["team_name"] == "Hakuchumu"
    assert set(match["teams"][9865]["members"]) == {19649, 16650}

    assert set(sides[1]) == {19649, 16650, 27181}


def test_standard_singles():
    sample_html = """<tr class="TRow1 TRowOnlineStream"><td class="TCol AlignCenter TextLowlight">133</td><td class="TCol TColSeparator">03.09.2023</td><td class="TCol TColSeparator"><a href="?id=8&amp;nr=1467"><img src="/site/main/img/ligen/normal/1467__20220828-.gif" class="ImagePromotionLogoMini ImagePromotionLogo_mini" width="36" height="18" alt="Tokyo Joshi Pro-Wrestling" title="Tokyo Joshi Pro-Wrestling"></a></td><td class="TCol TColSeparator">
<span class="MatchCard"><a href="?id=2&amp;nr=27181&amp;name=Toga">Toga</a> defeats <a href="?id=2&amp;nr=27259&amp;name=Shino+Suzuki">Shino Suzuki</a> (6:13)</span><div class="MatchEventLine"><a href="?id=1&amp;nr=375188">TJPW City Circuit '23 ~ Autumn Tour Opening Rounds ~</a> - Online Stream @ Otemachi Mitsui Hall in Tokyo, Japan</div></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    sides = match["sides"]
    print(match["sides"])
    assert match["is_victory"] is True
    assert len(sides) == 2
    assert set(sides[0]) == {27181}
    assert set(sides[1]) == {27259}
    assert match["country"] == "Japan"


def test_singles_with_unknown():
    sample_html = """<tr class="TRow2"><td class="TCol AlignCenter TextLowlight">28</td><td class="TCol TColSeparator">05.05.2009</td><td class="TCol TColSeparator"><a href="?id=8&amp;nr=2379"><img src="/site/main/img/ligen/normal/2379.gif" class="ImagePromotionLogoMini ImagePromotionLogo_mini" width="36" height="18" alt="Wrestling In Japan - Freelance Shows" title="Wrestling In Japan - Freelance Shows"></a></td><td class="TCol TColSeparator">
<span class="MatchType"><a href="?id=5&amp;nr=4380">DDT Iron Man Heavy Metal Title</a>: </span><span class="MatchCard">Mr. Kasai defeats <a href="?id=2&amp;nr=828&amp;name=Aja+Kong">Aja Kong</a> (c) - <span class="MatchTitleChange">TITLE CHANGE !!!</span></span><div class="MatchEventLine"><a href="?id=1&amp;nr=253173">Cherry Produce Fantasy Illusion 2</a> - Event @ Itabashi Green Hall in Tokyo, Japan</div></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    match = parse_match(soup)
    sides = match["sides"]

    assert match["is_victory"] is True
    assert len(sides) == 2
    assert set(sides[0]) == {-1}
    assert set(sides[1]) == {828}
    assert match["country"] == "Japan"
    assert -1 in match["wrestler_names"]
    assert match["wrestler_names"][-1] == ["Mr. Kasai"]
