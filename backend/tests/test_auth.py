import asyncio
from types import SimpleNamespace
from unittest import TestCase
from uuid import uuid4

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth.dependencies import get_current_user, get_current_user_id


class FakeAuthClient:
    def __init__(self, claims=None, error: Exception | None = None) -> None:
        self.claims = claims
        self.error = error
        self.received_token = None

    def get_claims(self, token: str):
        self.received_token = token
        if self.error:
            raise self.error
        return {"claims": self.claims}


class AuthDependencyTests(TestCase):
    def test_full_user_and_id_dependencies_share_token_validation(self):
        user_id = uuid4()
        credentials = HTTPAuthorizationCredentials(scheme='Bearer', credentials='verified-token')
        supabase = SimpleNamespace(auth=FakeAuthClient(
            claims={'sub': str(user_id), 'role': 'authenticated', 'email': 'member@example.com'},
        ))
        user = asyncio.run(get_current_user(credentials, supabase))
        self.assertEqual(user.id, asyncio.run(get_current_user_id(credentials, supabase)))
        self.assertEqual(user.email, 'member@example.com')
        for dependency in (get_current_user, get_current_user_id):
            for claims in (None, {'sub': str(user_id), 'role': 'service_role'}, {'role': 'authenticated'}, {'sub': 'bad', 'role': 'authenticated'}):
                with self.subTest(dependency=dependency.__name__, claims=claims):
                    with self.assertRaises(HTTPException) as context:
                        asyncio.run(dependency(credentials, SimpleNamespace(auth=FakeAuthClient(claims))))
                    self.assertEqual(context.exception.status_code, 401)
                    self.assertEqual(context.exception.headers, {'WWW-Authenticate': 'Bearer'})
            with self.assertRaises(HTTPException) as context:
                asyncio.run(dependency(None, supabase))
            self.assertEqual(context.exception.status_code, 401)

    def test_only_full_user_dependency_requires_email(self):
        credentials = HTTPAuthorizationCredentials(scheme='Bearer', credentials='verified-token')
        user_id = uuid4()
        supabase = SimpleNamespace(auth=FakeAuthClient(claims={'sub': str(user_id), 'role': 'authenticated'}))
        self.assertEqual(asyncio.run(get_current_user_id(credentials, supabase)), user_id)
        with self.assertRaises(HTTPException) as context:
            asyncio.run(get_current_user(credentials, supabase))
        self.assertEqual(context.exception.status_code, 401)

    def test_returns_verified_user_uuid(self) -> None:
        user_id = uuid4()
        auth = FakeAuthClient(
            claims={"sub": str(user_id), "role": "authenticated"}
        )
        supabase = SimpleNamespace(auth=auth)

        result = asyncio.run(
            get_current_user_id(
                HTTPAuthorizationCredentials(
                    scheme="Bearer",
                    credentials="verified-token",
                ),
                supabase,
            )
        )

        self.assertEqual(result, user_id)
        self.assertEqual(auth.received_token, "verified-token")

    def test_rejects_missing_bearer_token(self) -> None:
        with self.assertRaises(HTTPException) as context:
            asyncio.run(
                get_current_user_id(
                    None,
                    SimpleNamespace(auth=FakeAuthClient()),
                )
            )

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(context.exception.detail, "Authentication required")

    def test_rejects_invalid_claims(self) -> None:
        with self.assertRaises(HTTPException) as context:
            asyncio.run(
                get_current_user_id(
                    HTTPAuthorizationCredentials(
                        scheme="Bearer",
                        credentials="invalid-token",
                    ),
                    SimpleNamespace(
                        auth=FakeAuthClient(
                            claims={"sub": "not-a-uuid", "role": "authenticated"}
                        )
                    ),
                )
            )

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(
            context.exception.detail,
            "Invalid or expired access token",
        )
