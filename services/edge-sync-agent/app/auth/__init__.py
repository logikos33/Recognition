"""Device identity: RSA keypair + enrollment + short-lived self-signed JWTs.

Contract reproduced from `scripts/edge_artery_probe.py` (PR #227, the proven
reference): the device owns the private key and auto-signs its own bearer
tokens (RS256) — the cloud never issues a device token (ADR-0019 S7).
"""

from .enrollment import (
    EnrollmentConfig,
    EnrollmentError,
    build_enrollment_config_from_env,
    ensure_enrolled,
)
from .token_manager import (
    DeviceIdentity,
    TokenManager,
    TokenManagerError,
    build_token_manager_from_env,
)

__all__ = [
    "DeviceIdentity",
    "EnrollmentConfig",
    "EnrollmentError",
    "TokenManager",
    "TokenManagerError",
    "build_enrollment_config_from_env",
    "build_token_manager_from_env",
    "ensure_enrolled",
]
