"""
Map data for Flow B: satellite basemap tiles, place geocoding, and real feature
geometry (canals, rivers, roads, rail, admin areas) from OpenStreetMap.

Sources (all free; credited on screen and in the post):
  basemap   EOxCloudless Sentinel-2 2016 by EOX — CC BY 4.0 (commercial use OK;
            the 2018+ layers are NC-SA, and the 2017 layer has gaps over Thailand)
  places    OpenStreetMap Nominatim (1 req/s, identified User-Agent)
  features  OpenStreetMap via Overpass API (ODbL)
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

import requests

from ..config import ASSETS, WORK_DIR

UA = "ShopeePipelineStoryBot/1.0 (https://github.com/warongkorn6560/shopee-pipeline)"
TILE_LAYER = "s2cloudless_3857"
TILE_URL = "https://tiles.maps.eox.at/wmts/1.0.0/" + TILE_LAYER + "/default/g/{z}/{y}/{x}.jpg"
TILE = 256
MAX_TILE_Z = 15
BASEMAP_CREDIT = "ภาพดาวเทียม: Sentinel-2 cloudless 2016 โดย EOX (CC BY 4.0) · ข้อมูลแผนที่ © OpenStreetMap"
OVERPASS = ("https://overpass-api.de/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter")
NOMINATIM = "https://nominatim.openstreetmap.org/search"

CACHE = WORK_DIR / "geo-cache"
_nominatim_lock = threading.Lock()
_last_nominatim = [0.0]


# ---------------------------------------------------------------------------
# Web Mercator
# ---------------------------------------------------------------------------
def to_px(lon: float, lat: float, z: float) -> tuple[float, float]:
    """Global pixel coordinates at (possibly fractional) zoom z."""
    lat = max(min(lat, 85.0), -85.0)
    n = TILE * (2 ** z)
    x = (lon + 180.0) / 360.0 * n
    s = math.sin(math.radians(lat))
    y = (0.5 - math.log((1 + s) / (1 - s)) / (4 * math.pi)) * n
    return x, y


def meters_per_px(lat: float, z: float) -> float:
    return 156543.03392 * math.cos(math.radians(lat)) / (2 ** z)


def zoom_for_span(span_km: float, lat: float, width_px: int) -> float:
    """Zoom at which width_px pixels cover span_km kilometres."""
    m_per_px = span_km * 1000 / width_px
    return math.log2(156543.03392 * math.cos(math.radians(lat)) / m_per_px)


# ---------------------------------------------------------------------------
# Basemap tiles
# ---------------------------------------------------------------------------
def _tile(z: int, x: int, y: int) -> bytes | None:
    path = CACHE / "tiles" / TILE_LAYER / f"{z}/{x}/{y}.jpg"
    if path.exists():
        return path.read_bytes()
    url = TILE_URL.format(z=z, x=x, y=y)
    for attempt in range(3):
        try:
            r = requests.get(url, headers={"User-Agent": UA}, timeout=30)
            if r.ok and r.content[:3] == b"\xff\xd8\xff":  # placeholders are tiny non-JPEGs
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(r.content)
                return r.content
        except requests.RequestException:
            time.sleep(1 + attempt)
    return None


@dataclass
class Mosaic:
    image: object            # PIL.Image (RGB)
    z: int
    origin: tuple[int, int]  # global pixel of the image's top-left corner

    def px(self, lon: float, lat: float) -> tuple[float, float]:
        gx, gy = to_px(lon, lat, self.z)
        return gx - self.origin[0], gy - self.origin[1]


def build_mosaic(west: float, south: float, east: float, north: float, z: int) -> Mosaic:
    """Stitch the tiles covering a lon/lat box at zoom z into one image."""
    from io import BytesIO

    from PIL import Image, ImageEnhance

    z = max(1, min(z, MAX_TILE_Z))
    x0, y0 = to_px(west, north, z)
    x1, y1 = to_px(east, south, z)
    tx0, ty0, tx1, ty1 = int(x0 // TILE), int(y0 // TILE), int(x1 // TILE), int(y1 // TILE)
    if (tx1 - tx0 + 1) * (ty1 - ty0 + 1) > 900:
        raise ValueError(f"mosaic too large at z{z}")
    img = Image.new("RGB", ((tx1 - tx0 + 1) * TILE, (ty1 - ty0 + 1) * TILE), (18, 26, 32))
    coords = [(tx, ty) for tx in range(tx0, tx1 + 1) for ty in range(ty0, ty1 + 1)]
    with ThreadPoolExecutor(max_workers=8) as ex:
        for (tx, ty), data in zip(coords, ex.map(lambda c: _tile(z, *c), coords)):
            if data:
                try:
                    img.paste(Image.open(BytesIO(data)).convert("RGB"), ((tx - tx0) * TILE, (ty - ty0) * TILE))
                except OSError:
                    pass
    # Slightly darker and punchier so overlays and labels pop, like a night-mode globe.
    img = ImageEnhance.Contrast(ImageEnhance.Brightness(img).enhance(0.78)).enhance(1.12)
    return Mosaic(img, z, (tx0 * TILE, ty0 * TILE))


# ---------------------------------------------------------------------------
# Geocoding (Nominatim)
# ---------------------------------------------------------------------------
def _cached(kind: str, key: str, fetch):
    path = CACHE / kind / (hashlib.sha1(key.encode()).hexdigest()[:16] + ".json")
    if path.exists():
        return json.loads(path.read_text())
    value = fetch()
    if value is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False))
    return value


def geocode(name: str, bbox: tuple[float, float, float, float] | None = None) -> tuple[float, float] | None:
    """(lon, lat) of a place name, preferring results inside bbox (w, s, e, n)."""
    def fetch():
        params = {"q": name, "format": "jsonv2", "limit": 1, "accept-language": "th"}
        if bbox:
            w, s, e, n = bbox
            params.update(viewbox=f"{w},{n},{e},{s}", bounded=0)
        with _nominatim_lock:  # Nominatim policy: max 1 request per second
            wait = 1.1 - (time.time() - _last_nominatim[0])
            if wait > 0:
                time.sleep(wait)
            try:
                r = requests.get(NOMINATIM, params=params, headers={"User-Agent": UA}, timeout=30)
                _last_nominatim[0] = time.time()
                hits = r.json() if r.ok else []
            except (requests.RequestException, ValueError):
                return None
        return [float(hits[0]["lon"]), float(hits[0]["lat"])] if hits else None

    got = _cached("geocode", f"{name}|{bbox}", fetch)
    return (got[0], got[1]) if got else None


# ---------------------------------------------------------------------------
# Feature geometry (Overpass)
# ---------------------------------------------------------------------------
_KIND_FILTERS = {
    "waterway": [("way", '["waterway"]'), ("relation", '["waterway"]')],
    "road": [("way", '["highway"]')],
    "railway": [("way", '["railway"~"rail|light_rail|subway|monorail"]')],
    "admin_area": [("relation", '["boundary"="administrative"]')],
    "area": [("way", ""), ("relation", "")],
}


@dataclass
class Feature:
    name: str
    lines: list[list[tuple[float, float]]] = field(default_factory=list)   # (lon, lat)
    polygons: list[list[tuple[float, float]]] = field(default_factory=list)

    @property
    def points(self) -> list[tuple[float, float]]:
        return [p for seg in self.lines + self.polygons for p in seg]

    def bbox(self) -> tuple[float, float, float, float] | None:
        pts = self.points
        if not pts:
            return None
        lons, lats = [p[0] for p in pts], [p[1] for p in pts]
        return min(lons), min(lats), max(lons), max(lats)


def _overpass(query: str) -> dict | None:
    for url in OVERPASS:
        try:
            r = requests.post(url, data={"data": query}, headers={"User-Agent": UA}, timeout=90)
            if r.ok and r.text.lstrip().startswith("{"):
                return r.json()
        except (requests.RequestException, ValueError):
            continue
    return None


def _escape(name: str) -> str:
    return "".join("\\" + c if c in '\\".*+?()[]{}|^$' else c for c in name)


def _join_ways(ways: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """Merge way segments that share endpoints into longer polylines."""
    segs = [w[:] for w in ways if len(w) > 1]
    merged = True
    while merged:
        merged = False
        for i in range(len(segs)):
            for j in range(i + 1, len(segs)):
                a, b = segs[i], segs[j]
                if a[-1] == b[0]:
                    segs[i] = a + b[1:]
                elif a[-1] == b[-1]:
                    segs[i] = a + b[::-1][1:]
                elif a[0] == b[-1]:
                    segs[i] = b + a[1:]
                elif a[0] == b[0]:
                    segs[i] = b[::-1] + a[1:]
                else:
                    continue
                del segs[j]
                merged = True
                break
            if merged:
                break
    return segs


def fetch_feature(name: str, kind: str, bbox: tuple[float, float, float, float]) -> Feature | None:
    """Real geometry for a named feature inside bbox (w, s, e, n)."""
    w, s, e, n = bbox
    filters = _KIND_FILTERS.get(kind, _KIND_FILTERS["area"])
    name_re = _escape(name)
    parts = "".join(f'{t}{f}["name"~"{name_re}",i]({s},{w},{n},{e});'
                    f'{t}{f}["name:th"~"{name_re}",i]({s},{w},{n},{e});'
                    f'{t}{f}["name:en"~"{name_re}",i]({s},{w},{n},{e});' for t, f in filters)
    query = f"[out:json][timeout:60];({parts});out geom 40;"

    def fetch():
        data = _overpass(query)
        return data.get("elements", []) if data else None

    elements = _cached("overpass", query, fetch) or []
    feat = Feature(name)
    open_ways: list[list[tuple[float, float]]] = []
    for el in elements:
        if el.get("type") == "way" and el.get("geometry"):
            pts = [(g["lon"], g["lat"]) for g in el["geometry"]]
            closed = len(pts) > 3 and pts[0] == pts[-1]
            (feat.polygons if closed and kind in ("area", "admin_area") else open_ways).append(pts)
        elif el.get("type") == "relation":
            outer = [[(g["lon"], g["lat"]) for g in m.get("geometry", [])]
                     for m in el.get("members", []) if m.get("role") in ("outer", "") and m.get("geometry")]
            if kind in ("admin_area", "area"):
                feat.polygons.extend(p for p in _join_ways(outer) if len(p) > 3)
            else:
                open_ways.extend(outer)
    feat.lines = _join_ways(open_ways)
    return feat if feat.points else None


# ---------------------------------------------------------------------------
# Coastline clipping: OSM admin boundaries include territorial sea, so a coastal
# province or country drawn as-is spills offshore in straight lines.
# ---------------------------------------------------------------------------
_LAND = None


def _land():
    global _LAND
    if _LAND is None:
        from shapely.geometry import shape
        from shapely.prepared import prep
        geom = shape(json.loads((ASSETS / "geo" / "land_sea.geojson").read_text())["geometry"])
        _LAND = (geom, prep(geom))
    return _LAND


def clip_to_land(polygons: list[list[tuple[float, float]]]) -> list[list[tuple[float, float]]]:
    """Exterior rings of the polygons' land part; unchanged when they are mostly sea (marine
    parks) or the land data is unavailable."""
    try:
        from shapely.geometry import MultiPolygon, Polygon
        from shapely.ops import unary_union
        geom, prepared = _land()
        shapes = [Polygon(p).buffer(0) for p in polygons if len(p) > 3]
        area = unary_union(shapes)
        if area.is_empty or not prepared.intersects(area):
            return polygons
        clipped = area.intersection(geom)
        if clipped.area < 0.35 * area.area:
            return polygons
        parts = clipped.geoms if isinstance(clipped, MultiPolygon) else [clipped]
        return [list(p.exterior.coords) for p in parts
                if isinstance(p, Polygon) and p.area > 0.002 * clipped.area]
    except Exception as e:  # noqa: BLE001 — clipping is cosmetic, never fail the render
        print(f"    [geo] land clip skipped: {e}")
        return polygons
