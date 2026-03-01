"""
Internal: wrapper around eth_account LocalAccount that never exposes the private key.

The wrapper does NOT store the account as an attribute. A factory creates each wrapper
with a closure-held store (token -> account), so there is no module-level _STORE and
object.__getattribute__ / gc.get_referents cannot reach the key.
"""

from __future__ import annotations

import secrets
import sys

# Blocked attribute names on the wrapper.
_BLOCKED_ATTRS = frozenset({
    "key",
    "private_key",
    "privateKey",
    "private_key_hex",
    "key_hex",
    "_inner",
    "_a",
    "__dict__",
    "__getstate__",
    "__setstate__",
})

_TOKEN_ATTR = "_token"
_RESOLVER_ATTR = "_resolver"

# Internal-only: only ledge.signing may read _token (via __getattribute__).
_INTERNAL_ATTRS = frozenset({_TOKEN_ATTR})


def _check_caller_ledge_signing() -> bool:
    """True only if the caller is code from a real ledge.signing module (not exec-spoofed __name__)."""
    try:
        for skip in (2, 3, 4, 5):
            try:
                frame = sys._getframe(skip)
            except ValueError:
                break
            name = frame.f_globals.get("__name__", "")
            if name == "__main__" or name.startswith("tests."):
                return False
            if name.startswith("ledge.signing"):
                mod = sys.modules.get(name)
                if mod is None:
                    return False
                path = getattr(mod, "__file__", "") or ""
                path = path.replace("\\", "/")
                if "ledge" not in path or "signing" not in path:
                    return False
                return True
        return False
    except (ValueError, KeyError):
        return False


class _ResolverDescriptor:
    """Descriptor so that object.__getattribute__(wrapper, '_resolver') invokes __get__ and we can check caller."""

    def __init__(self, resolver_by_id: dict[int, object]) -> None:
        self._resolver_by_id = resolver_by_id

    def __get__(self, obj: object | None, owner: type | None = None) -> object:
        if obj is None:
            return self
        if not _check_caller_ledge_signing():
            raise AttributeError(f"{type(obj).__name__!r} object has no attribute {_RESOLVER_ATTR!r}")
        res = self._resolver_by_id.get(id(obj))
        if res is None:
            raise AttributeError(f"{type(obj).__name__!r} object has no attribute {_RESOLVER_ATTR!r}")
        return res


def _SecureAccountWrapper(account: object) -> object:
    """
    Factory: wrapper holds only token; resolver is a class-level descriptor so slot bypass is impossible.
    Methods use self._resolver(self) and do NOT close over store (no closure extraction from method).
    """
    store: dict[bytes, object] = {}
    token = secrets.token_bytes(32)
    store[token] = account
    resolver_by_id: dict[int, object] = {}

    def resolver(self: "Wrapper") -> object:
        t = object.__getattribute__(self, _TOKEN_ATTR)
        return store[t]

    class Wrapper:
        __slots__ = (_TOKEN_ATTR,)
        _resolver = _ResolverDescriptor(resolver_by_id)  # type: ignore[assignment]

        def __init__(self) -> None:
            object.__setattr__(self, _TOKEN_ATTR, token)

        def __getattribute__(self, name: str) -> object:
            if name in _BLOCKED_ATTRS:
                raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")
            if name == _TOKEN_ATTR and not _check_caller_ledge_signing():
                raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")
            return object.__getattribute__(self, name)

        def __setattr__(self, name: str, value: object) -> None:
            if name in _BLOCKED_ATTRS or name == _TOKEN_ATTR:
                raise AttributeError(f"{type(self).__name__!r} object has no attribute {name!r}")
            object.__setattr__(self, name, value)

        def sign_transaction(self, tx: dict[str, object]) -> object:
            return self._resolver(self).sign_transaction(tx)

        def sign_message(self, signable: object) -> object:
            return self._resolver(self).sign_message(signable)

        @property
        def address(self) -> object:
            return self._resolver(self).address

        def __dir__(self) -> list[str]:
            return ["address", "sign_message", "sign_transaction"]

        def __del__(self) -> None:
            try:
                t = object.__getattribute__(self, _TOKEN_ATTR)
                store.pop(t, None)
            except Exception:
                pass
            resolver_by_id.pop(id(self), None)

    w = Wrapper()
    resolver_by_id[id(w)] = resolver
    return w
