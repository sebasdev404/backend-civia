"""Validate the supplied real workbook and read-only API behavior; no fabricated citizens."""
import unittest
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1.citizens import router
from app.core.database import SessionLocal
from app.core.security import create_access_token
from app.models.citizen import Citizen
from app.models.user import User
from app.services.citizen_import import parse_contact_file, import_contacts, phone_key

WORKBOOK = Path(__file__).resolve().parents[2] / "contactos_whatsapp_28-09-2026.xlsx"


@unittest.skipUnless(WORKBOOK.exists(), "El archivo fuente no está disponible en este entorno")
class RealContactImportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.content = WORKBOOK.read_bytes()
        cls.parsed = parse_contact_file(cls.content, WORKBOOK.name)
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        cls.client = TestClient(app)
        with SessionLocal() as db:
            user = db.query(User).filter(User.is_active == True).first()
            if user is None:
                raise unittest.SkipTest("Se requiere un usuario existente")
            cls.headers = {"Authorization": "Bearer " + create_access_token({"sub": user.id})}

    def test_actual_workbook_rows_and_full_metadata(self):
        parsed = self.parsed
        self.assertEqual(parsed["sheet_name"], "Contactos")
        self.assertEqual(parsed["total_rows"], 300)
        self.assertEqual(len(parsed["records"]), 300)
        self.assertEqual(len(parsed["columns"]), 17)
        self.assertEqual(parsed["issues"], [])
        self.assertTrue(all(len(row["fields"]) == 17 for row in parsed["records"]))
        self.assertTrue(all(row["channel"] == "WhatsApp" for row in parsed["records"]))

    def test_actual_identifiers_and_missing_numbers(self):
        rows = self.parsed["records"]
        phones = [row["phone"] for row in rows if row["phone"]]
        usernames = [row["whatsapp_username"] for row in rows if not row["phone"]]
        self.assertEqual(len(phones), 263)
        self.assertEqual(len(set(phones)), 263)
        self.assertEqual(len(usernames), 37)
        self.assertEqual(len(set(usernames)), 37)
        self.assertTrue(all(usernames))
        self.assertTrue(all(phone.startswith("+57") for phone in phones))

    def test_preview_does_not_write(self):
        with SessionLocal() as db:
            before = db.query(Citizen).count()
            result = import_contacts(db, self.parsed, preview=True)
            self.assertEqual(db.query(Citizen).count(), before)
            self.assertEqual(result["summary"]["rejected"], 0)
            self.assertEqual(result["summary"]["duplicates"], 0)

    def test_contacts_require_signed_session(self):
        for headers in ({}, {"Authorization": "Bearer demo-token-alcalde"}):
            self.assertEqual(self.client.get("/api/v1/citizens", headers=headers).status_code, 401)
            self.assertEqual(self.client.post("/api/v1/citizens/import/preview", headers=headers,
                files={"file": (WORKBOOK.name, self.content)}).status_code, 401)

    def test_invalid_file_is_not_a_success(self):
        response = self.client.post("/api/v1/citizens/import/preview", headers=self.headers,
                                    files={"file": ("archivo.txt", b"invalid")})
        self.assertEqual(response.status_code, 422)

    def test_pagination_validation_and_source_detail(self):
        self.assertEqual(self.client.get("/api/v1/citizens?limit=0", headers=self.headers).status_code, 422)
        first = self.client.get("/api/v1/citizens?limit=50&offset=0", headers=self.headers)
        self.assertEqual(first.status_code, 200)
        data = first.json()
        self.assertLessEqual(len(data["items"]), 50)
        self.assertTrue(all("source_data" not in item for item in data["items"]))
        with SessionLocal() as db:
            imported = db.query(Citizen).filter(Citizen.handle.like("contact:%")).first()
            if not imported:
                return
            detail = self.client.get("/api/v1/citizens/" + imported.id, headers=self.headers).json()
            self.assertEqual(len(detail["source_data"]["fields"]), 17)
            comments = self.client.get("/api/v1/citizens/" + imported.id + "/comments", headers=self.headers).json()
            self.assertEqual(comments["comments"], [])
            self.assertEqual(comments["relationship_status"], "not_linked")

    def test_stored_rows_match_source_when_imported(self):
        with SessionLocal() as db:
            stored = db.query(Citizen).filter(Citizen.handle.like("contact:%")).all()
            stored = [c for c in stored if (c.source_data or {}).get("file_sha256") == self.parsed["file_sha256"]]
            if not stored:
                self.skipTest("El archivo todavía no está importado")
            self.assertEqual(len(stored), 300)
            by_row = {c.source_data["row_number"]: c for c in stored}
            for row in self.parsed["records"]:
                citizen = by_row[row["row_number"]]
                self.assertEqual(citizen.name, row["name"])
                self.assertEqual(citizen.source_data["fields"], row["fields"])
                self.assertEqual(phone_key(citizen.phone), phone_key(row["phone"]))
                self.assertEqual(citizen.user_type, "Sin clasificar")
                self.assertEqual(citizen.total_reports, 0)
                self.assertEqual(citizen.followers_count, 0)
                self.assertEqual(citizen.bot_probability, 0)
            repeat = import_contacts(db, self.parsed, preview=True)
            self.assertEqual(repeat["summary"]["unchanged"], 300)
            self.assertEqual(repeat["summary"]["new_citizens_added"], 0)


if __name__ == "__main__":
    unittest.main()
