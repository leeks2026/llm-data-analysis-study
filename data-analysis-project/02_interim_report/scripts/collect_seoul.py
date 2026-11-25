#!/usr/bin/env python3
"""Download the three annual source files from Seoul's official data portal."""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "subway"
PAGE = "https://data.seoul.go.kr/dataList/OA-12921/A/1/datasetView.do"
ENDPOINT = "https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false"
# Sequence values are visible in the source page's official download controls.
ANNUAL = {2023: "45", 2024: "44", 2025: "46"}


def download(year: int, sequence: str) -> dict:
    path = OUT / f"subway_{year}.csv"
    data = urlencode({"infId": "OA-12921", "seqNo": "", "seq": sequence, "infSeq": "1"}).encode()
    request = Request(ENDPOINT, data=data, headers={"User-Agent": "Mozilla/5.0", "Referer": PAGE})
    tmp = path.with_suffix(".csv.part")
    digest = hashlib.sha256()
    with urlopen(request, timeout=90) as response, tmp.open("wb") as target:
        status = response.status
        content_type = response.headers.get("Content-Type", "")
        for block in iter(lambda: response.read(1024 * 1024), b""):
            target.write(block)
            digest.update(block)
    size = tmp.stat().st_size
    if size < 1_000_000 or "text/html" in content_type.lower():
        raise RuntimeError(f"{year}: expected annual CSV, got {size} bytes ({content_type}); kept {tmp}")
    os.replace(tmp, path)
    result = {"year": year, "source_page": PAGE, "download_sequence": sequence,
              "retrieved_utc": datetime.now(timezone.utc).isoformat(), "http_status": status,
              "bytes": size, "sha256": digest.hexdigest(), "file": path.name}
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    records = [download(year, sequence) for year, sequence in ANNUAL.items()]
    (OUT / "provenance.json").write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
