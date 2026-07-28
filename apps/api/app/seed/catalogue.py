"""The demo data tables, and the deterministic generators for the bulk catalogue.

Pure data and pure functions — no session, no imports from the app. A part that
needs more demo rows of an EXISTING shape edits this file; a part that needs a new
KIND of section adds its own `app/seed/<domain>.py` instead.
"""
from __future__ import annotations

# --- reference data ------------------------------------------------------

CATEGORIES = [
    ("TIS", "Tissue & Paper Consumables", "AUR", "PRIVATE_LABEL"),
    ("GB", "Garbage Bags & Waste Management", "APX", "MASTER_DIST"),
    ("FP", "Food Packaging", "APX", "MASTER_DIST"),
    ("FSD", "Food Service Disposables", "APX", "MASTER_DIST"),
    ("CC", "Cleaning Chemicals", "APX", "CONTRACT_MFR"),
    ("CT", "Cleaning Tools", "APX", "MASTER_DIST"),
    ("WS", "Washroom Solutions", "APX", "PRIVATE_LABEL"),
    ("GLV", "Gloves & Safety Consumables", "APX", "MASTER_DIST"),
    ("GA", "Guest Amenities", "APX", "PRIVATE_LABEL"),
]

# (sku, name, spec, uom_code, sell_minor, buy_minor, category_code, brand_code)
PRODUCTS = [
    ("AUR-TIS-001", "Toilet Roll", "2 Ply Standard", "PACK", 12000, 8400, "TIS", "AUR"),
    ("AUR-TIS-002", "Toilet Roll", "3 Ply Premium", "PACK", 18000, 12600, "TIS", "AUR"),
    ("AUR-TIS-003", "Kitchen Towel", "2 Ply", "ROLL", 9000, 6300, "TIS", "AUR"),
    ("AUR-TIS-004", "M-Fold Hand Towel", "1 Ply", "PACK", 15000, 10500, "TIS", "AUR"),
    ("AUR-TIS-005", "C-Fold Hand Towel", "1 Ply", "PACK", 14000, 9800, "TIS", "AUR"),
    ("AUR-TIS-006", "Facial Tissue", "2 Ply", "PACK", 8000, 5600, "TIS", "AUR"),
    ("AUR-TIS-007", "Napkin Tissue", "1 Ply", "PACK", 6000, 4200, "TIS", "AUR"),
    ("AUR-TIS-008", "Dispenser Napkin", "1 Ply", "PACK", 7000, 4900, "TIS", "AUR"),
    ("APX-GB-001", "Black Garbage Bag 19x21", "19x21", "PACK", 5000, 3500, "GB", "APX"),
    ("APX-GB-002", "Black Garbage Bag 24x32", "24x32", "PACK", 7500, 5250, "GB", "APX"),
    ("APX-GB-003", "Black Garbage Bag 30x37", "30x37", "PACK", 10000, 7000, "GB", "APX"),
    ("APX-GB-004", "Bin Liner Small", "Small", "ROLL", 4000, 2800, "GB", "APX"),
    ("APX-GB-005", "Bin Liner Medium", "Medium", "ROLL", 5500, 3850, "GB", "APX"),
    ("APX-GB-006", "Bin Liner Large", "Large", "ROLL", 7000, 4900, "GB", "APX"),
    ("APX-GB-007", "Heavy Duty Garbage Bag 30x50", "30x50", "PACK", 14000, 9800, "GB", "APX"),
    ("APX-GB-008", "Heavy Duty Garbage Bag 36x48", "36x48", "PACK", 16000, 11200, "GB", "APX"),
    ("APX-GB-009", "Biodegradable Garbage Bag 24x32", "24x32 Bio", "PACK", 12000, 8400, "GB", "APX"),
]

# (code, name, parent_code) — the second level of the tree (R3.10). Products stay on the
# top-level categories, so a sub-category is a real "no products yet" row: deleting it is
# allowed, deleting its parent is not.
SUBCATEGORIES = [
    ("TIS1", "Toilet Rolls", "TIS"),
    ("TIS2", "Hand Towels", "TIS"),
    ("TIS3", "Napkins & Facial", "TIS"),
    ("GB1", "Bin Liners", "GB"),
    ("GB2", "Heavy Duty Sacks", "GB"),
    ("GB3", "Biodegradable", "GB"),
    ("CC1", "Floor Care", "CC"),
    ("CC2", "Washroom Chemicals", "CC"),
    ("FSD1", "Cups & Plates", "FSD"),
    ("FSD2", "Cutlery & Straws", "FSD"),
    ("GLV1", "Hand Protection", "GLV"),
    ("GA1", "Bath Amenities", "GA"),
]

# Third level under two of the above, so the tree is genuinely multi-level.
SUB_SUBCATEGORIES = [
    ("TS2A", "M-Fold", "TIS2"),
    ("TS2B", "C-Fold", "TIS2"),
    ("CC1A", "Neutral pH", "CC1"),
]

DEMO_CUSTOMERS = [
    ("CUST-0001", "Blue Fig Restaurant", "RESTAURANT", "Pune", "Maharashtra", 30000000, 30),
    ("CUST-0002", "Grand Sarovar Hotel", "HOTEL", "Mumbai", "Maharashtra", 50000000, 30),
    ("CUST-0003", "CafeMocha", "CAFE", "Pune", "Maharashtra", 20000000, 30),
]

# --- bulk catalogue + book (R2.13) ---------------------------------------
#
# Pagination and filtering are only real against hundreds of rows, so the demo
# data is generated rather than typed. Generation is deterministic — index
# arithmetic, no randomness — so a re-seed produces the same rows, `get_or_create`
# stays idempotent, and a test can name a row it expects to find. Status, stock
# and credit are deliberately uneven: an all-happy-row seed exercises no filter
# and no empty state (G14).

