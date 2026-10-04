# Deal scan queries — THE single source of truth for every product the
# pipeline tracks. Adding a product = adding ONE dict here; everything else
# (eBay scan, €/GB column, Facebook Marketplace deep links, the report) is
# derived from this list automatically. Do NOT hardcode products anywhere else.
#
# Fields:
#   name       display name (category label in the report + site)
#   q          eBay search keyword
#   min/max    static fallback price window in EUR; adaptive windows in
#              windows.py refine these from history once a few days exist
#   cond       condition filter (USED/NEW/REFURBISHED, "" = any)
#   category   eBay category id, or None for keyword-only scans
#   capacity_gb  OPTIONAL: unambiguous capacity for the €/GB column
#              (omit for mixed-capacity categories like "Nvidia Quadro RTX")
#   exclude    OPTIONAL: lowercase phrases that disqualify a LISTING by its
#              title (parts, accessories, broken units). Enforced locally in
#              ebay_search.apply_local_filters — the Browse API has no
#              keyword-exclusion filter, so this is the only place it can
#              happen. Terms of 5+ characters match as substrings (titles glue
#              words: "Z8G4-Netzteil"); shorter ones match whole words only, so
#              "cpu" cannot kill a complete workstation that merely lists its
#              processors. This is what lets a floor sit below the barebone
#              price when the model name doubles as a parts name.
#   barebone_floor_eur  OPTIONAL: EUR price of the cheapest barebone/parts
#              listing that shares the model name (no CPU/RAM). `min` must be
#              >= this; tests/test_queries.py enforces it, so a floor can
#              never silently start admitting barebones.
#   mp         OPTIONAL: Facebook Marketplace deep-link config for the board:
#              { "max": 1100 }                       -> all FB_MARKETPLACES countries, default city
#              { "max": 200, "city": "all" }         -> every city of the countries
#              { "max": 120, "min": 40, "countries": "DE,AT" }  -> specific countries
#              Omit `mp` entirely if you don't want Marketplace links.
#
# --- shared exclude lists -------------------------------------------------
# A workstation model name is also the name of its own spare parts (a "HP Z8
# G4" PSU, the bare CTO chassis, a lone CPU), so a price floor alone cannot
# tell a complete machine from a part. Both lists disqualify a listing by
# TITLE via ebay_search.match_exclude and are shared by the three entries
# below so they live in exactly one place.
#
# WORD list: terms that also occur INSIDE ordinary listing words, so they are
# matched as whole words. "cto" is the motivating case — "Octo" and "vector"
# contain it. NOTE: "cpu" is deliberately NOT here — word boundaries cannot
# separate a complete system that lists its processors ("2x Xeon Gold 6132 CPU")
# from a CPU-only listing, because both write "CPU" as a standalone word, so the
# term would drop the target inventory. "ohne cpu" (SUBSTRING list) catches the
# barebone listings that actually say so.
EXCLUDE_WORKSTATION_WORDS = [
    "cto",            # the bare CTO chassis is the €882–980 barebone tier
]

# SUBSTRING list: distinctive 5+ character terms that cannot appear inside an
# unrelated word, so they match even when a title glues them on ("Z8G4-Netzteil").
EXCLUDE_WORKSTATION_PARTS = [
    "defekt",         # broken / for parts
    "bastler",
    "ersatzteil",
    "netzteil",       # PSU — a Z8 G4 1700 W PSU alone asks ~€209
    "mainboard",
    "motherboard",
    "kühler",         # cooler (ASCII variant included: titles often drop the umlaut)
    "kuehler",
    "gehäuse",        # chassis
    "gehaeuse",
    "chassis",
    "barebone",
    "ohne ram",       # a barebone listing that says so instead of "chassis"
    "ohne cpu",
    "not working",
]

# What the three workstation entries below actually use. A fresh list per entry
# (never the shared objects) so no caller can mutate the module-level lists by
# touching a product's `exclude`.
EXCLUDE_WORKSTATION_ALL = EXCLUDE_WORKSTATION_WORDS + EXCLUDE_WORKSTATION_PARTS

