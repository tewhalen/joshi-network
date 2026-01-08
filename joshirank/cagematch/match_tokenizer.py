"""An alternative approach to parsing match HTML to extract as much info as possible.

Takes in the match HTML and walks through it to extract information about
the wrestlers involved in the match.
"""

import datetime
from dataclasses import dataclass
from typing import Literal

from bs4 import BeautifulSoup

from joshirank.cagematch.util import parse_cm_date_flexible

# basic token types


@dataclass(frozen=True)
class TextToken:
    """Plain text node (potential unlinked wrestler names, match results, etc)."""

    text: str
    type: Literal["text"] = "text"


@dataclass(frozen=True)
class SpanToken:
    """A span element (for MatchType, MatchCard, etc)."""

    attrs: dict
    text: str
    type: Literal["span"] = "span"


@dataclass(frozen=True)
class DivToken:
    """A div element (for MatchEventLine, etc)."""

    attrs: dict
    text: str
    type: Literal["div"] = "div"


@dataclass(frozen=True)
class LinkToken:
    """A generic link that isn't a wrestler or team."""

    href: str
    text: str
    type: Literal["link"] = "link"


@dataclass(frozen=True)
class TagToken:
    """Other HTML tags (img, etc)."""

    name: str
    attrs: dict
    type: Literal["tag"] = "tag"


# Union type for all raw tokens
RawToken = TextToken | SpanToken | DivToken | LinkToken | TagToken


## Classified Tokens


@dataclass(frozen=True)
class WrestlerToken:
    """A wrestler with a CageMatch profile link."""

    id: int
    name: str
    type: Literal["wrestler"] = "wrestler"


@dataclass(frozen=True)
class NamedTeamToken:
    """A tag team or stable with a CageMatch link."""

    team_id: int
    team_name: str
    team_type: Literal["tag_team", "stable"]
    type: Literal["named_team"] = "named_team"


@dataclass(frozen=True)
class PromotionToken:
    """A promotion with a CageMatch link."""

    promotion_id: int
    promotion_name: str
    type: Literal["promotion"] = "promotion"


@dataclass(frozen=True)
class EventToken:
    """An event with a CageMatch link."""

    event_id: int
    event_name: str
    type: Literal["event"] = "event"


@dataclass(frozen=True)
class SeparatorToken:
    """Match result separators and team joins."""

    separator: Literal["team_join", "versus", "victory", "side_join"]
    text: str
    type: Literal["separator"] = "separator"


@dataclass(frozen=True)
class DateToken:
    """A date in DD.MM.YYYY format."""

    date: datetime.date
    text: str
    type: Literal["date"] = "date"


@dataclass(frozen=True)
class MatchTypeToken:
    """A match type token."""

    match_type: str
    type: Literal["match_type"] = "match_type"


@dataclass(frozen=True)
class ParenthesisToken:
    """Parenthesis token for grouping (used for named team members)."""

    paren: Literal["(", ")"]
    type: Literal["parenthesis"] = "parenthesis"


@dataclass(frozen=True)
class EventDetailToken:
    """Event location details with extracted country information."""

    text: str
    country: str
    event_type: str = ""
    type: Literal["event_detail"] = "event_detail"


ClassifiedToken = (
    WrestlerToken
    | NamedTeamToken
    | SeparatorToken
    | DateToken
    | PromotionToken
    | EventToken
    | MatchTypeToken
    | ParenthesisToken
    | EventDetailToken
)

# Union type for all tokens
Token = RawToken | ClassifiedToken


def raw_tokens(match_soup: BeautifulSoup) -> list[RawToken]:
    """Tokenize match HTML into a structured list of tokens.

    Args:
        match_soup: BeautifulSoup object representing the match row
    """
    raw_tokens = []

    # iterate over the TD elements
    for td in match_soup.find_all("td"):
        # walk through the soup and add all elements and strings to raw_tokens
        for element in td.children:
            raw_tokens.extend(_process_element(element))
    return raw_tokens


def _process_element(element) -> list[RawToken]:
    """Process a BeautifulSoup element and yield tokens."""
    tokens = []

    if element.name == "span":
        attrs = {k: v for k, v in element.attrs.items()}
        tokens.append(SpanToken(attrs=attrs, text=element.get_text(strip=True)))
        for child in element.children:
            tokens.extend(_process_element(child))
    elif element.name == "div":
        attrs = {k: v for k, v in element.attrs.items()}
        tokens.append(DivToken(attrs=attrs, text=element.get_text(strip=True)))
        for child in element.children:
            tokens.extend(_process_element(child))
    elif element.name is None:
        # Text node
        text = str(element).strip()
        if text:
            tokens.append(TextToken(text=text))
    elif element.name == "a":
        attrs = {k: v for k, v in element.attrs.items()}
        href = attrs.get("href", "")
        tokens.append(LinkToken(href=href, text=element.get_text(strip=True)))
    else:
        tokens.append(TagToken(name=element.name, attrs=dict(element.attrs)))

    return tokens


def date_token(token: TextToken) -> DateToken | None:
    """If a token represents a date, return it as DateToken, else None."""
    parsed_value = parse_cm_date_flexible(token.text)
    if parsed_value is not None:
        return DateToken(date=parsed_value, text=token.text)
    else:
        return None


def wrestler_token(token: LinkToken) -> WrestlerToken | None:
    """If a token represents a wrestler link return it as WrestlerToken, else None."""
    if "id=2&nr=" in token.href:
        parts = token.href.split("id=2&nr=")
        if len(parts) > 1:
            id_part = parts[1].split("&")[0]
            wrestler_id = int(id_part)
            wrestler_name = token.text if token.text else "Unknown"
            return WrestlerToken(id=wrestler_id, name=wrestler_name)
    return None


