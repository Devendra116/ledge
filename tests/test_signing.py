"""Tests for signing providers."""

import os

import pytest

from ledge.signing.env_signer import EnvSigner
from ledge.signing.mock_signer import MockSigner


def test_mock_sign_returns_string() -> None:
    s = MockSigner()
    result = s.sign({"to": "0xabc", "value": 1000})
    assert isinstance(result, str)
    assert result.startswith("0x")


def test_mock_sign_typed_data_returns_string() -> None:
    s = MockSigner()
    result = s.sign_typed_data({}, {}, {"value": 100})
    assert isinstance(result, str)
    assert result.startswith("0x")


def test_mock_address_accessible() -> None:
    s = MockSigner()
    assert s.address.startswith("0x")


def test_mock_repr_safe() -> None:
    s = MockSigner()
    assert "key" not in repr(s).lower()


TEST_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


def test_env_signer_removes_key_from_env() -> None:
    os.environ["TEST_LEDGE_KEY"] = TEST_KEY
    _ = EnvSigner(env_var="TEST_LEDGE_KEY")
    assert "TEST_LEDGE_KEY" not in os.environ


def test_env_signer_address_accessible() -> None:
    os.environ["TEST_LEDGE_KEY"] = TEST_KEY
    signer = EnvSigner(env_var="TEST_LEDGE_KEY")
    assert signer.address.startswith("0x")
    assert len(signer.address) == 42


def test_env_signer_raises_if_no_env_var() -> None:
    os.environ.pop("MISSING_KEY", None)
    with pytest.raises(ValueError, match="not set"):
        EnvSigner(env_var="MISSING_KEY")


def test_env_signer_repr_has_no_key() -> None:
    os.environ["TEST_LEDGE_KEY"] = TEST_KEY
    signer = EnvSigner(env_var="TEST_LEDGE_KEY")
    rep = repr(signer)
    assert TEST_KEY not in rep
    assert "key" not in rep.lower()


def test_env_signer_sign_typed_data() -> None:
    os.environ["TEST_LEDGE_KEY"] = TEST_KEY
    signer = EnvSigner(env_var="TEST_LEDGE_KEY")
    domain = {
        "name": "TestToken",
        "version": "1",
        "chainId": 84532,
        "verifyingContract": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    }
    types = {
        "Transfer": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
        ]
    }
    message = {
        "from": signer.address,
        "to": "0x742d35Cc6634C0532925a3b8D4C9C3E0a1b2f3A4",
        "value": 10000,
    }
    sig = signer.sign_typed_data(domain, types, message)
    assert isinstance(sig, str)
    assert sig.lower().startswith("0x")
    assert len(sig) > 10
