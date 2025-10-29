import re
import unicodedata
from typing import Optional

# -----------------------------
# County → code mapping
# -----------------------------
COUNTY_TO_CODE = {
    "barnstable": "BARN",
    "berkshire": "BERK",
    "bristol": "BRISTOL",
    "dukes and nantucket": "BDN",
    "franklin": "FRANK",
    "hampden": "HAMPDEN",
    "hampshire": "HAMPSHIRE",
    "middlesex": "MIDDLE",
    "norfolk": "NORFOLK",
    "plymouth": "PLY",
    "suffolk": "SUFFOLK",
    "worcester": "WOR",
    "essex": "ESSEX",
}
# -----------------------------
# Ordinal lookup table
# -----------------------------
ORDINAL_MAP = {
    "1st": 1, "first": 1,
    "2nd": 2, "second": 2,
    "3rd": 3, "third": 3,
    "4th": 4, "fourth": 4,
    "5th": 5, "fifth": 5,
    "6th": 6, "sixth": 6,
    "7th": 7, "seventh": 7,
    "8th": 8, "eighth": 8,
    "9th": 9, "ninth": 9,
    "10th": 10, "tenth": 10,
    "11th": 11, "eleventh": 11,
    "12th": 12, "twelfth": 12,
    "13th": 13, "thirteenth": 13,
    "14th": 14, "fourteenth": 14,
    "15th": 15, "fifteenth": 15,
    "16th": 16, "sixteenth": 16,
    "17th": 17, "seventeenth": 17,
    "18th": 18, "eighteenth": 18,
    "19th": 19, "nineteenth": 19,
    "20th": 20, "twentieth": 20,
    "21st": 21, "twenty-first": 21, "twenty first": 21,
    "22nd": 22, "twenty-second": 22, "twenty second": 22,
    "23rd": 23, "twenty-third": 23, "twenty third": 23,
    "24th": 24, "twenty-fourth": 24, "twenty fourth": 24,
    "25th": 25, "twenty-fifth": 25, "twenty fifth": 25,
    "26th": 26, "twenty-sixth": 26, "twenty sixth": 26,
    "27th": 27, "twenty-seventh": 27, "twenty seventh": 27,
    "28th": 28, "twenty-eighth": 28, "twenty eighth": 28,
    "29th": 29, "twenty-ninth": 29, "twenty ninth": 29,
    "30th": 30, "thirtieth": 30,
    "31st": 31, "thirty-first": 31, "thirty first": 31,
    "32nd": 32, "thirty-second": 32, "thirty second": 32,
    "33rd": 33, "thirty-third": 33, "thirty third": 33,
    "34th": 34, "thirty-fourth": 34, "thirty fourth": 34,
    "35th": 35, "thirty-fifth": 35, "thirty fifth": 35,
    "36th": 36, "thirty-sixth": 36, "thirty sixth": 36,
    "37th": 37, "thirty-seventh": 37, "thirty seventh": 37,
}


def strip_accents(s: str) -> str:
    return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c))


def normalize_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def normalize_to_centroid_key(
    branch: str, district: str, centroid_keys: dict
) -> Optional[str]:
    """
    Given branch ('House' or 'Senate'), a district name, and a dict of centroid keys:
    returns the normalized centroid key if found, else None.
    """
    if branch == "House":
        ds = strip_accents(district).lower().replace(",", " ").replace("-", " ")
        ds = normalize_spaces(ds)
        if "barnstable" in ds and "nantucket" in ds:
            return "BDN" if "BDN" in centroid_keys else None
        parts = ds.split(" ")
        if len(parts) >= 2:
            ordinal_token = parts[0]
            n = ORDINAL_MAP.get(ordinal_token)
            county = " ".join(parts[1:]).replace("district", "").strip()
            county = re.sub(r"\b(of|the)\b", "", county).strip()
            if n and county in COUNTY_TO_CODE:
                code = COUNTY_TO_CODE[county]
                key = f"{code}{n:02d}"
                if key in centroid_keys:
                    return key
        return None
    elif branch == "Senate":
        if district in centroid_keys:
            return district
        d = strip_accents(district)
        d = re.sub(r"\s+", " ", d.replace(", and", " and").replace(" ,", ",")).strip()
        candidates = {
            d,
            d.title(),
            d.replace(" and ", ", "),
            d.replace(", and", " and")
        }
        for c in candidates:
            if c in centroid_keys:
                return c
        def tokens(name: str):
            name = name.lower().replace("&", "and")
            return set(re.findall(r"[a-z]+", name)) - {"and"}
        target = tokens(district)
        for k in centroid_keys:
            if tokens(k) == target:
                return k
        return None
    else:
        raise ValueError(f"Invalid branch: {branch}")