def promotion_token(token: LinkToken) -> PromotionToken | None:
    """If a token represents a promotion link return it as PromotionToken, else None."""
    if "id=8&nr=" in token.href:
        parts = token.href.split("id=8&nr=")
        if len(parts) > 1:
            id_part = parts[1].split("&")[0]
            promotion_id = int(id_part)
            promotion_name = token.text if token.text else "Unknown"
            return PromotionToken(
                promotion_id=promotion_id, promotion_name=promotion_name
            )
    return None


def event_token(token: LinkToken) -> EventToken | None:
    """If a token represents an event link return it as EventToken, else None."""
    if "id=1&nr=" in token.href:
        parts = token.href.split("id=1&nr=")
        if len(parts) > 1:
            id_part = parts[1].split("&")[0]
            event_id = int(id_part)
            event_name = token.text if token.text else "Unknown"
            return EventToken(event_id=event_id, event_name=event_name)
    return None


def tag_team_token(token: LinkToken) -> NamedTeamToken | None:
    """If a token represents a tag team link return it as NamedTeamToken, else None."""
    if "id=28&nr=" in token.href or "id=29&nr=" in token.href:
        team_id_str = token.href.split("nr=")[1].split("&")[0]
        team_type: Literal["tag_team", "stable"] = (
            "tag_team" if "id=28&nr=" in token.href else "stable"
        )
        return NamedTeamToken(
            team_id=int(team_id_str),
            team_name=token.text if token.text else "Unknown",
            team_type=team_type,
        )
    return None


def match_type_token(token: SpanToken) -> MatchTypeToken | None:
    """If a token represents a match type return it as MatchTypeToken, else None."""
    if "MatchType" in token.attrs.get("class", []):
        return MatchTypeToken(match_type=token.text)
    return None


def specialize_link_token(token: LinkToken) -> Token:
    """Try to specialize a generic LinkToken into a more specific token type."""
    for func in [
        wrestler_token,
        promotion_token,
        event_token,
        tag_team_token,
    ]:
        specialized = func(token)
        if specialized is not None:
            return specialized
    return token


def specialize_span_token(token: SpanToken) -> Token:
    """Try to specialize a generic SpanToken into a more specific token type."""
    mt_token = match_type_token(token)
    if mt_token is not None:
        return mt_token
    return token


def specialize_text_token(token: TextToken):
    """Try to specialize a generic TextToken into a more specific token type.

    Splits text on separator boundaries to handle cases where a single text node
    contains multiple separators and names (e.g., "and Sleepy Ed and").
    """
    import re

    from joshirank.cagematch.data import country_map

    text = token.text

    # Check if this is a date first (dates shouldn't be split)
    # if any wrestler has a name like "2001" or "1999.1" this could create
    # issues
    date_token_instance = date_token(token)
    if date_token_instance is not None:
        yield date_token_instance
        return

    # Check if this is an event detail with country information
    # Pattern matches: "Event @ Location, Country" or similar
    country_match = re.search(
        r"(Event|Online Stream|TV-Show|Pay Per View|Dark Match|House Show) @ (.*)$",
        text,
    )
    if country_match:
        location_text = country_match.group(2)
        event_type = country_match.group(1)
        # Country is typically the last component after the final comma
        best_guess = location_text.split(",")[-1].strip().strip(".")
        country = country_map.get(best_guess, best_guess)
        yield EventDetailToken(text=text, country=country, event_type=event_type)
        return

    # Split on separator patterns
    # Use word boundaries for "and" and "defeats", flexible spacing for others
    # Note: vs. uses \s* not \s+ to handle cases like ") vs. " where paren was already extracted
    pattern = r"(\s*&\s*|\band\b|\s*vs\.\s*|\bdefeats?\b)"
    parts = re.split(pattern, text, flags=re.IGNORECASE)

    for part in parts:
        if not part or part.isspace():
            continue

        stripped = part.strip()
        lower = stripped.lower()

        # Identify parentheses and split them from text
        if "(" in part or ")" in part:
            # Split on parentheses but capture them
            paren_parts = re.split(r"([()])", part)
            for ppart in paren_parts:
                if not ppart or ppart.isspace():
                    continue
                if ppart == "(":
                    yield ParenthesisToken(paren="(")
                elif ppart == ")":
                    yield ParenthesisToken(paren=")")
                else:
                    # Regular text around the parentheses
                    ppart_stripped = ppart.strip()
                    if ppart_stripped:
                        yield TextToken(text=ppart_stripped)
            continue

        # Identify separator type
        if re.match(r"^&$", stripped):
            yield SeparatorToken(separator="team_join", text="&")
        elif re.match(r"^and$", lower):
            yield SeparatorToken(separator="side_join", text="and")
        elif "vs." in lower:
            yield SeparatorToken(separator="versus", text="vs.")
        elif lower in ("defeat", "defeats"):
            yield SeparatorToken(separator="victory", text=stripped)
        else:
            # Preserved text (unlinked wrestler name, match result, etc)
            if stripped:
                yield TextToken(text=stripped)


def match_tokenizer(match_soup: BeautifulSoup) -> list[Token]:
    """Tokenize match HTML and classify tokens by type.

    Returns a list of typed token dataclasses representing the match structure.
    """
    tokens = []

    for token in raw_tokens(match_soup):
        match token:
            case LinkToken():
                specialized = specialize_link_token(token)
                tokens.append(specialized)
                continue
            case SpanToken():
                specialized = specialize_span_token(token)
                tokens.append(specialized)
                continue
            case TextToken():
                for specialized in specialize_text_token(token):
                    if isinstance(specialized, Token):
                        tokens.append(specialized)
                continue
            case _:
                # Keep original token if not reclassified
                tokens.append(token)
    return tokens
