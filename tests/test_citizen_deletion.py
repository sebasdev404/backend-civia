"""Exercise deletion on real records inside savepoints; always roll back every change."""
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.v1.citizens import router
from app.core.database import engine, get_db
from app.core.security import create_access_token
from app.models.citizen import Citizen
from app.models.case import Case
from app.models.meta_post import MetaPost
from app.models.user import User


class CitizenDeletionTests(unittest.TestCase):
    def setUp(self):
        self.connection = engine.connect()
        self.transaction = self.connection.begin()
        self.db = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        app = FastAPI()
        app.include_router(router, prefix="/api/v1")
        app.dependency_overrides[get_db] = lambda: self.db
        self.client = TestClient(app)
        self.ids = [row[0] for row in self.db.query(Citizen.id).order_by(Citizen.id).limit(3)]
        self.before = self.db.query(Citizen).count()
        self.admin = self.db.query(User).filter(User.role == "ADMIN", User.is_active.is_(True)).first()
        if len(self.ids) < 3 or not self.admin:
            self.tearDown()
            self.skipTest("Se requieren ciudadanos reales y un administrador existente")
        self.headers = self.authorization(self.admin)

    def tearDown(self):
        self.client.close()
        self.db.close()
        if self.transaction.is_active:
            self.transaction.rollback()
        self.connection.close()

    @staticmethod
    def authorization(user):
        return {"Authorization": "Bearer " + create_access_token({"sub": user.id})}

    def bulk(self, ids, headers=None):
        return self.client.post("/api/v1/citizens/bulk-delete", json={"citizen_ids": ids}, headers=self.headers if headers is None else headers)

    def test_single_deletion_is_exact_and_preserves_cases_and_posts(self):
        cases = self.db.query(Case).count()
        posts = self.db.query(MetaPost).count()
        response = self.client.delete("/api/v1/citizens/" + self.ids[0], headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted_ids"], [self.ids[0]])
        self.assertEqual(response.json()["deleted_count"], 1)
        self.assertIsNone(self.db.get(Citizen, self.ids[0]))
        self.assertEqual(self.db.query(Citizen).count(), self.before - 1)
        self.assertIsNotNone(self.db.get(Citizen, self.ids[1]))
        self.assertEqual(self.db.query(Case).count(), cases)
        self.assertEqual(self.db.query(MetaPost).count(), posts)

    def test_bulk_deletion_deduplicates_ids_and_updates_metrics(self):
        response = self.bulk([self.ids[0], self.ids[1], self.ids[0]])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["deleted_count"], 2)
        self.assertEqual(set(response.json()["deleted_ids"]), set(self.ids[:2]))
        self.assertIsNotNone(self.db.get(Citizen, self.ids[2]))
        metrics = self.client.get("/api/v1/citizens", headers=self.headers).json()["metrics"]
        self.assertEqual(metrics["total_registered"], self.before - 2)

    def test_stale_selection_deletes_nothing(self):
        response = self.bulk([self.ids[0], "no-existing-citizen"])
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.db.query(Citizen).count(), self.before)
        self.assertIsNotNone(self.db.get(Citizen, self.ids[0]))

    def test_missing_single_citizen_does_not_delete_another(self):
        response = self.client.delete("/api/v1/citizens/no-existing-citizen", headers=self.headers)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(self.db.query(Citizen).count(), self.before)

    def test_repeat_request_is_honest(self):
        self.assertEqual(self.bulk(self.ids[:2]).status_code, 200)
        self.assertEqual(self.bulk(self.ids[:2]).status_code, 409)
        self.assertEqual(self.db.query(Citizen).count(), self.before - 2)

    def test_empty_unbounded_and_invalid_requests_are_rejected(self):
        for ids in ([], [""], [" "], ["x" * 51], [self.ids[0]] * 501):
            self.assertEqual(self.bulk(ids).status_code, 422)
        response = self.client.post("/api/v1/citizens/bulk-delete", json={"citizen_ids": self.ids[:1], "all": True}, headers=self.headers)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.db.query(Citizen).count(), self.before)

    def test_unsigned_or_missing_session_cannot_delete(self):
        for headers in ({}, {"Authorization": "Bearer demo-token-alcalde"}):
            self.assertEqual(self.bulk(self.ids[:1], headers).status_code, 401)
            self.assertEqual(self.client.delete("/api/v1/citizens/" + self.ids[0], headers=headers).status_code, 401)
        self.assertEqual(self.db.query(Citizen).count(), self.before)

    def test_operator_cannot_delete(self):
        operator = self.db.query(User).filter(User.role == "OPERADOR", User.is_active.is_(True)).first()
        if not operator:
            self.skipTest("No hay operador existente")
        headers = self.authorization(operator)
        self.assertEqual(self.bulk(self.ids[:1], headers).status_code, 403)
        self.assertEqual(self.client.delete("/api/v1/citizens/" + self.ids[0], headers=headers).status_code, 403)
        self.assertEqual(self.db.query(Citizen).count(), self.before)


if __name__ == "__main__":
    unittest.main()
