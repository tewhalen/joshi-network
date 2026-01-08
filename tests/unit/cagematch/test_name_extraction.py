from bs4 import BeautifulSoup

from joshirank.cagematch.cm_match_embed import extract_gimmick_names


def test_parsing_of_three_way_tag_names():
    """This is a real match from WCW in 1996 with a three-way tag team match that ended in a no contest."""
    sample_html = """<tr class="TRow2"><td class="TCol AlignCenter TextLowlight">4</td><td class="TCol TColSeparator">18.11.1996</td><td class="TCol TColSeparator"><a href="?id=8&amp;nr=2"><img src="/site/main/img/ligen/normal/2_WCW Monday NITRO_1995-199903.gif" class="ImagePromotionLogoMini ImagePromotionLogo_mini" width="36" height="18" alt="World Championship Wrestling" title="World Championship Wrestling"></a></td><td class="TCol TColSeparator">
<span class="MatchType">Dark Three Way: </span><span class="MatchCard"><a href="?id=2&amp;nr=1256&amp;name=Ciclope">Ciclope</a> &amp; <a href="?id=2&amp;nr=1007&amp;name=Galaxy">Galaxy</a> vs. <a href="?id=28&amp;nr=452&amp;name=High+Voltage">High Voltage</a> (<a href="?id=2&amp;nr=1681&amp;name=Kenny+Kaos">Kenny Kaos</a> &amp; <a href="?id=2&amp;nr=1682&amp;name=Robbie+Rage">Robbie Rage</a>) vs. <a href="?id=28&amp;nr=67&amp;name=The+Nasty+Boys">The Nasty Boys</a> (<a href="?id=2&amp;nr=633&amp;name=Brian+Knobbs">Brian Knobbs</a> &amp; <a href="?id=2&amp;nr=558&amp;name=Jerry+Sags">Jerry Sags</a>) - No Contest</span><div class="MatchEventLine"><a href="?id=1&amp;nr=4091">WCW Monday NITRO #62</a> - Dark Match @ Civic Center in Florence, South Carolina, USA</div></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    names = extract_gimmick_names(soup)

    assert names == {
        1256: "Ciclope",
        1007: "Galaxy",
        1681: "Kenny Kaos",
        1682: "Robbie Rage",
        633: "Brian Knobbs",
        558: "Jerry Sags",
    }


def test_singles_with_unknown():
    sample_html = """<tr class="TRow2"><td class="TCol AlignCenter TextLowlight">28</td><td class="TCol TColSeparator">05.05.2009</td><td class="TCol TColSeparator"><a href="?id=8&amp;nr=2379"><img src="/site/main/img/ligen/normal/2379.gif" class="ImagePromotionLogoMini ImagePromotionLogo_mini" width="36" height="18" alt="Wrestling In Japan - Freelance Shows" title="Wrestling In Japan - Freelance Shows"></a></td><td class="TCol TColSeparator">
<span class="MatchType"><a href="?id=5&amp;nr=4380">DDT Iron Man Heavy Metal Title</a>: </span><span class="MatchCard">Mr. Kasai defeats <a href="?id=2&amp;nr=828&amp;name=Aja+Kong">Aja Kong</a> (c) - <span class="MatchTitleChange">TITLE CHANGE !!!</span></span><div class="MatchEventLine"><a href="?id=1&amp;nr=253173">Cherry Produce Fantasy Illusion 2</a> - Event @ Itabashi Green Hall in Tokyo, Japan</div></td></tr>"""
    soup = BeautifulSoup(sample_html, "html.parser")
    names = extract_gimmick_names(soup)
    assert names == {828: "Aja Kong", -1: "Mr. Kasai"}
