"""Tests for signing providers."""

import copy
import json
import os
import pickle
from pathlib import Path

import pytest
from eth_account import Account

from ledge.errors import SigningFailed
from ledge.signing.encrypted_file_signer import EncryptedFileSigner
from ledge.signing.env_signer import EnvSigner
from ledge.signing.mock_signer import MockSigner


def _write_keystore_json(path: Path, private_key_hex: str, password: str) -> None:
    """Write Ethereum keystore JSON v3 to path (test helper; SDK does not create key files)."""
    account = Account.from_key(private_key_hex)
    keystore = Account.encrypt(account.key, password)
    path.write_text(json.dumps(keystore), encoding="utf-8")


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


# --- EncryptedFileSigner ---


def test_encrypted_file_signer_load_and_sign(tmp_path: Path) -> None:
    key_file = tmp_path / "keystore.json"
    _write_keystore_json(key_file, TEST_KEY, "secret-pass")
    signer = EncryptedFileSigner(key_file, passphrase="secret-pass")
    assert signer.address.startswith("0x")
    assert len(signer.address) == 42
    sig = signer.sign_typed_data({"chainId": 1}, {}, {"value": 1})
    assert isinstance(sig, str)
    assert sig.startswith("0x")


def test_encrypted_file_signer_same_address_as_env_signer(tmp_path: Path) -> None:
    key_file = tmp_path / "keystore.json"
    _write_keystore_json(key_file, TEST_KEY, "pass")
    enc_signer = EncryptedFileSigner(key_file, passphrase="pass")
    os.environ["TMP_KEY"] = TEST_KEY
    try:
        env_signer = EnvSigner(env_var="TMP_KEY")
        assert enc_signer.address == env_signer.address
    finally:
        os.environ.pop("TMP_KEY", None)


def test_encrypted_file_signer_wrong_passphrase_raises(tmp_path: Path) -> None:
    key_file = tmp_path / "keystore.json"
    _write_keystore_json(key_file, TEST_KEY, "right-pass")
    with pytest.raises(SigningFailed, match="Decryption failed"):
        EncryptedFileSigner(key_file, passphrase="wrong-pass")


def test_encrypted_file_signer_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        EncryptedFileSigner("/nonexistent/keystore.json", passphrase="x")


def test_encrypted_file_signer_repr_has_no_key(tmp_path: Path) -> None:
    key_file = tmp_path / "keystore.json"
    _write_keystore_json(key_file, TEST_KEY, "pass")
    signer = EncryptedFileSigner(key_file, passphrase="pass")
    rep = repr(signer)
    assert TEST_KEY not in rep
    assert "pass" not in rep
    assert "EncryptedFileSigner" in rep


def test_encrypted_file_signer_passphrase_from_env(tmp_path: Path) -> None:
    key_file = tmp_path / "keystore.json"
    _write_keystore_json(key_file, TEST_KEY, "env-secret")
    os.environ["LEDGE_TEST_PASSPHRASE"] = "env-secret"
    try:
        signer = EncryptedFileSigner(key_file, passphrase_env="LEDGE_TEST_PASSPHRASE")
        assert signer.address.startswith("0x")
        assert "LEDGE_TEST_PASSPHRASE" not in os.environ
    finally:
        os.environ.pop("LEDGE_TEST_PASSPHRASE", None)


def test_encrypted_file_signer_raises_if_passphrase_missing(tmp_path: Path) -> None:
    key_file = tmp_path / "keystore.json"
    _write_keystore_json(key_file, TEST_KEY, "pass")
    os.environ.pop("MISSING_PASSPHRASE_VAR", None)
    with pytest.raises(ValueError, match="Passphrase not set"):
        EncryptedFileSigner(key_file, passphrase_env="MISSING_PASSPHRASE_VAR")


def test_encrypted_file_signer_invalid_keystore_raises(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.json"
    bad_file.write_text('{"version": 3}', encoding="utf-8")
    with pytest.raises(SigningFailed, match="Decryption failed|Invalid key file"):
        EncryptedFileSigner(bad_file, passphrase="any")


def test_signer_account_does_not_expose_key_env() -> None:
    """Agent/code cannot read private key via signer._account.key (EnvSigner)."""
    os.environ["TEST_KEY_EXPOSE"] = TEST_KEY
    try:
        signer = EnvSigner(env_var="TEST_KEY_EXPOSE")
        with pytest.raises(AttributeError, match="key|private_key|no attribute"):
            _ = signer._account.key
        with pytest.raises(AttributeError, match="no attribute"):
            _ = signer._account.private_key
    finally:
        os.environ.pop("TEST_KEY_EXPOSE", None)


def test_signer_account_does_not_expose_key_encrypted(tmp_path: Path) -> None:
    """Agent/code cannot read private key via signer._account.key (EncryptedFileSigner)."""
    key_file = tmp_path / "keystore.json"
    _write_keystore_json(key_file, TEST_KEY, "pass")
    signer = EncryptedFileSigner(key_file, passphrase="pass")
    with pytest.raises(AttributeError, match="key|private_key|no attribute"):
        _ = signer._account.key
    with pytest.raises(AttributeError, match="no attribute"):
        _ = signer._account.private_key


def test_signer_cannot_be_pickled() -> None:
    """SigningProvider instances must not be picklable (no key material over the wire)."""
    os.environ["TEST_PICKLE_KEY"] = TEST_KEY
    try:
        signer = EnvSigner(env_var="TEST_PICKLE_KEY")
        with pytest.raises(TypeError, match="cannot be pickled"):
            pickle.dumps(signer)
    finally:
        os.environ.pop("TEST_PICKLE_KEY", None)


def test_signer_cannot_be_copied() -> None:
    """SigningProvider instances must not be copy/deepcopy (no key material duplication)."""
    os.environ["TEST_COPY_KEY"] = TEST_KEY
    try:
        signer = EnvSigner(env_var="TEST_COPY_KEY")
        with pytest.raises(TypeError, match="cannot be copied"):
            copy.copy(signer)
        with pytest.raises(TypeError, match="cannot be copied"):
            copy.deepcopy(signer)
    finally:
        os.environ.pop("TEST_COPY_KEY", None)


def test_secure_wrapper_dir_does_not_expose_inner() -> None:
    """dir(signer._account) must not suggest _a or other key-related attrs."""
    os.environ["TEST_DIR_KEY"] = TEST_KEY
    try:
        signer = EnvSigner(env_var="TEST_DIR_KEY")
        attrs = dir(signer._account)
        assert "_a" not in attrs
        assert "key" not in attrs
        assert "private_key" not in attrs
        assert "sign_transaction" in attrs
        assert "sign_message" in attrs
        assert "address" in attrs
    finally:
        os.environ.pop("TEST_DIR_KEY", None)


def test_secure_wrapper_inner_account_not_accessible_outside_ledge_signing() -> None:
    """Code outside ledge.signing (e.g. tests or agent) must not access wrapper._a."""
    os.environ["TEST_INNER_KEY"] = TEST_KEY
    try:
        signer = EnvSigner(env_var="TEST_INNER_KEY")
        with pytest.raises(AttributeError, match="no attribute '_a'|no attribute \"_a\""):
            _ = signer._account._a
    finally:
        os.environ.pop("TEST_INNER_KEY", None)
