from __future__ import annotations

import tempfile
import zipfile
import json
from os.path import exists
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
import shutil
from pathlib import Path
from typing import Optional

import geopandas as gpd

from src.models import Chamber
from src.normalizer import normalize_to_centroid_key

SENATE_URL: str = (
    "https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles"
    "/state/SENATE2021.zip"
)
HOUSE_URL: str = (
    "https://s3.us-east-1.amazonaws.com/download.massgis.digital.mass.gov/shapefiles"
    "/state/HOUSE2021.zip"
)
SENATE_SHAPEFILE: str = "SENATE2021_POLY.shp"
HOUSE_SHAPEFILE: str = "HOUSE2021_POLY.shp"
EPSG_STATE: int = 26_986
EPSG_WGS84: int = 4_326
CENTROIDS_PATH: Path = Path("data/district_centroids.json")


def build_or_load_centroids() -> dict:
    if CENTROIDS_PATH.exists():
        print("[info] district_centroids.json found — loading.")
        return json.loads(CENTROIDS_PATH.read_text())
    out = ensure_leg_district_shapefiles(SENATE_URL, HOUSE_URL, dest_dir="data/shapefiles")
    centroids = load_and_centroid(out)
    return centroids


CENTROIDS = build_or_load_centroids()


def _download(url: str, dest_zip: Path) -> tuple[bool, Optional[str]]:
    dest_zip.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = Request(url, headers={"User-Agent": "stipend-tracker/0.1"})
        with urlopen(req, timeout=60) as r, open(dest_zip, "wb") as f:
            shutil.copyfileobj(r, f)
        return True, None
    except HTTPError as e:
        return False, f"HTTP {e.code} for {url}"
    except URLError as e:
        return False, f"Network error {e.reason} for {url}"
    except Exception as e:
        return False, f"Error downloading {url}: {e}"


def _extract(zip_path: Path, extract_to: Path):
    extract_to.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(extract_to)


def _find_poly_shp(
    root: Path, preferred_name: str, fallback_glob: str
) -> Optional[Path]:
    exact = list(root.rglob(preferred_name))
    if exact:
        return exact[0]
    matches = list(root.rglob(fallback_glob))
    if matches:
        matches.sort(key=lambda p: (len(str(p)), str(p).lower()))
        return matches[0]
    return None


def ensure_leg_district_shapefiles(
    senate_zip_url: str,
    house_zip_url: str,
    dest_dir: str = "data/shapefiles",
) -> dict[Chamber, Path]:
    """
    Ensures SENATE2021_POLY.shp and HOUSE2021_POLY.shp exist in dest_dir.
    If present, skips work. Otherwise downloads ZIPs, extracts, and copies
    the POLY shapefiles to standardized filenames in dest_dir.

    Returns: dict with keys 'senate' and 'house' -> Path or None
    """
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    senate_target = dest / SENATE_SHAPEFILE
    house_target  = dest / HOUSE_SHAPEFILE
    results = {Chamber.senate: None, Chamber.house: None}
    if senate_target.exists() and house_target.exists():
        results[Chamber.senate] = senate_target
        results[Chamber.house] = house_target
        print("[info] Shapefiles already present, skipping download/extract.")
        return results
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        if not senate_target.exists():
            senate_zip = tmp / "senate.zip"
            ok, err = _download(senate_zip_url, senate_zip)
            if ok:
                _extract(senate_zip, tmp / "senate")
                sen_src = _find_poly_shp(
                    tmp / "senate",
                    preferred_name="SENATE2021_POLY.shp",
                    fallback_glob="*SENATE*POLY.shp",
                )
                if sen_src and sen_src.exists():
                    _ = sen_src.stem.replace("SENATE2021_POLY", "")
                    for ext in ("shp", "shx", "dbf", "prj", "cpg", "qpj"):
                        candidate = sen_src.with_suffix(f".{ext}")
                        if candidate.exists():
                            shutil.copy2(candidate, dest / f"SENATE2021_POLY.{ext}")
                    results["senate"] = senate_target
                    print(f"[ok] Senate shapefile → {senate_target}")
                else:
                    print(
                        "[warn] Could not find SENATE*POLY.shp in Senate ZIP contents."
                    )
            else:
                print(f"[warn] Senate download failed: {err}")
        else:
            results["senate"] = senate_target
            print(f"[info] Senate shapefile already present → {senate_target}")
        if not house_target.exists():
            house_zip = tmp / "house.zip"
            ok, err = _download(house_zip_url, house_zip)
            if ok:
                _extract(house_zip, tmp / "house")
                hou_src = _find_poly_shp(
                    tmp / "house",
                    preferred_name=HOUSE_SHAPEFILE,
                    fallback_glob="*HOUSE*POLY.shp",
                )
                if hou_src and hou_src.exists():
                    for ext in ("shp", "shx", "dbf", "prj", "cpg", "qpj"):
                        candidate = hou_src.with_suffix(f".{ext}")
                        if candidate.exists():
                            shutil.copy2(candidate, dest / f"HOUSE2021_POLY.{ext}")
                    results["house"] = house_target
                    print(f"[ok] House shapefile → {house_target}")
                else:
                    print(
                        "[warn] Could not find HOUSE*POLY.shp in House ZIP contents."
                    )
            else:
                print(f"[warn] House download failed: {err}")
        else:
            results["house"] = house_target
            print(f"[info] House shapefile already present → {house_target}")
    return results


