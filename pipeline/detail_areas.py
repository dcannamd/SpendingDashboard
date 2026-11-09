"""Product areas: finer-grained spending lines than the eight dashboard categories.

Each area lists, per country, one or more OPTIONS. An option is a list of line
names that are added together. For each region and year the first option whose
lines are ALL present is used. That handles Statistics Canada renaming lines
over the years (the same spending appears under an old or a new label).

Names are lower-case and must match the agency's own wording (see
data/detail_lines.txt, written by `python3 -m pipeline.list_detail`).

Rules that keep the numbers honest:
  * Only one level of the hierarchy goes into an option, so lines are never
    double counted. An area may still sit inside another area ("part_of"), so
    the two are shown separately, never added together.
  * US and Canadian lines are not like-for-like even where an area exists in
    both, so the dashboard only ever compares a region with its own country.
  * An area with no line in a country simply has no data for that country.
"""

NONE = []


def A(id, label, group, us=NONE, ca=NONE, part_of=None, note=None):
    return {"id": id, "label": label, "group": group, "us": us, "ca": ca,
            "part_of": part_of, "note": note}


AREAS = [
    # ---- Recreation ---------------------------------------------------------
    A("pets", "Pets and pet care", "recreation",
      us=[["pets, pet products, and related services"]],
      ca=[["pet expenses"],
          ["pet food and pet-related goods", "purchase of pets", "veterinarian and other services"]]),
    A("sports_goods", "Sports, hobby and toy goods", "recreation",
      us=[["other sporting and recreational goods"]],
      ca=[["sports, athletic and recreational equipment and related services"]],
      note="US figure also covers toys and hobby goods."),
    A("toys", "Children's toys", "recreation", part_of="sports_goods",
      ca=[["children's toys"]]),
    A("art_craft", "Art and craft materials", "recreation", part_of="sports_goods",
      ca=[["art and craft materials"]]),
    A("bikes", "Bicycles, parts and accessories", "recreation",
      ca=[["bicycles (purchase), parts and accessories"], ["bicycles (purchase)"]]),
    A("fitness", "Gyms and sports club fees", "recreation",
      us=[["membership clubs and participant sports centers"]],
      ca=[["dues and fees for sports and recreation facilities"],
          ["dues and fees for sports and recreational activities and athletic and recreational facilities"]]),
    A("electronics", "Consumer electronics and computers", "recreation",
      us=[["video and audio equipment", "information processing equipment",
           "telephone and related communication equipment"]],
      ca=[["computer equipment and supplies", "home entertainment equipment",
           "purchase of telephones and equipment"],
          ["computer equipment and supplies", "audio equipment and home theatre systems", "televisions",
           "dvd players, blu-ray players and other video equipment and accessories",
           "purchase of telephones and equipment"]]),
    A("wearables", "Wearable electronic devices", "recreation",
      ca=[["wearable electronic devices"]]),
    A("package_trips", "Package tours and trips", "recreation",
      us=[["package tours"]], ca=[["package trips"]]),

    # ---- Furnishings and home ----------------------------------------------
    A("furniture", "Furniture and floor coverings", "furnishings",
      us=[["furniture, furnishings, and floor coverings"]],
      ca=[["furniture", "rugs, mats and underpadding"]]),
    A("appliances", "Household appliances", "furnishings",
      us=[["household appliances"]], ca=[["household appliances"]]),
    A("textiles", "Linens and household textiles", "furnishings",
      us=[["household textiles"]], ca=[["linens"]]),
    A("kitchenware", "Kitchen, dining and cooking ware", "furnishings",
      us=[["glassware, tableware, and household utensils"]],
      ca=[["non-electric kitchen and cooking equipment"]]),
    A("tools", "Home and garden tools and equipment", "furnishings",
      us=[["tools and equipment for house and garden"]],
      ca=[["home and workshop tools and equipment",
           "lawn, garden and snow-removal equipment and tools"]]),
    A("decor", "Art and decorative ware", "furnishings",
      ca=[["art, antiques and decorative ware"],
          ["works of art, carvings and other decorative ware"]]),
    A("home_security", "Home security services", "furnishings",
      ca=[["home security services"]]),
    A("cleaning", "Household cleaning supplies", "other",
      ca=[["household cleaning supplies and equipment"]]),
    A("garden", "Garden supplies and services", "other",
      ca=[["garden supplies and services"]]),
    A("child_care", "Child care", "other",
      ca=[["child care"]]),

    # ---- Clothing -----------------------------------------------------------
    A("womens_clothing", "Women's and girls' clothing", "clothing",
      us=[["women's and girls' clothing"]]),
    A("mens_clothing", "Men's and boys' clothing", "clothing",
      us=[["men's and boys' clothing"]]),
    A("kids_clothing", "Infants' and children's clothing", "clothing",
      us=[["children's and infants' clothing"]]),
    A("footwear", "Footwear", "clothing",
      us=[["footwear"]]),
    A("jewellery", "Watches and jewellery", "clothing",
      ca=[["watches and jewellery (women and girls aged 4 years and over)",
           "watches and jewellery (men and boys aged 4 years and over)"],
          ["watches and jewellery"]]),
    A("laundry", "Laundry and dry cleaning", "clothing",
      us=[["laundry and dry cleaning services"]],
      ca=[["laundry and dry-cleaning services"],
          ["laundromats, dry-cleaning and laundry services"]]),

    # ---- Personal care and health ------------------------------------------
    A("personal_care", "Personal care", "other",
      us=[["personal care"]], ca=[["personal care"]]),
    A("hair_care", "Hair care products", "other", part_of="personal_care",
      ca=[["hair care products"]]),
    A("skin_care", "Makeup, skin care and fragrance", "other", part_of="personal_care",
      ca=[["makeup, skin care, manicure and fragrance products"]]),
    A("oral_care", "Oral hygiene products", "other", part_of="personal_care",
      ca=[["oral hygiene products"]]),
    A("diapers", "Disposable diapers", "other", part_of="personal_care",
      ca=[["disposable diapers"]]),
    A("personal_items", "Personal items (bags, jewellery and similar)", "other",
      us=[["personal items"]]),
    A("medical_supplies", "Medical supplies and devices", "health",
      us=[["other medical products", "therapeutic appliances and equipment"]],
      ca=[["non-prescribed medicines, pharmaceutical products, health care supplies and equipment"]],
      note="Canada's line also includes non-prescription medicines."),
    A("home_health", "Home health care", "health",
      us=[["home health care"]]),
    A("dental", "Dental services", "health",
      us=[["dental services"]], ca=[["dental services"]]),
    A("eye_care", "Eye-care goods and services", "health",
      ca=[["eye-care goods and services"]]),

    # ---- Food ---------------------------------------------------------------
    A("restaurants", "Restaurants and takeout", "food",
      us=[["purchased meals and beverages"]], ca=[["food purchased from restaurants"]]),
    A("alcohol_stores", "Alcohol bought in stores", "other",
      us=[["alcoholic beverages purchased for off-premises consumption"]],
      ca=[["alcoholic beverages purchased from stores"]]),
    A("bakery", "Bakery products", "food", ca=[["bakery products"]]),
    A("dairy", "Dairy products and eggs", "food", ca=[["dairy products and eggs"]]),
    A("meat", "Meat", "food", ca=[["meat"]]),
    A("seafood", "Fish and seafood", "food", ca=[["fish and seafood"]]),
    A("produce", "Fruit, nuts and vegetables", "food",
      ca=[["fruit, fruit preparations and nuts", "vegetables and vegetable preparations"]]),
    A("beverages_other", "Non-alcoholic drinks and other foods", "food",
      ca=[["non-alcoholic beverages and other food products"]]),

    # ---- Transport, housing, services ---------------------------------------
    A("vehicle_parts", "Vehicle parts and accessories", "transport",
      us=[["motor vehicle parts and accessories"]],
      ca=[["tires, batteries, and other parts and supplies for vehicles",
           "accessories for automobiles, vans and trucks"]]),
    A("vehicle_repair", "Vehicle maintenance and repair", "transport",
      us=[["motor vehicle maintenance and repair"]],
      ca=[["maintenance and repairs of vehicles"]]),
    A("rent", "Rent", "housing",
      us=[["rental of tenant-occupied nonfarm housing"]], ca=[["rent"]]),
    A("electricity", "Electricity", "housing",
      us=[["electricity"]], ca=[["electricity for principal accommodation"]]),
    A("internet", "Internet access", "other",
      us=[["internet access"]], ca=[["internet access services"]]),
    A("education", "Education and tuition", "other",
      us=[["education"]], ca=[["education"]]),
    A("lessons", "Hobby courses and lessons", "other", part_of="education",
      ca=[["personal interest courses and lessons (excluding driving lessons)"]]),
]

AREA_BY_ID = {a["id"]: a for a in AREAS}
assert len(AREA_BY_ID) == len(AREAS), "duplicate area id"


def names_needed(country):
    """Every distinct line name used for a country (lower-case)."""
    key = country.lower()
    return sorted({n for a in AREAS for opt in a[key] for n in opt})
