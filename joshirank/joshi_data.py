#!/usr/bin/env python
"""Datafile containing info about the Joshi scene on cagematch.net"""

joshi_promotions = {
    "ChocoPro",
    "Ice Ribbon",
    "Stardom",
    "TJPW",
    "SEAdLINNNG",
    "Sendai Girls",
    "OZ Academy",
    "Marvelous",
    "Diana",
    "Wave",
    #  "Pro Wrestling FREEDOMS",
    "Actwres girl'Z",
    "Colors",
    "Prominence",
    "Marigold",
    "PURE-J",
    "JTO",
    "Asuka Pro Wrestling",
    "Ganbare",
    "Evolution",
    "GLEAT",
    "PPP Tokyo",
    "Kishu Bundara Pro Wrestling",
    "Itabasi Pro Wrestling",
    "Prominence",
    "Hot Shushu",
    "Michinoku",
    "Best Body Japan",
    "UpTown",
}

known_joshi = {
    "17272",  # Willow
    "16997",  # Jungle
    "11386",  # Alex Lee
    "16871",  # Charli Evans
    "22290",  # Masha Slamovich
    "20230",  # Banny
    "21322",  # crane yu
    "2114",  # michiko
    "21687",  # pretty ota
    "13902",  # Natsu sumire
    "14276",  # rina yamashita
    "26542",  # echika
    "25256",  # maya fukuda
    "4898",  # Kazuki
    "27827",  # riara
    "27601",  # chairo
    "23863",  # MIKA
    "18417",  # Yuina
    "3788",  # Yuu Yamagata
    "5962",  # Miss Mongol
    "4913",
    "6208",
    "15711",
    "3761",
    "20459",  # the other mizuki
    "19159",  # sae
    "21496",  # rhythm
    "19810",
    "26350",
    "18216",  # marika
    "16375",
    "13375",
}

non_joshi = {
    "22354",
    "21402",
    "6337",
    "22355",
    "5474",
    "8406",
    "16374",
    "1854",
    "11317",
    "12598",
    "25241",
    "3800",
    "12878",
    "3972",
    "26755",
    "24625",
    "3265",
    "3792",
    "3887",
    "4568",
    "9849",
    "19426",
    "15750",
    "18548",
    "3760",  # gabai ji-chan
    "20176",  # shoki kitamura
    "26614",  # yuki toki
    "27616",  # munetatsu
    "26790",  # dr gore
    "17161",  # andrew tang
    "5266",  # chon shiryu
    "25474",
    "27566",
    "6198",
    "18752",
    "20364",  # akki
    "26525",
    "15907",
    "2266",
    "22696",
    "20672",
    "20147",
    "20163",
    "21144",
    "7169",
    "5473",
    "24590",
    "24577",
    "12464",
    "27526",
    "9162",
    "22588",  # andreza
    "25608",
    "25608",
    "8929",
    "8796",
    "8931",  # bison tagai
}


promotion_map = {
    "21342": "666",
    "17025": "All Elite Wrestling",  # Nyla Rose
    "23408": "DEFY Wrestling",  # vert vixen
    "17510": "FCF Wrestling",
    "17272": "All Elite Wrestling",  # Willow
    "26052": "Game Changer Wrestling",  # Sawyer
    "4629": "All Elite Wrestling",  # emi sakura
    "9462": "All Elite Wrestling",  # hikaru shida
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
}


considered_female = {
    22620,
    22139,
    26282,  # (Kouki Amarei)
    32870,  # ren konatsu
    26191,  # sazzy boatright
    9232,  # seleziya sparx
}


# name mapping for known wrestlers with inconsistent naming
