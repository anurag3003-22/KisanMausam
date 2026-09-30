"""
Build the Panchayat directory used by KisanMausam.

Sources (both CC0 1.0 - please keep the attribution in DATA_SOURCES.md):
  1. LGD-mapped Gram Panchayat boundaries (LGD / Bharatmaps), packaged by
     ramSeraph/indian_admin_boundaries  ->  LGD_panchayats.parquet
     Covers 25 states/UTs with genuine LGD Gram Panchayat codes.
  2. Bhuvan Panchayat boundaries (NRSC/ISRO), same packager  ->  bhuvan_panchayats.parquet
     Used ONLY for the states the LGD layer lacks (HP, J&K, Sikkim, Meghalaya,
     Mizoram, Manipur, Nagaland, Arunachal). Its codes are Bhuvan codes, not LGD
     codes, so they are stored as "B<code>" and flagged in the manifest.

Nothing is invented: a Panchayat appears only if the source gives it a name.
Boundary polygons without a name/code in the source are counted and skipped.

Usage:
  pip install pyarrow shapely numpy
  python scripts/build_data.py                 # downloads the two files (~1.3 GB) into scripts/.cache
  python scripts/build_data.py --lgd a.parquet --bhuvan b.parquet
  python scripts/build_data.py --csv my.csv    # optional CSV mode (see CSV_COLUMNS)

Output: public/data/manifest.json and public/data/states/<slug>.json
"""
import argparse, csv, json, math, re, sys, time, urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "public" / "data"
CACHE = Path(__file__).resolve().parent / ".cache"
BASE = "https://github.com/ramSeraph/indian_admin_boundaries/releases/download/panchayats/"
LGD_URL = BASE + "LGD_panchayats.parquet"
BHUVAN_URL = BASE + "bhuvan_panchayats.parquet"

CSV_COLUMNS = "state,district,block,panchayat,code,lat,lng  (optional: area_km2)"

STATE_FIX = {
    "ANDAMAN & NICOBAR": "Andaman & Nicobar Islands",
    "DADRA,NAGAR HAVELI,DAMAN & DIU": "Dadra & Nagar Haveli and Daman & Diu",
    "DELHI": "Delhi",
    "Orissa": "Odisha", "ODISHA": "Odisha",
    "Union Territory of Jammu and Kashmir": "Jammu & Kashmir",
    "Jammu And Kashmir": "Jammu & Kashmir",
}
BHUVAN_ONLY_STATES = ["Himachal Pradesh", "Union Territory of Jammu and Kashmir", "Sikkim",
                      "Meghalaya", "Mizoram", "Manipur", "Nagaland", "Arunachal Pradesh"]

ROMAN = re.compile(r"^\(?(?:I{1,3}|IV|V|VI{0,3}|IX|X)\)?$", re.I)


def nice(s):
    """Tidy source spellings: 'KASBA (II)' -> 'Kasba (II)'; keep already-mixed-case text."""
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    if not s or not (s.isupper() or s.islower()):
        return s
    words = []
    for w in s.split(" "):
        if ROMAN.match(w) and len(w) <= 5:
            words.append(w.upper())
            continue
        words.append("-".join(p[:1].upper() + p[1:].lower() for p in w.split("-")))
    return " ".join(words)


def state_name(raw):
    raw = str(raw).strip()
    return STATE_FIX.get(raw) or nice(raw)


