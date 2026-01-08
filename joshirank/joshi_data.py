#!/usr/bin/env python
"""Datafile containing info about the Joshi scene on cagematch.net"""

joshi_promotions = {
    # Full database names (these match get_promotion_name() output)
    "ChocoPro",
    "Ice Ribbon",
    "World Wonder Ring Stardom",
    "Tokyo Joshi Pro-Wrestling",
    "SEAdLINNNG",
    "Sendai Girls' Pro Wrestling",
    "OZ Academy",
    "Marvelous That's Women Pro Wrestling",
    "World Woman Pro-Wrestling Diana",
    "Pro Wrestling WAVE",
    "Actwres girl'Z",
    "Dream Star Fighting Marigold",
    "PURE-J",
    "JTO",
    "Ladies Legend Pro Wrestling-X",
    # Additional Joshi/women-focused promotions with 100% female usage
    "Ryukyu Dragon Pro Wrestling",
    # Legacy short names (kept for compatibility but may not match database)
    "Stardom",  # matches "World Wonder Ring Stardom"
    "TJPW",  # matches "Tokyo Joshi Pro-Wrestling"
    "Sendai Girls",  # matches "Sendai Girls' Pro Wrestling"
    "Diana",  # matches "World Woman Pro-Wrestling Diana"
    "Wave",  # matches "Pro Wrestling WAVE"
    "Marigold",  # matches "Dream Star Fighting Marigold"
    "Marvelous",  # matches "Marvelous That's Women Pro Wrestling"
    "Colors",
    "Prominence",
    "Asuka Pro Wrestling",
    "Ganbare",
    "Evolution",
    "GLEAT",
    "PPP Tokyo",
    "Kishu Bundara Pro Wrestling",
    "Itabasi Pro Wrestling",
    "Hot Shushu",
    "Michinoku",
    "Best Body Japan",
    "UpTown",
    "Major Girl's Fighting AtoZ",
    "NEO Women's Pro Wrestling",
    "Japanese Women Pro-Wrestling Project",
    "JD Star Women's Pro Wrestling",
    "All Japan Women's Pro-Wrestling",
    "GAEA Japan",
    "Girl's Pro-Wrestling Unit Color's",
    "REINA",
    "OSAKA Women's Pro-Wrestling",
    "New All Japan Women's Pro Wrestling",
    "Sareee-ISM",
    "Japan Woman Pro-Wrestling",
}

international_women_promotions = {
    "SHINE Wrestling",
    "Women Of Wrestling",
    "SHIMMER Women Athletes",
    "SPARK Joshi Puroresu Of America",
    "Uprising Women Athletes",
    "Women's Superstars United",
    "Kitsune Women's Wrestling",
    "Gorgeous Ladies Of Wrestling",
    "Lucha Libre Femenil",
    "Magnificent Ladies Wrestling",
    "Pro-Wrestling: EVE",
    "Dangerous Women Of Wrestling",
    "Lucha Internacional Femenil",
    "Sukeban",
}


promotion_abbreviations = {
    "All Elite Wrestling": "AEW",
    "World Wonder Ring Stardom": "Stardom",
    "World Wrestling Entertainment": "WWE",
    "Tokyo Joshi Pro-Wrestling": "TJPW",
    "Marvelous That's Women Pro Wrestling": "Marvelous",
    "Sendai Girls' Pro Wrestling": "Sendai Girls",
    "Girl's Pro-Wrestling Unit Color's": "Colors",
    "Dream Star Fighting Marigold": "Marigold",
    "Ganbare Pro Wrestling": "Ganbare",
    "Pro Wrestling WAVE": "Wave",
    "Total Nonstop Action Wrestling": "TNA",
    "Women Of Wrestling": "WOW",
    "Yanagase Pro Wrestling": "Yanagase",
    "World Woman Pro-Wrestling Diana": "Diana",
    "National Wrestling Alliance": "NWA",
    "Consejo Mundial De Lucha Libre": "CMLL",
    "Ohio Valley Wrestling": "OVW",
    "Juggalo Championship Wrestling": "Juggalo",
    "Lucha Libre AAA Worldwide": "AAA",
    "Lucha Libre AAA World Wide": "AAA",
    "Major League Wrestling": "MLW",
    "Gokigen Pro Wrestling": "Gokigen",
    "Pro-Wrestling Evolution": "Evolution",
    "Active Advance Pro Wrestling": "2AW",
    "Hokuto Pro Wrestling": "Hokuto",
    "Michinoku Pro Wrestling": "Michinoku",
    "Pro Wrestling Up Town": "UpTown",
    "P.P.P. Tokyo": "PPP Tokyo",
    "Freelancer": "",
    "Shinsyu Girls Pro Wrestling": "Shinsyu",
    "Ladies Legend Pro Wrestling-X": "LLPW-X",
    "2Point5 Joshi Pro-Wrestling": "2Point5",
    "Best Body Japan Pro-Wrestling": "Best Body Japan",
    "World Wrestling Federation": "WWF",
    "All Japan Women's Pro-Wrestling": "AJW",
    "GAEA Japan": "GAEA",
    "Major Girl's Fighting AtoZ": "AtoZ",
    "Hyper Visual Fighting Arsion": "Arsion",
    "World Wide Wrestling Federation": "WWWF",
    "Frontier Martial-Arts Wrestling": "FMW",
    "World Championship Wrestling": "WCW",
    "Japanese Women Pro-Wrestling Project": "JWP",
    "Gatoh Move Pro Wrestling": "Gatoh Move",
}

# for example, WWE was WWF before 2002
promotion_name_changes = {
    "World Wrestling Entertainment": (2002, "World Wrestling Federation"),
    "Major Girl's Fighting AtoZ": (2003, "Hyper Visual Fighting Arsion"),
    "World Wrestling Federation": (1979, "World Wide Wrestling Federation"),
    "World Wide Wrestling Federation": (1963, "Capitol Wrestling Corporation"),
    "ChocoPro": (2024, "Gatoh Move Pro Wrestling"),
}


considered_female = {
    22620,  # abadon
    22139,  # max the impaler
    26282,  # (Kouki Amarei)
    32870,  # ren konatsu
    26191,  # sazzy boatright
    9232,  # seleziya sparx
    12132,  # veda scott
}
