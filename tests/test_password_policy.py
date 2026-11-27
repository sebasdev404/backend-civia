"""The same composition rules apply to every newly chosen password."""
import unittest
from pydantic import ValidationError
from app.schemas.user import UserCreate, UserLogin, ResetPasswordRequest, ChangePasswordRequest


class PasswordPolicyTests(unittest.TestCase):
    def schemas(self, password):
        return (
            (UserCreate, {'email': 'policy@fixture.invalid', 'full_name': 'Policy fixture', 'password': password}),
            (ResetPasswordRequest, {'email': 'policy@fixture.invalid', 'otp_code': '246810', 'new_password': password}),
            (ChangePasswordRequest, {'current_password': '1234', 'new_password': password}),
        )

    def test_missing_each_requirement_is_rejected_in_every_flow(self):
        for password in ('Aa1!short', 'onlylowercase1!', 'ONLYUPPERCASE1!', 'NoDigitsHere!', 'NoSymbolsHere1',
                         'NoSymbolSpace1 ', '           '):
            for schema, payload in self.schemas(password):
                with self.subTest(schema=schema.__name__, case=password):
                    with self.assertRaises(ValidationError):
                        schema(**payload)

    def test_valid_passwords_accept_unicode_without_modifying_the_value(self):
        for password in ('Safe-password-2026', 'ÁrbolesFuertes7!', 'ÁrbolesFuertes٧€', 'Aa1!' + 'é' * 34,
                         'Aa1!' + 'a' * 68, ' Space-Allowed7! '):
            for schema, payload in self.schemas(password):
                with self.subTest(schema=schema.__name__, case=password):
                    result = schema(**payload)
                    field = 'password' if schema is UserCreate else 'new_password'
                    self.assertEqual(getattr(result, field), password)

    def test_bcrypt_byte_limit_is_checked_after_composition(self):
        for schema, payload in self.schemas('Aa1!' + 'é' * 35):
            with self.subTest(schema=schema.__name__):
                with self.assertRaises(ValidationError):
                    schema(**payload)

    def test_1234_is_only_an_initial_admin_created_password(self):
        self.assertEqual(UserCreate(email='default@fixture.invalid', full_name='Fixture').password, '1234')
        self.assertEqual(UserCreate(email='default@fixture.invalid', full_name='Fixture', password='1234').password, '1234')
        for schema, payload in self.schemas('1234')[1:]:
            with self.assertRaises(ValidationError):
                schema(**payload)

    def test_existing_legacy_passwords_can_still_be_submitted_to_login(self):
        for password in ('1234', 'legacy-password'):
            self.assertEqual(UserLogin(email='login@fixture.invalid', password=password).password, password)
