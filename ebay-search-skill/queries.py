# Deal scan queries. `min`/`max` are the static fallback windows; once
# site/data/history.csv has a few days of medians per category, the scanner
# derives ADAPTIVE windows from the market (see windows.py) — these numbers are
# only the starting point. Updated 2026-08 to current-market ranges so
# categories the shortage pushed above their old windows (RTX 3090, DDR5, …)
# start accumulating history again.

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
    },
    {
        "name": "RTX 3090 Ti",
        "q": "RTX 3090 Ti",
        "min": 1000,
        "max": 1800,
        "cond": "USED",
        "category": 27386,
    },
    {
        "name": "RTX 4070 Ti Super",
        "q": "RTX 4070 Ti Super",
        "min": 600,
        "max": 850,
        "cond": "USED",
        "category": 27386,
    },
    {
        "name": "RTX 4080 Super",
        "q": "RTX 4080 Super",
        "min": 650,
        "max": 900,
        "cond": "USED",
        "category": 27386,
    },
    {
        "name": "RTX 5070 16GB",
        "q": "RTX 5070 16GB",
        "min": 800,
        "max": 1400,
        "cond": "USED",
        "category": 27386,
    },
    {
        "name": "RTX 5060",
        "q": "RTX 5060 16GB",
        "min": 400,
        "max": 750,
        "cond": "USED",
        "category": 27386,
    },
    # Budget 16-GB-class cards the local-AI crowd actually buys.
    {
        "name": "RTX 4060 Ti 16GB",
        "q": "RTX 4060 Ti 16GB",
        "min": 250,
        "max": 500,
        "cond": "USED",
        "category": 27386,
    },
    {
        "name": "Tesla P40",
        "q": "Tesla P40",
        "min": 100,
        "max": 300,
        "cond": "USED",
        "category": 27386,
    },
    {
        "name": "Tesla T4",
        "q": "Tesla T4",
        "min": 300,
        "max": 800,
        "cond": "USED",
        "category": 27386,
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
    },
    {
        "name": "Radeon PRO W7900",
        "q": "Radeon PRO W7900",
        "min": 1200,
        "max": 3500,
        "cond": "USED",
        "category": 27386,
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
    },
    {
        "name": "DDR4 RDIMM 64GB",
        "q": "DDR4 RDIMM 64GB",
        "min": 80,
        "max": 200,
        "cond": "USED",
        "category": 11210,
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
    },
    {
        "name": "DDR5 RDIMM",
        "q": "DDR5 RDIMM",
        "min": 80,
        "max": 400,
        "cond": "USED",
        "category": 11210,
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
]
