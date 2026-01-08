from collections import defaultdict
from dataclasses import dataclass
from typing import Literal

from bs4 import BeautifulSoup

from joshirank.cagematch.cm_match import MatchDict
from joshirank.cagematch.match_tokenizer import (
    DateToken,
    EventDetailToken,
    EventToken,
    MatchTypeToken,
    NamedTeamToken,
    ParenthesisToken,
    PromotionToken,
    SeparatorToken,
    SpanToken,
    TextToken,
    WrestlerToken,
    match_tokenizer,
)


@dataclass
class ParseState:
    """State machine for parsing match tokens."""

    # Match metadata
    date: str | None = None
    promotion_id: int | None = None
    promotion_name: str | None = None
    event_id: int | None = None
    event_name: str | None = None
    match_type: str | None = None
    country: str | None = None

    # Result tracking
    is_victory: bool | None = None  # None = not yet determined
    found_main_separator: bool = False
    in_match_card: bool = False  # Are we inside the MatchCard span?

    # Side/team building
    all_sides: list[list[int]] = (
        None  # List of sides, each side is list of wrestler IDs
    )
    current_side: list[int] = None  # Current side being built
    in_parentheses: bool = False  # Are we inside parentheses?
    current_team: NamedTeamToken | None = None  # Named team being processed
    current_team_members: list[int] = None  # Track wrestlers in current team
    expecting_wrestler: bool = (
        True  # Are we expecting a wrestler next? (vs TextToken metadata)
    )
    teams: dict[int, dict] = None  # Map team_id to team metadata + members

    # Wrestler tracking
    all_wrestlers: set[int] = None
    wrestler_names: dict[int, list[str]] = None  # wrestler_id -> list of name variants

    def __post_init__(self):
        """Initialize mutable defaults."""
        if self.all_sides is None:
            self.all_sides = []
        if self.current_side is None:
            self.current_side = []
        if self.all_wrestlers is None:
            self.all_wrestlers = set()
        if self.wrestler_names is None:
            self.wrestler_names = defaultdict(list)

        if self.teams is None:
            self.teams = {}
        if self.current_team_members is None:
            self.current_team_members = []

    def start_new_side(self):
        """Finish current side and start a new one."""
        if self.current_side:
            self.all_sides.append(self.current_side)
            self.current_side = []
            # Don't reset current_team here - it might span multiple sides

    def add_wrestler(self, wrestler_id: int, name: str):
        """Add a wrestler to the current side."""
        self.current_side.append(wrestler_id)
        self.all_wrestlers.add(wrestler_id)
        self.wrestler_names[wrestler_id].append(name)
        self.expecting_wrestler = (
            False  # Next TextToken is likely metadata, not a wrestler
        )

        # If we're in parentheses after a NamedTeamToken, track this as a team member
        if self.in_parentheses and self.current_team:
            self.current_team_members.append(wrestler_id)

    def add_unlinked_wrestler(self, name: str):
        """Add an unlinked wrestler (no CageMatch ID) to tracking."""
        # Use -1 as sentinel for unlinked wrestlers
        self.current_side.append(-1)
        self.all_wrestlers.add(-1)  # Track -1 in all_wrestlers too

        self.wrestler_names[-1].append(name)  # Add to wrestler_names dict too
        self.expecting_wrestler = (
            False  # Next TextToken is likely metadata, not a wrestler
        )

    def finalize(self):
        """Finish parsing by adding final side."""
        if self.current_side:
            self.all_sides.append(self.current_side)

    def final_sides(self) -> list[tuple[int, ...]]:
        """Return sides as sorted tuples, not lists"""
        return [tuple(sorted(side)) for side in self.all_sides]