def slugify(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def download(url, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 1_000_000:
        return dest
    print(f"Downloading {url}\n  -> {dest} (large file, please wait)")
    urllib.request.urlretrieve(url, dest)
    return dest


def km2(area_deg2, lat):
    # small-area equirectangular approximation, good to <1% for Panchayat sizes
    return area_deg2 * (111.195 ** 2) * math.cos(math.radians(lat))


def read_parquet(path, code_col, name_col, st_col, dt_col, bl_col, only_states=None, prefix=""):
    """Return {code: dict} using one representative point per Panchayat."""
    import numpy as np
    import pyarrow.parquet as pq
    import shapely

    pf = pq.ParquetFile(path)
    cols = [code_col, name_col, st_col, dt_col, bl_col, "geometry"]
    best = {}
    skipped_unnamed = 0
    seen_rows = 0
    for batch in pf.iter_batches(batch_size=20000, columns=cols):
        d = batch.to_pydict()
        geoms = shapely.from_wkb(np.array(d["geometry"], dtype=object))
        areas = shapely.area(geoms)
        pts = shapely.point_on_surface(geoms)
        xs, ys = shapely.get_x(pts), shapely.get_y(pts)
        for i in range(len(areas)):
            seen_rows += 1
            code = str(d[code_col][i] or "").strip()
            name = str(d[name_col][i] or "").strip()
            st = str(d[st_col][i] or "").strip()
            if only_states is not None and st not in only_states:
                continue
            if not code or not name or name.upper() == "NA" or math.isnan(xs[i]):
                skipped_unnamed += 1
                continue
            key = prefix + code
            a = float(areas[i])
            rec = best.get(key)
            if rec is None:
                best[key] = {"code": key, "name": name, "state": st, "district": str(d[dt_col][i] or "").strip(),
                             "block": str(d[bl_col][i] or "").strip(), "lat": float(ys[i]), "lng": float(xs[i]),
                             "big": a, "area_deg2": a}
            else:
                rec["area_deg2"] += a
                if a > rec["big"]:
                    rec["big"], rec["lat"], rec["lng"] = a, float(ys[i]), float(xs[i])
    print(f"  {path.name}: {seen_rows} polygon rows, {len(best)} named Panchayats kept, {skipped_unnamed} rows without a usable name/code skipped")
    return list(best.values()), skipped_unnamed


def median(v):
    v = sorted(v)
    n = len(v)
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def write_states(records, sources):
    """records: list of dicts with state,district,block,name,code,lat,lng,area_km2,src"""
    (OUT / "states").mkdir(parents=True, exist_ok=True)
    for old in (OUT / "states").glob("*.json"):
        old.unlink()
    by_state = defaultdict(list)
    for r in records:
        by_state[r["state"]].append(r)
    manifest_states = []
    for st in sorted(by_state):
        rows = by_state[st]
        tree = defaultdict(lambda: defaultdict(list))
        for r in rows:
            tree[r["district"] or "Unknown district"][r["block"] or "Unknown block"].append(r)
        districts, n_blocks = [], 0
        lats, lngs = [], []
        for dn in sorted(tree):
            blocks = []
            for bn in sorted(tree[dn]):
                gps = sorted(tree[dn][bn], key=lambda x: x["name"].lower())
                blocks.append({
                    "n": bn,
                    "lat": round(median([g["lat"] for g in gps]), 4),
                    "lng": round(median([g["lng"] for g in gps]), 4),
                    # [name, code, lat, lng, area_km2]
                    "g": [[g["name"], g["code"], round(g["lat"], 4), round(g["lng"], 4), round(g["area_km2"], 1)] for g in gps],
                })
                lats += [g["lat"] for g in gps]
                lngs += [g["lng"] for g in gps]
            n_blocks += len(blocks)
            districts.append({"n": dn, "b": blocks})
        src = rows[0]["src"]
        slug = slugify(st)
        payload = {"state": st, "slug": slug, "source": src, "count": len(rows), "d": districts}
        text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        (OUT / "states" / f"{slug}.json").write_text(text, encoding="utf-8")
        manifest_states.append({
            "slug": slug, "name": st, "count": len(rows), "districts": len(districts), "blocks": n_blocks,
            "source": src, "code_system": "LGD" if src == "lgd" else "Bhuvan",
            "bbox": [round(min(lngs), 3), round(min(lats), 3), round(max(lngs), 3), round(max(lats), 3)],
            "bytes": len(text.encode("utf-8")),
        })
        print(f"  {st:42s} {len(rows):6d} Panchayats  {len(districts):4d} districts  {n_blocks:5d} blocks  {len(text)/1e6:5.2f} MB")
    manifest = {
        "generated": time.strftime("%Y-%m-%d"),
        "total_panchayats": sum(s["count"] for s in manifest_states),
        "states": manifest_states,
        "sources": sources,
        "note": "Panchayat locations are representative points inside each boundary; area_km2 is approximate.",
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"TOTAL {manifest['total_panchayats']} Panchayats in {len(manifest_states)} states/UTs")


def from_parquet(a):
    lgd = Path(a.lgd) if a.lgd else download(LGD_URL, CACHE / "LGD_panchayats.parquet")
    bhu = Path(a.bhuvan) if a.bhuvan else download(BHUVAN_URL, CACHE / "bhuvan_panchayats.parquet")
    print("Reading LGD layer ...")
    lg, lg_skipped = read_parquet(lgd, "gpcode", "gpname", "stname", "dtname", "blkname")
    print("Reading Bhuvan layer (only states missing from LGD) ...")
    bh, _ = read_parquet(bhu, "gp_code", "gp_name", "s_name", "d_name", "b_name", only_states=set(BHUVAN_ONLY_STATES), prefix="B")
    recs, seen = [], set()
    for r in lg:
        recs.append(dict(state=state_name(r["state"]), district=nice(r["district"]), block=nice(r["block"]),
                         name=nice(r["name"]), code=r["code"], lat=r["lat"], lng=r["lng"],
                         area_km2=km2(r["area_deg2"], r["lat"]), src="lgd"))
    lgd_states = {x["state"] for x in recs}
    for r in bh:
        st = state_name(r["state"])
        if st in lgd_states:
            continue
        k = (st, r["district"].lower(), r["block"].lower(), r["name"].lower())
        if k in seen:
            continue
        seen.add(k)
        recs.append(dict(state=st, district=nice(r["district"]), block=nice(r["block"]), name=nice(r["name"]),
                         code=r["code"], lat=r["lat"], lng=r["lng"], area_km2=km2(r["area_deg2"], r["lat"]), src="bhuvan"))
    sources = [
        {"id": "lgd", "name": "LGD-mapped Gram Panchayat boundaries (LGD / Bharatmaps), packaged by ramSeraph/indian_admin_boundaries",
         "license": "CC0 1.0 (attribute DataMeet and the original government source)",
         "note": f"{lg_skipped} boundary polygons had no LGD name/code in the source and were skipped."},
        {"id": "bhuvan", "name": "Bhuvan Panchayat (NRSC/ISRO, SIS-DP), packaged by ramSeraph/indian_admin_boundaries",
         "license": "CC0 1.0 (attribute DataMeet and the original government source)",
         "note": "Used only for states absent from the LGD layer; codes are Bhuvan codes prefixed with B."},
    ]
    write_states(recs, sources)


def from_csv(path):
    recs = []
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            try:
                lat, lng = float(r["lat"]), float(r["lng"])
            except (KeyError, ValueError):
                continue
            recs.append(dict(state=state_name(r["state"]), district=nice(r["district"]), block=nice(r["block"]),
                             name=nice(r["panchayat"]), code=str(r["code"]).strip(), lat=lat, lng=lng,
                             area_km2=float(r.get("area_km2") or 0), src="csv"))
    write_states(recs, [{"id": "csv", "name": f"User CSV {Path(path).name}", "license": "as provided", "note": ""}])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lgd"); ap.add_argument("--bhuvan"); ap.add_argument("--csv", help=CSV_COLUMNS)
    args = ap.parse_args()
    from_csv(args.csv) if args.csv else from_parquet(args)
