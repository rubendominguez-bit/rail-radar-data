import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import refresh_ouigo as updater


def fixture(end="20261212"):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in {
            "stops.txt": "stop_id,stop_name,stop_lat,stop_lon\na,Madrid,40,-3\n",
            "routes.txt": "route_id,route_short_name,route_type\nr,Ouigo,2\n",
            "trips.txt": "route_id,service_id,trip_id\nr,s,t\n",
            "stop_times.txt": "trip_id,stop_id,stop_sequence,arrival_time,departure_time\nt,a,1,12:00:00,12:00:00\n",
            "calendar.txt": f"service_id,start_date,end_date\ns,20260626,{end}\n",
        }.items():
            archive.writestr(name, content)
    return output.getvalue()


class UpdaterChecks(unittest.TestCase):
    def test_select_latest_valid_static_feed(self):
        files = [
            {"id": 1, "esValido": True, "nombreTipoFichero": "GTFS", "fechaActualizacion": "2026-07-01"},
            {"id": 2, "esValido": False, "nombreTipoFichero": "GTFS", "fechaActualizacion": "2026-11-01"},
            {"id": 3, "esValido": True, "nombreTipoFichero": "GTFS-RT", "fechaActualizacion": "2026-11-01"},
            {"id": 4, "esValido": True, "nombreTipoFichero": "GTFS", "fechaActualizacion": "2026-10-01"},
        ]
        self.assertEqual(updater.select_file({"id": 1515, "ficheros": files})["id"], 4)

    def test_publication_matches_archive_and_keeps_last_success_on_failure(self):
        now = dt.datetime(2026, 11, 1, tzinfo=dt.timezone.utc)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            data = fixture()
            manifest = updater.publish(root, data, {"id": 1766, "fechaActualizacion": "2026-07-02T08:17:54Z"}, now)
            self.assertEqual(manifest["sha256"], hashlib.sha256(data).hexdigest())
            self.assertEqual((root / manifest["archive"]).read_bytes(), data)
            self.assertFalse(manifest["realtime"])
            self.assertEqual(manifest["validUntil"], "20261212")
            original = (root / "ouigo.json").read_bytes()
            for invalid in [b"<html>Maintenance</html>", fixture("20261001")]:
                with self.assertRaises(Exception):
                    updater.publish(root, invalid, {"id": 8, "fechaActualizacion": "2026-11-01T00:00:00Z"}, now)
                self.assertEqual((root / "ouigo.json").read_bytes(), original)
            self.assertNotIn("enlaceDescarga", json.loads(original))

    def test_no_credentials_to_other_hosts(self):
        with self.assertRaises(ValueError):
            updater.fetch("https://example.org/file", key="private-key")

    def test_archive_traversal_is_rejected(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("../stops.txt", "invalid")
        with self.assertRaises(ValueError):
            updater.inspect_gtfs(data.getvalue())


if __name__ == "__main__":
    unittest.main()
