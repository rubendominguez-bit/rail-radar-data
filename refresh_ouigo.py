"""Publish the latest validated Ouigo GTFS from the NAP. NAP_API_KEY stays in the runner."""
import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

NAP = "https://nap.transportes.gob.es"
SOURCE = NAP + "/ConjuntoDato/Detail/1515"
MAX_DOWNLOAD = 20_000_000
MAX_EXPANDED = 80_000_000


def fetch(url, key=None):
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("HTTPS download required")
    if key and parsed.hostname != "nap.transportes.gob.es":
        raise ValueError("NAP credentials must only be sent to the NAP")
    headers = {"User-Agent": "RailRadar timetable updater (+https://rubendominguez.work/rail-radar)"}
    if key:
        headers["ApiKey"] = key
    # API endpoints do not redirect. Never forward the credential to a redirect target.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None
    opener = urllib.request.build_opener(NoRedirect()) if key else urllib.request.build_opener()
    try:
        with opener.open(urllib.request.Request(url, headers=headers), timeout=40) as response:
            data = response.read(MAX_DOWNLOAD + 1)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"HTTP {error.code} while retrieving timetable data") from None
    except urllib.error.URLError:
        raise RuntimeError("Timetable service unavailable") from None
    if len(data) > MAX_DOWNLOAD:
        raise ValueError("Download exceeds the allowed size")
    return data


def api(path, key):
    result = json.loads(fetch(NAP + path, key))
    if not result.get("success") or result.get("data") is None:
        raise RuntimeError("NAP did not return a valid result")
    return result["data"]


def select_file(dataset):
    if dataset.get("id") != 1515 or dataset.get("isObsolete"):
        raise ValueError("Unexpected or obsolete dataset")
    candidates = [item for item in dataset.get("ficheros", [])
                  if item.get("esValido") and "GTFS" in item.get("nombreTipoFichero", "").upper()
                  and "RT" not in item.get("nombreTipoFichero", "").upper()]
    if not candidates:
        raise ValueError("No validated Ouigo GTFS available")
    return max(candidates, key=lambda item: item.get("fechaActualizacion", ""))


def inspect_gtfs(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        if len(entries) > 200 or sum(item.file_size for item in entries) > MAX_EXPANDED:
            raise ValueError("Archive exceeds the allowed size")
        files = {}
        for item in entries:
            parts = Path(item.filename).parts
            if item.filename.startswith("/") or ".." in parts:
                raise ValueError("Unsafe archive path")
            name = Path(item.filename).name
            if name in files:
                raise ValueError("Duplicate timetable file")
            if name.endswith(".txt"):
                files[name] = archive.read(item).decode("utf-8-sig")
        if not {"stops.txt", "routes.txt", "trips.txt", "stop_times.txt"} <= files.keys():
            raise ValueError("Incomplete GTFS")
        if not ({"calendar.txt", "calendar_dates.txt"} & files.keys()):
            raise ValueError("Missing service calendars")
        stops = list(csv.DictReader(io.StringIO(files["stops.txt"])))
        trips = list(csv.DictReader(io.StringIO(files["trips.txt"])))
        if not stops or not trips:
            raise ValueError("Empty GTFS")
        dates = []
        for row in csv.DictReader(io.StringIO(files.get("calendar.txt", ""))):
            if row.get("start_date") and row.get("end_date"):
                dates += [row["start_date"], row["end_date"]]
        for row in csv.DictReader(io.StringIO(files.get("calendar_dates.txt", ""))):
            if row.get("exception_type") == "1" and row.get("date"):
                dates.append(row["date"])
        if not dates:
            raise ValueError("No published service dates")
        for date in dates:
            dt.datetime.strptime(date, "%Y%m%d")
        return min(dates), max(dates)


def publish(output, data, metadata, now=None):
    start, end = inspect_gtfs(data)
    now = now or dt.datetime.now(dt.timezone.utc)
    if end < now.strftime("%Y%m%d"):
        raise ValueError("The NAP timetable has expired; keeping the last publication")
    digest = hashlib.sha256(data).hexdigest()
    filename = f"ouigo-{digest}.zip"
    manifest = {
        "schemaVersion": 1, "operator": "ouigo", "datasetID": 1515,
        "sourceURL": SOURCE, "checkedAt": now.isoformat().replace("+00:00", "Z"),
        "updatedAt": metadata["fechaActualizacion"], "validFrom": start, "validUntil": end,
        "archive": filename, "sha256": digest, "fileID": metadata["id"],
        "attribution": "Powered by MITRAMS · Ouigo · Punto de Acceso Nacional",
        "licenseURL": NAP + "/licencia-datos", "realtime": False,
    }
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    # Content-addressed files ensure a cached manifest always refers to the matching archive.
    (output / filename).write_bytes(data)
    temporary = output / "ouigo.json.tmp"
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(output / "ouigo.json")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="docs")
    args = parser.parse_args()
    key = os.environ.get("NAP_API_KEY", "").strip()
    if not key:
        raise ValueError("Configure the NAP_API_KEY repository secret")
    item = select_file(api("/api/v2/conjunto-dato/1515", key))
    link = api(f"/api/v2/fichero/{item['id']}/descarga", key)["enlaceDescarga"]
    # The API key is deliberately absent from the archive download request.
    data = fetch(link)
    result = publish(args.output, data, item)
    print(f"Ouigo timetable verified: file {result['fileID']}, valid until {result['validUntil']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        # Do not print request objects, API response bodies, signed URLs or credentials.
        print(f"Update failed: {type(error).__name__}. Last valid publication retained.", file=sys.stderr)
        sys.exit(1)