def _process(path: Path, chamber_label: str) -> dict:
    if not path or not path.exists():
        print(f"[warn] {chamber_label} shapefile missing or invalid path.")
        return {}
    gdf = gpd.read_file(path)
    CANDIDATES = [
        "DIST_NAME", "DISTRICT", "NAME", "NAMELSAD",
        "SEN_DIST", "SEN_NAME", "HSE_DIST", "HSE_NAME",
        "DIST_CODE", "SEN_CODE", "HSE_CODE"
    ]
    name_col = next((c for c in CANDIDATES if c in gdf.columns), None)
    if not name_col:
        raise ValueError(
            f"No district name/code column found in {path.name}. "
            f"Columns: {list(gdf.columns)}"
        )
    gdf = gdf[[name_col, "geometry"]].rename(
        columns={name_col: "district"}
    ).to_crs(EPSG_STATE)
    pts = gdf.geometry.representative_point()
    gdf = gpd.GeoDataFrame(
        {"district": gdf["district"], "geometry": pts}, crs=EPSG_STATE
    ).to_crs(EPSG_WGS84)
    mapping = {}
    for d, geom in zip(gdf["district"], gdf.geometry):
        lat, lon = round(geom.y, 6), round(geom.x, 6)
        mapping[str(d).strip()] = [lat, lon]
    return {chamber_label: mapping}


def load_and_centroid(out: dict[Chamber, Path]) -> dict:
    """
    Given the shapefile paths dict from ensure_leg_district_shapefiles(),
    compute centroid (lat, lon) for each district and return a dict ready for JSON.
    """
    if exists("data/district_centroids.json"):
        print("[info] district_centroids.json already exists, loading from file.")
        return json.loads(Path("data/district_centroids.json").read_text())
    house_map = _process(out.get(Chamber.house), Chamber.house.capitalize())
    senate_map = _process(out.get(Chamber.senate), Chamber.senate.capitalize())
    centroids = {
        "House": house_map.get("House", {}),
        "Senate": senate_map.get("Senate", {})\
    }
    print(
        f"[ok] Computed {len(centroids['House'])} House "
        f"+ {len(centroids['Senate'])} Senate centroids"
    )
    Path(
        "data/district_centroids.json"
    ).write_text(json.dumps(centroids, indent=2))
    return centroids


def centroid_for(member_record: dict) -> Optional[tuple[float, float]]:
    branch = (member_record.get("branch") or "").strip()
    district = (member_record.get("district") or "").strip()
    if not branch or not district:
        return None
    chamber_key: str = (
        "House"
        if branch.lower().startswith("house")
        else "Senate"
        if branch.lower().startswith("senate")
        else branch
    )
    chamber_map: dict = CENTROIDS.get(chamber_key, {})
    ll = chamber_map.get(district)
    if ll:
        return float(ll[0]), float(ll[1])
    key = normalize_to_centroid_key(chamber_key, district, chamber_map)
    if key:
        ll = chamber_map.get(key)
        if ll:
            return float(ll[0]), float(ll[1])
    district_norm = (
        district.replace("–", "-").replace("—", "-")
        .replace(" and ", " & ").strip()
    )
    ll = chamber_map.get(district_norm)
    if ll:
        return float(ll[0]), float(ll[1])
    return None
