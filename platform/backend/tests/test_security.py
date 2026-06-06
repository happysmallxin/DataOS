"""Test JWT security utilities."""

from app.core.security import hash_password, verify_password, create_access_token, decode_access_token


class TestPasswordHashing:
    def test_hash_password(self):
        hashed = hash_password("mypassword")
        assert hashed != "mypassword"
        assert hashed.startswith("$2b$")

    def test_verify_correct_password(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed)

    def test_verify_wrong_password(self):
        hashed = hash_password("mypassword")
        assert not verify_password("wrongpassword", hashed)


class TestJWT:
    def test_create_and_decode_token(self):
        token = create_access_token(data={"sub": "1", "username": "admin"})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == "1"
        assert payload["username"] == "admin"
        assert "exp" in payload

    def test_decode_invalid_token(self):
        assert decode_access_token("invalid.token.here") is None
        assert decode_access_token("") is None

    def test_token_contains_iat(self):
        token = create_access_token(data={"sub": "42"})
        payload = decode_access_token(token)
        assert "iat" in payload
