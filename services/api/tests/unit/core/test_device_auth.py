"""Testes unitários — device_auth (claim codes + enrollment token)."""
from app.core.device_auth import (
    _CLAIM_ALPHABET,
    CLAIM_CODE_LENGTH,
    generate_claim_code,
    generate_enrollment_token,
    hash_claim_code,
)

TENANT = "11111111-1111-1111-1111-111111111111"
CLAIM_ID = "33333333-3333-3333-3333-333333333333"


class TestGenerateClaimCode:
    def test_length_is_8(self):
        assert len(generate_claim_code()) == CLAIM_CODE_LENGTH == 8

    def test_uses_unambiguous_alphabet(self):
        for _ in range(50):
            code = generate_claim_code()
            assert all(c in _CLAIM_ALPHABET for c in code)
            # Sem caracteres ambíguos
            assert not any(c in "0O1IL" for c in code)

    def test_codes_are_random(self):
        codes = {generate_claim_code() for _ in range(50)}
        assert len(codes) > 45  # colisões em 50 amostras seriam suspeitas


class TestHashClaimCode:
    def test_sha256_hex_64_chars(self):
        digest = hash_claim_code("ABCD2345")
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)

    def test_normalizes_case_spaces_and_hyphens(self):
        base = hash_claim_code("ABCD2345")
        assert hash_claim_code("abcd2345") == base
        assert hash_claim_code(" ABCD-2345 ") == base
        assert hash_claim_code("abcd 2345") == base

    def test_different_codes_different_hashes(self):
        assert hash_claim_code("ABCD2345") != hash_claim_code("ABCD2346")


class TestGenerateEnrollmentToken:
    def test_token_carries_device_enrollment_claims(self, app):
        from flask_jwt_extended import decode_token

        with app.app_context():
            token = generate_enrollment_token(TENANT, CLAIM_ID)
            payload = decode_token(token)

        assert payload["token_type"] == "device_enrollment"
        assert payload["tenant_id"] == TENANT
        assert payload["sub"] == CLAIM_ID
        assert payload["exp"] > payload["iat"]
