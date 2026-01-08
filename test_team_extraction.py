#!/usr/bin/env python3
"""Test team extraction functionality."""

from bs4 import BeautifulSoup

from joshirank.cagematch.cm_match import parse_match

# Test case 1: Tag match with team links (both sides have teams)
html_tag_with_teams = """
<tr class="TRow1">
    <td class="TCol">30.12.2024</td>
    <td class="TCol">
        <span class="MatchType">Tag Team: </span>
        <span class="MatchCard">
            <a href="?id=28&amp;nr=7325&amp;name=Azure+Revolution">Azure Revolution</a> 
            (<a href="?id=2&amp;nr=15833&amp;name=Maya+Yukihi">Maya Yukihi</a> &amp; 
            <a href="?id=2&amp;nr=12695&amp;name=Risa+Sera">Risa Sera</a>) 
            defeat 
            <a href="?id=2&amp;nr=20998&amp;name=Haruka+Umesaki">Haruka Umesaki</a> &amp; 
            <a href="?id=2&amp;nr=9468&amp;name=Miyako+Matsumoto">Miyako Matsumoto</a>
        </span>
        <div class="MatchEventLine">Test Event</div>
    </td>
</tr>
"""

# Test case 2: Tag match with stable link
html_stable = """
<tr class="TRow1">
    <td class="TCol">30.12.2024</td>
    <td class="TCol">
        <span class="MatchType">Tag Team: </span>
        <span class="MatchCard">
            <a href="?id=29&amp;nr=4140&amp;name=HATE++">HATE</a> 
            (<a href="?id=2&amp;nr=18714&amp;name=Natsuko+Tora">Natsuko Tora</a> &amp; 
            <a href="?id=2&amp;nr=18723&amp;name=Ruaka">Ruaka</a>) 
            defeat 
            <a href="?id=2&amp;nr=20998&amp;name=Haruka+Umesaki">Haruka Umesaki</a> &amp; 
            <a href="?id=2&amp;nr=27941&amp;name=Mei+Seira">Mei Seira</a>
        </span>
        <div class="MatchEventLine">Test Event</div>
    </td>
</tr>
"""

# Test case 3: Tag match without team links (should have no team info)
html_no_teams = """
<tr class="TRow1">
    <td class="TCol">30.12.2024</td>
    <td class="TCol">
        <span class="MatchType">Tag Team: </span>
        <span class="MatchCard">
            <a href="?id=2&amp;nr=9462&amp;name=Hikaru+Shida">Hikaru Shida</a> &amp;
            <a href="?id=2&amp;nr=10402&amp;name=Mayu+Iwatani">Mayu Iwatani</a> defeat
            <a href="?id=2&amp;nr=4629&amp;name=Emi+Sakura">Emi Sakura</a> &amp;
            <a href="?id=2&amp;nr=9434&amp;name=Riho">Riho</a>
        </span>
        <div class="MatchEventLine">Test Event</div>
    </td>
</tr>
"""

# Test case 4: Partial team (3 wrestlers, team should NOT be extracted)
html_partial_team = """
<tr class="TRow1">
    <td class="TCol">30.12.2024</td>
    <td class="TCol">
        <span class="MatchType">Tag Team: </span>
        <span class="MatchCard">
            <a href="?id=2&amp;nr=20998&amp;name=Haruka+Umesaki">Haruka Umesaki</a> &amp; 
            <a href="?id=29&amp;nr=4139&amp;name=Neo+Genesis">Neo Genesis</a> 
            (<a href="?id=2&amp;nr=25831&amp;name=Miyu+Amasaki">Miyu Amasaki</a> &amp; 
            <a href="?id=2&amp;nr=17563&amp;name=Starlight+Kid">Starlight Kid</a>) 
            defeat 
            <a href="?id=29&amp;nr=4140&amp;name=HATE++">HATE</a> 
            (<a href="?id=2&amp;nr=16624&amp;name=Konami">Konami</a>, 
            <a href="?id=2&amp;nr=20416&amp;name=Rina">Rina</a> &amp; 
            <a href="?id=2&amp;nr=18723&amp;name=Ruaka">Ruaka</a>)
        </span>
        <div class="MatchEventLine">Test Event</div>
    </td>
</tr>
"""


def test_match(name, html):
    print(f"\n{'=' * 70}")
    print(f"Testing: {name}")
    print("=" * 70)
    soup = BeautifulSoup(html, "html.parser")
    match_row = soup.find("tr")
    result = parse_match(match_row)

    print(f"Version: {result.get('version')}")
    print(f"Side A: {result.get('side_a')}")
    print(f"Side B: {result.get('side_b')}")
    print("\nSides structure:")
    for i, side in enumerate(result["sides"]):
        print(f"  Side {i}:")
        print(f"    wrestlers: {side['wrestlers']}")
        print(f"    is_winner: {side['is_winner']}")
        if "team_id" in side:
            print(f"    team_id: {side['team_id']}")
            print(f"    team_name: {side['team_name']}")
            print(f"    team_type: {side['team_type']}")
        else:
            print("    (no team info)")


if __name__ == "__main__":
    test_match("Tag match with team link (Azure Revolution)", html_tag_with_teams)
    test_match("Tag match with stable link (HATE)", html_stable)
    test_match("Tag match without team links", html_no_teams)
    test_match("Partial team (should NOT extract team info)", html_partial_team)

    print(f"\n{'=' * 70}")
    print("TEST COMPLETE")
    print("=" * 70)