def parse_match(match: BeautifulSoup) -> MatchDict:
    """Turn match soup into a dictionary, extracting all relevant info.

    Uses the tokenizer to extract structured data, then builds match sides
    using a state machine that tracks:
    - Whether we're inside parentheses (team members)
    - Which side we're building (winner vs losers)
    - Named teams and their members
    - Unlinked wrestlers (names without IDs)

    Args:
        match: BeautifulSoup object representing the match row
    Returns:
        MatchDict with extracted info
    """
    tokens = list(match_tokenizer(match))
    state = ParseState()

    for token in tokens:
        match token:
            # Track when we're in the MatchCard span (only process wrestlers/sides here)
            case SpanToken(attrs=attrs):
                if "MatchCard" in attrs.get("class", []):
                    state.in_match_card = True

            # Extract metadata (promotion, event, date, etc)
            case PromotionToken(promotion_id=pid, promotion_name=pname):
                state.promotion_id = pid
                state.promotion_name = pname

            case EventToken(event_id=eid, event_name=ename):
                state.event_id = eid
                state.event_name = ename

            case DateToken(text=date_text):
                state.date = date_text

            case MatchTypeToken(match_type=mtype):
                state.match_type = mtype

            case EventDetailToken(country=country):
                state.country = country

            case _ if not state.in_match_card:
                # Only process match structure within MatchCard span
                continue

            # Track parentheses (for named team members)
            case ParenthesisToken(paren="("):
                state.in_parentheses = True

            case ParenthesisToken(paren=")"):
                state.in_parentheses = False

                # If we have team members, store the team
                if state.current_team and state.current_team_members:
                    state.teams[state.current_team.team_id] = {
                        "team_name": state.current_team.team_name,
                        "team_type": state.current_team.team_type,
                        "members": tuple(sorted(state.current_team_members)),
                    }
                    # Reset for next team
                    state.current_team = None
                    state.current_team_members = []

            # Named teams
            case NamedTeamToken():
                state.current_team = token

            # Wrestlers
            case WrestlerToken(id=wid, name=name):
                state.add_wrestler(wid, name)

            # Unlinked wrestlers (text between separators or wrestlers)
            case TextToken(text=text) if state.expecting_wrestler:
                # Check if this looks like a wrestler name (not a match result or metadata)
                # Heuristic: wrestler names are typically short, not sentences
                text = text.strip()
                if len(text) > 0 and len(text) < 50 and not text.startswith("-"):
                    # Could be an unlinked wrestler
                    state.add_unlinked_wrestler(text)

            # Separators control side/team structure
            case SeparatorToken(separator="team_join"):
                # "&" joins wrestlers on same side - expect another wrestler
                state.expecting_wrestler = True

            case SeparatorToken(separator="versus"):
                # "vs." starts a new side (only if not in parentheses)
                if not state.in_parentheses:
                    state.start_new_side()
                state.expecting_wrestler = True

            case SeparatorToken(separator="side_join"):
                # "and" could be side separator or within description
                # If we've seen the main separator, "and" separates sides
                if state.found_main_separator and not state.in_parentheses:
                    state.start_new_side()
                state.expecting_wrestler = True

            case SeparatorToken(separator="victory"):
                # "defeats" marks the main separator and starts new side
                state.is_victory = True
                state.found_main_separator = True
                state.start_new_side()
                state.expecting_wrestler = True

            case _:
                # Unhandled token type
                pass

    # Finalize by adding the last side
    state.finalize()

    # Build MatchDict
    pre_match_dict = {
        "date": state.date,
        "promotion_id": state.promotion_id,
        "promotion_name": state.promotion_name,
        "event_id": state.event_id,
        "event_name": state.event_name,
        "match_type": state.match_type,
        "country": state.country or "Unknown",
        "wrestlers": list(state.all_wrestlers),
        "wrestler_names": dict(state.wrestler_names),
        "sides": state.final_sides(),
        "is_victory": state.is_victory if state.is_victory is not None else False,
        "teams": state.teams,  # Team metadata separate from sides
    }

    return pre_match_dict


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

if __name__ == "__main__":
    from pprint import pprint

    match_info = parse_match(SAMPLE_THREE_WAY_TAG)
    pprint(match_info)
