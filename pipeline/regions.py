"""Regions and their positions on the dashboard's tile-grid map.

A tile grid (one equal square per state/province) is used instead of real map
shapes: it needs no geometry files, and small regions stay as readable as big
ones. Mexico can be added later as a third grid.
"""

# code, name, col, row
US = [
    ("AK", "Alaska", 0, 0), ("ME", "Maine", 10, 0),
    ("VT", "Vermont", 9, 1), ("NH", "New Hampshire", 10, 1),
    ("WA", "Washington", 0, 2), ("ID", "Idaho", 1, 2), ("MT", "Montana", 2, 2),
    ("ND", "North Dakota", 3, 2), ("MN", "Minnesota", 4, 2), ("IL", "Illinois", 5, 2),
    ("WI", "Wisconsin", 6, 2), ("MI", "Michigan", 7, 2), ("NY", "New York", 8, 2),
    ("RI", "Rhode Island", 9, 2), ("MA", "Massachusetts", 10, 2),
    ("OR", "Oregon", 0, 3), ("NV", "Nevada", 1, 3), ("WY", "Wyoming", 2, 3),
    ("SD", "South Dakota", 3, 3), ("IA", "Iowa", 4, 3), ("IN", "Indiana", 5, 3),
    ("OH", "Ohio", 6, 3), ("PA", "Pennsylvania", 7, 3), ("NJ", "New Jersey", 8, 3),
    ("CT", "Connecticut", 9, 3),
    ("CA", "California", 0, 4), ("UT", "Utah", 1, 4), ("CO", "Colorado", 2, 4),
    ("NE", "Nebraska", 3, 4), ("MO", "Missouri", 4, 4), ("KY", "Kentucky", 5, 4),
    ("WV", "West Virginia", 6, 4), ("VA", "Virginia", 7, 4), ("MD", "Maryland", 8, 4),
    ("DE", "Delaware", 9, 4),
    ("AZ", "Arizona", 1, 5), ("NM", "New Mexico", 2, 5), ("KS", "Kansas", 3, 5),
    ("AR", "Arkansas", 4, 5), ("TN", "Tennessee", 5, 5), ("NC", "North Carolina", 6, 5),
    ("SC", "South Carolina", 7, 5), ("DC", "District of Columbia", 8, 5),
    ("OK", "Oklahoma", 3, 6), ("LA", "Louisiana", 4, 6), ("MS", "Mississippi", 5, 6),
    ("AL", "Alabama", 6, 6), ("GA", "Georgia", 7, 6),
    ("HI", "Hawaii", 0, 7), ("TX", "Texas", 3, 7), ("FL", "Florida", 8, 7),
]

CA = [
    ("YT", "Yukon", 0, 0), ("NT", "Northwest Territories", 1, 0),
    ("NU", "Nunavut", 2, 0), ("NL", "Newfoundland and Labrador", 7, 0),
    ("BC", "British Columbia", 0, 1), ("AB", "Alberta", 1, 1),
    ("SK", "Saskatchewan", 2, 1), ("MB", "Manitoba", 3, 1), ("ON", "Ontario", 4, 1),
    ("QC", "Quebec", 5, 1), ("NB", "New Brunswick", 6, 1),
    ("PE", "Prince Edward Island", 7, 1), ("NS", "Nova Scotia", 6, 2),
]


def all_regions():
    out = []
    for country, grid in (("US", US), ("CA", CA)):
        for code, name, col, row in grid:
            out.append({"code": f"{country}-{code}", "name": name,
                        "country": country, "col": col, "row": row})
    return out


US_NAME_TO_CODE = {name: f"US-{code}" for code, name, _, _ in US}
CA_NAME_TO_CODE = {name: f"CA-{code}" for code, name, _, _ in CA}