DEFAULT_QUERIES = [
    # --- GPUs >= 16 GB VRAM (category 27386 = Grafik-/Videokarten) ---
    # Shortage market 2026-08: used 3090s ask €1000–1500; window widened to
    # catch the whole market — the adaptive window refines the buy-low target.
    {
        "name": "RTX 3090",
        "q": "RTX 3090",
        "min": 900,
        "max": 1600,
        "cond": "USED",
        "category": 27386,
        "capacity_gb": 24,
        "mp": {"max": 1100},
    },
    {
        "name": "RTX 3090 Ti",
        "q": "RTX 3090 Ti",
        "min": 1000,
        "max": 1800,
        "cond": "USED",
        "category": 27386,
        "capacity_gb": 24,
    },
    {
        "name": "RTX 4070 Ti Super",
        "q": "RTX 4070 Ti Super",
        "min": 600,
        "max": 850,
        "cond": "USED",
        "category": 27386,
        "capacity_gb": 16,
    },
    {
        "name": "RTX 4080 Super",
        "q": "RTX 4080 Super",
        "min": 650,
        "max": 900,
        "cond": "USED",
        "category": 27386,
        "capacity_gb": 16,
    },
    {
        "name": "RTX 5070 16GB",
        "q": "RTX 5070 16GB",
        "min": 800,
        "max": 1400,
        "cond": "USED",
        "category": 27386,
        "capacity_gb": 16,
        "mp": {"q": "RTX 5070", "max": 900},
    },
    {
        "name": "RTX 5060",
        "q": "RTX 5060 16GB",
        "min": 400,
        "max": 750,
        "cond": "USED",
        "category": 27386,
        "capacity_gb": 16,
    },
    # Budget 16-GB-class cards the local-AI crowd actually buys.
    {
        "name": "RTX 4060 Ti 16GB",
        "q": "RTX 4060 Ti 16GB",
        "min": 250,
        "max": 500,
        "cond": "USED",
        "category": 27386,
        "capacity_gb": 16,
    },
    {
        "name": "Tesla P40",
        "q": "Tesla P40",
        "min": 100,
        "max": 300,
        "cond": "USED",
        "category": 27386,
        "capacity_gb": 24,
    },
    {
        "name": "Tesla T4",
        "q": "Tesla T4",
        "min": 300,
        "max": 800,
        "cond": "USED",
        "category": 27386,
        "capacity_gb": 16,
    },
    # Radeon PRO (CDNA/RDNA workstation): W7800 32 GB, W7900 48 GB — the AMD
    # route to big VRAM for AI.
    {
        "name": "Radeon PRO W7800",
        "q": "Radeon PRO W7800",
        "min": 800,
        "max": 2500,
        "cond": "USED",
        "category": 27386,
        "capacity_gb": 32,
    },
    {
        "name": "Radeon PRO W7900",
        "q": "Radeon PRO W7900",
        "min": 1200,
        "max": 3500,
        "cond": "USED",
        "category": 27386,
        "capacity_gb": 48,
    },
    # Quadro RTX (Turing pro cards): RTX 5000 16GB €450–500, RTX 6000 24GB €799–840 (live 2026-08).
    # 24GB cheaper than a used 3090 — strong AI value pick.
    {
        "name": "Nvidia Quadro RTX",
        "q": "Quadro RTX",
        "min": 400,
        "max": 1000,
        "cond": "USED",
        "category": 27386,
    },
    # --- Mini PCs (category 171957 = Desktops & All-in-One-PCs) ---
    {
        "name": "EliteDesk 800 G4 Mini",
        "q": "EliteDesk 800 G4 Mini",
        "min": 80,
        "max": 180,
        "cond": "USED",
        "category": 171957,
        "mp": {"q": "EliteDesk 800 G4", "max": 200, "city": "all", "countries": "DE"},
    },
    {
        "name": "EliteDesk 800 G5 Mini",
        "q": "EliteDesk 800 G5 Mini",
        "min": 100,
        "max": 200,
        "cond": "USED",
        "category": 171957,
    },
    {
        "name": "OptiPlex 3070 Micro",
        "q": "OptiPlex 3070 Micro",
        "min": 80,
        "max": 180,
        "cond": "USED",
        "category": 171957,
    },
    {
        "name": "ThinkCentre M720q",
        "q": "ThinkCentre M720q",
        "min": 80,
        "max": 180,
        "cond": "USED",
        "category": 171957,
    },
    {
        "name": "ThinkCentre M920q",
        "q": "ThinkCentre M920q",
        "min": 100,
        "max": 200,
        "cond": "USED",
        "category": 171957,
    },
    # --- RAM (11210 = Server-Speicher RAM for RDIMM; 170083 = Arbeitsspeicher RAM) ---
    {
        "name": "DDR4 RDIMM 32GB",
        "q": "DDR4 RDIMM 32GB",
        "min": 40,
        "max": 120,
        "cond": "USED",
        "category": 11210,
        "capacity_gb": 32,
        "mp": {"max": 120, "min": 40, "countries": "DE,AT"},
    },
    {
        "name": "DDR4 RDIMM 64GB",
        "q": "DDR4 RDIMM 64GB",
        "min": 80,
        "max": 200,
        "cond": "USED",
        "category": 11210,
        "capacity_gb": 64,
    },
    # DDR5 retail is ~4.2–4.5× its July-2025 level; used 32 GB kits now sit
    # far above the old window.
    {
        "name": "DDR5 32GB",
        "q": "DDR5 32GB",
        "min": 80,
        "max": 300,
        "cond": "USED",
        "category": 170083,
        "capacity_gb": 32,
    },
    {
        "name": "DDR5 RDIMM",
        "q": "DDR5 RDIMM",
        "min": 80,
        "max": 400,
        "cond": "USED",
        "category": 11210,
        "capacity_gb": 32,
    },
    # --- NVMe storage (no reliable single category id -> keyword-only scan) ---
    # SSD prices are rising with the DRAM crisis; 2 TB is the sweet spot for
    # local model storage.
    {
        "name": "NVMe SSD 2TB",
        "q": "NVMe 2TB",
        "min": 70,
        "max": 250,
        "cond": "USED",
        "category": None,
    },
    # --- Macs with big unified memory (M-series Max/Ultra = local LLMs) ---
    {
        "name": "MacBook Pro Max",
        "q": "MacBook Pro Max",
        "min": 900,
        "max": 4500,
        "cond": "USED",
        "category": 171485,
    },
    {
        "name": "Mac Studio Ultra",
        "q": "Mac Studio Ultra",
        "min": 1000,
        "max": 3500,
        "cond": "USED",
        "category": 171957,
    },
    # --- AI hardware (new-wave products, probed live on eBay.de 2026-08) ---
    # DGX Spark: no used market yet — no condition filter so new listings are caught too.
    {
        "name": "Nvidia DGX Spark",
        "q": "DGX Spark",
        "min": 2000,
        "max": 4000,
        "cond": "",
        "category": 171957,
    },
    # Strix Halo (Ryzen AI Max 395): NEW anchor = BOSGAME M5 128GB ≈ €1581–1700
    # (EU promo €1581; US $1699). Used listings on eBay.de at €2340–4625 are mostly
    # ABOVE new — only premium brands (HP Z2/ZBook, ASUS ROG Flow Z13) justify that.
    # Window set to catch anything priced below the new anchor (real used deals).
    {
        "name": "AMD Ryzen AI Max 395 (Strix Halo)",
        "q": "Ryzen AI Max 395",
        "min": 1200,
        "max": 3000,
        "cond": "USED",
        "category": None,
    },
    # Resold BOSGAME M5 units specifically — deal only if well below the €1581 new price.
    {
        "name": "BOSGAME M5 (Strix Halo)",
        "q": "BOSGAME M5",
        "min": 800,
        "max": 2000,
        "cond": "USED",
        "category": 171957,
    },
    # --- Whole gaming PCs (value flips: the GPU alone is worth most of the price) ---
    {
        "name": "Gaming PC mit RTX 3090",
        "q": "Gaming PC RTX 3090",
        "min": 1200,
        "max": 2600,
        "cond": "USED",
        "category": 171957,
    },
    {
        "name": "Gaming PC mit RTX 3080",
        "q": "Gaming PC RTX 3080",
        "min": 600,
        "max": 1100,
        "cond": "USED",
        "category": 171957,
    },
    # --- Build parts for the 2x RTX 3090 AI tower (X99 platform) ---
    {
        "name": "X99 Mainboard",
        "q": "X99 Mainboard",
        "min": 30,
        "max": 120,
        "cond": "USED",
        "category": 1244,
    },
    {
        "name": "Xeon E5-2690v4",
        "q": "Xeon E5-2690v4",
        "min": 10,
        "max": 50,
        "cond": "USED",
        "category": 164,
    },
    {
        "name": "Asus DGX Spark",
        "q": "ASUS Ascent GX10 (DGX Spark)",
        "min": 1000,
        "max": 3000,
        "cond": "USED",
        "category": 164,
    },
    {
        "name": "Dell DGX Spark",
        "q": "Dell Pro Max GB10 (DGX Spark)",
        "min": 1000,
        "max": 3000,
        "cond": "USED",
        "category": 164,
    },
    # --- Dual-socket tower workstations (Xeon Scalable, 8-channel RDIMM) ---
    # The same class as the HP Z8 G4: a full tower with 2 CPU sockets, 24 DDR4
    # slots and 2-4 double-width GPU bays — i.e. an off-the-shelf 2×3090 AI
    # host (see build_plan_2x3090.md) that is also very resellable. One entry
    # per brand's flagship tower; the single-socket siblings (Dell 7820,
    # Lenovo P720) are a class below and deliberately not tracked.
    #
    # The windows are set from dealer anchors, NOT from a live eBay scan, and
    # are deliberately WIDE (they must not hide the market — that is the whole
    # point of windows.py). The floors sit above the barebone/parts tier that
    # shares each model name — the `exclude` lists throw those listings out by
    # title, and `barebone_floor_eur` (CTO chassis without CPU/RAM: €882 Z8 G4,
    # €882 P920, €980 Precision 7920) is the price the floor must not go below.
    # The ceilings sit just above the most expensive single German listing
    # seen, so RAM-loaded flagships still match and only pallets, multi-unit
    # lots and mispriced listings are rejected.
    # Asking-price band on all three (Gekko, refurbed, Harlander, Oct 2026):
    # 16 GB entry ~€1.1–1.5k · the 2×Xeon/128 GB/RTX 4000-typical box
    # ~€2.2–2.7k · 768 GB–1.5 TB ~€7.1–13.0k. RAM is the dominant driver
    # (refurbed charges +€3,310 for 512 GB; ≈8.6 €/GB), which is why one
    # window cannot separate an entry deal from a RAM-loaded one.
    # KNOWN GAP: these are asking prices from refurb dealers, and eBay.de is
    # bot-blocked here, so the eBay floor may sit lower. Verify live — and
    # consider splitting each model into an entry (64–128 GB) and a RAM-loaded
    # (512 GB+) query if the single window mixes tiers once history exists.
    {
        "name": "HP Z8 G4 Workstation",
        # "Workstation" is not required: "HP Z8 G4" is already specific, and a
        # mandatory suffix would hide complete systems that omit the word.
        "q": "HP Z8 G4",
        "min": 1000,
        "max": 13500,
        "cond": "USED",
        "category": 171957,
        "barebone_floor_eur": 882,
        "exclude": list(EXCLUDE_WORKSTATION_ALL),
    },
    {
        "name": "Dell Precision 7920 Tower",
        # Bare "Precision 7920" also matches the 7920 Rack — hence the excludes.
        "q": "Precision 7920",
        "min": 1100,
        "max": 14000,
        "cond": "USED",
        "category": 171957,
        "barebone_floor_eur": 980,
        "exclude": list(EXCLUDE_WORKSTATION_ALL) + ["rack"],
    },
    {
        "name": "Lenovo ThinkStation P920",
        "q": "ThinkStation P920",
        "min": 950,
        "max": 11000,
        "cond": "USED",
        "category": 171957,
        "barebone_floor_eur": 882,
        "exclude": list(EXCLUDE_WORKSTATION_ALL),
    },
]


# --- derived views (consumers import these; never hardcode products elsewhere) ---

def capacity_map():
    """{query name: capacity_gb} for categories with an unambiguous capacity.

    Feeds the €/GB column in the report and the site. Categories without a
    `capacity_gb` field (mixed capacities, e.g. Quadro RTX) are left out.
    """
    return {q["name"]: q["capacity_gb"] for q in DEFAULT_QUERIES if q.get("capacity_gb")}


def marketplace_products():
    """[(query_name, keyword, mp_config), ...] for every product with an `mp`
    block — the Facebook Marketplace board's search entry points are generated
    from this, so adding `mp` to a product automatically adds its deep links.
    """
    return [
        (q["name"], mp.get("q") or q["name"], mp)
        for q in DEFAULT_QUERIES
        if (mp := q.get("mp"))
    ]