BULK_ITEMS: dict[str, list[str]] = {
    "TIS": ["Toilet Roll", "Kitchen Towel", "Hand Towel", "Facial Tissue", "Napkin"],
    "GB": ["Garbage Bag", "Bin Liner", "Compactor Sack", "Biohazard Bag"],
    "FP": ["Cling Film", "Aluminium Foil", "Butter Paper", "Food Container"],
    "FSD": ["Paper Cup", "Paper Plate", "Wooden Cutlery", "Straw", "Carry Bag"],
    "CC": ["Floor Cleaner", "Glass Cleaner", "Toilet Cleaner", "Degreaser", "Hand Wash"],
    "CT": ["Microfibre Cloth", "Mop Refill", "Scrub Pad", "Broom", "Squeegee"],
    "WS": ["Soap Dispenser", "Tissue Dispenser", "Air Freshener", "Urinal Screen"],
    "GLV": ["Nitrile Glove", "Latex Glove", "Face Mask", "Apron", "Shoe Cover"],
    "GA": ["Shampoo Sachet", "Bath Soap", "Dental Kit", "Shower Cap", "Sewing Kit"],
}
BULK_GRADES = ["Economy", "Standard", "Premium", "Industrial", "Eco"]
BULK_SIZES = ["Small", "Medium", "Large", "XL", "Jumbo", "Twin Pack", "Bulk Case"]
BULK_UOMS = ["PACK", "ROLL", "CASE", "PIECE"]
# Most of the catalogue is sellable; the rest exercises the status filter.
BULK_STATUSES = ["active"] * 7 + ["draft", "discontinued"]

BULK_CITIES = [
    ("Pune", "Maharashtra"), ("Mumbai", "Maharashtra"), ("Nashik", "Maharashtra"),
    ("Ahmedabad", "Gujarat"), ("Surat", "Gujarat"), ("Bengaluru", "Karnataka"),
    ("Hyderabad", "Telangana"), ("Indore", "Madhya Pradesh"),
]
BULK_CUSTOMER_WORDS = [
    "Green", "Royal", "Urban", "Coastal", "Golden", "Silver", "Spice", "Orchid",
    "Maple", "Sunrise", "Lotus", "Copper", "Velvet", "Harbour", "Summit", "Aster",
]
BULK_CUSTOMER_SUFFIX = {
    "RESTAURANT": ["Kitchen", "Diner", "Bistro", "Grill"],
    "HOTEL": ["Hotel", "Residency", "Inn", "Suites"],
    "CAFE": ["Cafe", "Coffee House", "Bakehouse"],
    "HOSPITAL": ["Hospital", "Clinic", "Care Centre"],
    "CORPORATE": ["Technologies", "Industries", "Solutions"],
    "SCHOOL": ["School", "Academy", "Campus"],
    "FACILITY_MANAGEMENT": ["Facilities", "Services", "Maintenance"],
}

def bulk_products() -> list[tuple]:
    """~300 catalogue rows: (sku, name, spec, uom, sell, buy, cat, brand, status)."""
    rows: list[tuple] = []
    for cat_code, items in BULK_ITEMS.items():
        brand = "AUR" if cat_code == "TIS" else "APX"
        for item_no, item in enumerate(items):
            for variant in range(7):
                seq = len(rows) + 1
                grade = BULK_GRADES[(item_no + variant) % len(BULK_GRADES)]
                size = BULK_SIZES[variant % len(BULK_SIZES)]
                # Integer minor units only, and a margin that never rounds (G1).
                sell = 4000 + (seq % 37) * 500 + variant * 250
                rows.append((
                    f"{brand}-{cat_code}-{100 + seq:03d}",
                    f"{grade} {item}",
                    f"{size} · {grade}",
                    BULK_UOMS[seq % len(BULK_UOMS)],
                    sell,
                    sell * 7 // 10,
                    cat_code,
                    brand,
                    BULK_STATUSES[seq % len(BULK_STATUSES)],
                ))
    return rows


def bulk_customers(start_seq: int, count: int = 250) -> list[tuple]:
    """(code, name, type, city, state, credit_limit_minor, terms, status)."""
    types = list(BULK_CUSTOMER_SUFFIX)
    rows: list[tuple] = []
    for i in range(count):
        seq = start_seq + i
        ctype = types[i % len(types)]
        suffixes = BULK_CUSTOMER_SUFFIX[ctype]
        word = BULK_CUSTOMER_WORDS[(i * 3) % len(BULK_CUSTOMER_WORDS)]
        city, state = BULK_CITIES[i % len(BULK_CITIES)]
        rows.append((
            f"CUST-{seq:04d}",
            f"{word} {suffixes[i % len(suffixes)]} {seq}",
            ctype,
            city,
            state,
            # Every 9th is a cash-only account: a zero limit is a real state, not a gap.
            0 if i % 9 == 0 else (5000000 + (i % 8) * 2500000),
            [15, 30, 45, 60][i % 4],
            "inactive" if i % 11 == 0 else "active",
        ))
    return rows

# (code, name, supplier_type, city, state, gstin)
DEMO_SUPPLIERS = [
    ("SUPP-0001", "PaperWings Sanaswadi", "MANUFACTURER", "Sanaswadi", "Maharashtra", "27AAECP1234A1Z5"),
    ("SUPP-0002", "Baroda Packaging", "DISTRIBUTOR", "Vadodara", "Gujarat", "24AABCB5678B1Z2"),
    ("SUPP-0003", "K K Sales Corporation", "DISTRIBUTOR", "Pune", "Maharashtra", "27AADFK9012C1Z9"),
]
