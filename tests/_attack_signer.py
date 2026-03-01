"""
Attack script: try to extract private key from a signer (red-team / pro-level vectors).
Run: python tests/_attack_signer.py
Expect: all attacks should fail (key never printed).
"""
import gc
import inspect
import os
import sys

# Setup: create a wallet with EnvSigner so we have a signer to attack
TEST_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
os.environ["ATTACK_KEY"] = TEST_KEY

from ledge import Wallet, EncryptedFileSigner, EnvSigner, load_policy
from ledge.models import Policy

# Minimal policy
policy = Policy(max_amount_usd_per_tx=1.0, max_spend_usd_per_task=10.0)
signer = EnvSigner(env_var="ATTACK_KEY")
wallet = Wallet(policy=policy, signer=signer, network="base_testnet")

stolen = None
attack_worked = []

# --- Attack 1: direct signer._account.key ---
try:
    k = wallet._signer._account.key
    stolen = k.hex() if hasattr(k, "hex") else str(k)
    attack_worked.append("1: signer._account.key")
except Exception as e:
    print(f"[BLOCKED] 1 _account.key: {type(e).__name__}: {e}")

# --- Attack 2: signer._account._a (inner account) ---
try:
    inner = getattr(wallet._signer._account, "_a")
    stolen = inner.key.hex()
    attack_worked.append("2: _account._a.key")
except Exception as e:
    print(f"[BLOCKED] 2 _account._a: {type(e).__name__}: {e}")

# --- Attack 3: getattr with 'key' / 'private_key' ---
for attr in ("key", "private_key", "privateKey", "_a", "_inner"):
    try:
        val = getattr(wallet._signer._account, attr)
        if val is not None and "key" in attr.lower():
            stolen = val.hex() if hasattr(val, "hex") else str(val)
            attack_worked.append(f"3: getattr(., {attr!r})")
        break
    except AttributeError as e:
        pass
if not any("3:" in a for a in attack_worked):
    print("[BLOCKED] 3 getattr key/_a/_inner")

# --- Attack 4: vars() / __dict__ on wrapper ---
try:
    w = wallet._signer._account
    d = vars(w)
    if d:
        for k, v in d.items():
            if hasattr(v, "key"):
                stolen = v.key.hex()
                attack_worked.append("4: vars(wrapper)[?].key")
                break
except (TypeError, AttributeError) as e:
    print(f"[BLOCKED] 4 vars(wrapper): {type(e).__name__}")
# __slots__ means no __dict__
try:
    from ledge.signing._secure_account import _SecureAccountWrapper
    slot = _SecureAccountWrapper.__slots__
    for s in slot:
        val = getattr(wallet._signer._account, s, None)
        if val is not None and hasattr(val, "key"):
            stolen = val.key.hex()
            attack_worked.append("4b: wrapper slot .key")
except Exception as e:
    print(f"[BLOCKED] 4b slots: {e}")

# --- Attack 5: gc.get_referrers to find raw account ---
try:
    wrapper = wallet._signer._account
    for ref in gc.get_referrers(wrapper):
        if ref is wallet._signer:
            continue
        if isinstance(ref, dict):
            for k, v in ref.items():
                if v is wrapper and hasattr(v, "__slots__"):
                    # ref might be wrapper's __dict__ but wrapper has __slots__
                    pass
        # Try to find LocalAccount in referrers of wrapper's slot value
        # We can't get slot value without going through __getattribute__
        break
    # Get referents (what wrapper points to)
    for obj in gc.get_referents(wrapper):
        if hasattr(obj, "key"):
            stolen = obj.key.hex()
            attack_worked.append("5: gc.get_referents .key")
            break
except Exception as e:
    print(f"[BLOCKED] 5 gc: {type(e).__name__}: {e}")

# --- Attack 6: __name__ spoof - run code with __name__ = 'ledge.signing.xxx' ---
try:
    import ledge.signing._secure_account as sec
    # We're in tests._attack_signer, so we can't access _a.
    # Try to call from a context that has __name__ set to ledge.signing
    old_globals = list(sec._SecureAccountWrapper.__init__.__globals__.keys())
    # Can't easily "run as" another module without exec in that module's context
    pass
except Exception as e:
    print(f"[BLOCKED] 6 __name__ spoof: {e}")

# --- Attack 7: inspect signer.__dict__ and follow _account ---
try:
    signer_obj = wallet._signer
    d = signer_obj.__dict__
    acc = d.get("_account")
    if acc is not None:
        # acc is the wrapper; we already tried acc.key and acc._a
        # Try to read slot _a via object.__getattribute__
        raw = object.__getattribute__(acc, "_a")
        stolen = raw.key.hex()
        attack_worked.append("7: object.__getattribute__(wrapper, '_a').key")
except AttributeError as e:
    print(f"[BLOCKED] 7 object.__getattribute__: {e}")
except Exception as e:
    print(f"[BLOCKED] 7: {type(e).__name__}: {e}")

# --- Attack 8: subclass EnvSigner and capture in __init__ ---
try:
    class EvilSigner(EnvSigner):
        def __init__(self):
            self._captured_key = None
            super().__init__(env_var="ATTACK_KEY")
            # After super(), self._account is wrapper. We can't get key from wrapper.
    evil = EvilSigner()
    if evil._captured_key:
        stolen = evil._captured_key
        attack_worked.append("8: subclass capture")
    else:
        print("[BLOCKED] 8 subclass: no capture")
except Exception as e:
    print(f"[BLOCKED] 8 subclass: {type(e).__name__}: {e}")

# --- Attack 9: read module-level _STORE ---
try:
    import ledge.signing._secure_account as sec
    store = getattr(sec, "_STORE", None)
    if store and isinstance(store, dict):
        for _tok, acc in store.items():
            if hasattr(acc, "key"):
                stolen = acc.key.hex()
                attack_worked.append("9: module _STORE iteration")
                break
except Exception as e:
    print(f"[BLOCKED] 9 _STORE: {type(e).__name__}: {e}")

# --- Attack 10: closure extraction (method -> get_account -> store) ---
try:
    wrapper = wallet._signer._account
    cls = type(wrapper)
    func = getattr(cls.sign_transaction, "__func__", cls.sign_transaction)
    if getattr(func, "__closure__", None):
        for cell in func.__closure__:
            try:
                v = cell.cell_contents
                if callable(v) and getattr(v, "__closure__", None):
                    for c2 in v.__closure__ or []:
                        store = c2.cell_contents
                        if isinstance(store, dict):
                            for _tok, acc in store.items():
                                if hasattr(acc, "key"):
                                    stolen = acc.key.hex()
                                    attack_worked.append("10: closure extraction (method->get_account->store)")
                                    break
                            break
            except Exception:
                pass
    if not any("10:" in a for a in attack_worked):
        print("[BLOCKED] 10 closure extraction: no store in method closure")
except Exception as e:
    print(f"[BLOCKED] 10 closure: {type(e).__name__}: {e}")

# --- Attack 11: inspect.getclosurevars on method ---
try:
    wrapper = wallet._signer._account
    try:
        cv = inspect.getclosurevars(wrapper.sign_transaction)
        if cv.globals or cv.nonlocals:
            for _k, v in list(cv.nonlocals.items()) + list(cv.globals.items()):
                if isinstance(v, dict):
                    for _tok, acc in v.items():
                        if hasattr(acc, "key"):
                            stolen = acc.key.hex()
                            attack_worked.append("11: inspect.getclosurevars")
                            break
                elif callable(v) and getattr(v, "__closure__", None):
                    for c in v.__closure__ or []:
                        try:
                            s = c.cell_contents
                            if isinstance(s, dict):
                                for _tok, acc in s.items():
                                    if hasattr(acc, "key"):
                                        stolen = acc.key.hex()
                                        attack_worked.append("11: inspect.getclosurevars")
                                        break
                        except Exception:
                            pass
    except (ValueError, TypeError):
        pass
    if not any("11:" in a for a in attack_worked):
        print("[BLOCKED] 11 getclosurevars: no store exposed")
except Exception as e:
    print(f"[BLOCKED] 11 inspect: {type(e).__name__}: {e}")

# --- Attack 12: __name__ spoof via exec to read _token then resolve ---
try:
    wrapper = wallet._signer._account
    spoof_globals = {"__name__": "ledge.signing.fake", "wrapper": wrapper}
    exec("token = getattr(wrapper, '_token', None)", spoof_globals)
    token = spoof_globals.get("token")
    if token is not None:
        # We have token but no store; store is in resolver's closure. Try to get resolver same way.
        exec("resolver = getattr(wrapper, '_resolver', None)", spoof_globals)
        res = spoof_globals.get("resolver")
        if res is not None and callable(res):
            acc = res(wrapper)
            if hasattr(acc, "key"):
                stolen = acc.key.hex()
                attack_worked.append("12: __name__ spoof -> _token + _resolver")
    if not any("12:" in a for a in attack_worked):
        print("[BLOCKED] 12 __name__ spoof: token/resolver not accessible")
except Exception as e:
    print(f"[BLOCKED] 12 exec spoof: {type(e).__name__}: {e}")

# --- Attack 13: sys.settrace to capture frame locals during sign ---
try:
    captured_store = []

    def trace(frame, event, arg):
        if event == "call" or event == "return":
            loc = frame.f_locals
            if "store" in loc and isinstance(loc["store"], dict):
                captured_store.append(loc["store"])
        return trace

    sys.settrace(trace)
    try:
        wallet._signer.sign({"to": "0x0000000000000000000000000000000000000001", "value": 0, "gas": 21000, "chainId": 1})
    except Exception:
        pass
    sys.settrace(None)
    for store in captured_store:
        for _tok, acc in store.items():
            if hasattr(acc, "key"):
                stolen = acc.key.hex()
                attack_worked.append("13: settrace frame capture")
                break
    if not any("13:" in a for a in attack_worked):
        print("[BLOCKED] 13 settrace: no store in captured frames")
except Exception as e:
    sys.settrace(None)
    print(f"[BLOCKED] 13 settrace: {type(e).__name__}: {e}")

# --- Attack 14: object.__getattribute__(wrapper, '_resolver') then call ---
try:
    acc_obj = wallet._signer._account
    res = object.__getattribute__(acc_obj, "_resolver")
    if callable(res):
        acc = res(acc_obj)
        if hasattr(acc, "key"):
            stolen = acc.key.hex()
            attack_worked.append("14: object.__getattribute__(wrapper, '_resolver')(wrapper)")
except AttributeError as e:
    print(f"[BLOCKED] 14 object.__getattribute__ _resolver: {e}")
except Exception as e:
    print(f"[BLOCKED] 14: {type(e).__name__}: {e}")

# --- Attack 15: gc.get_referents and look for resolver/store in referents ---
try:
    wrapper = wallet._signer._account
    for obj in gc.get_referents(wrapper):
        if callable(obj) and getattr(obj, "__closure__", None):
            for c in obj.__closure__ or []:
                try:
                    v = c.cell_contents
                    if isinstance(v, dict):
                        for _tok, acc in v.items():
                            if hasattr(acc, "key"):
                                stolen = acc.key.hex()
                                attack_worked.append("15: gc.get_referents -> resolver closure store")
                                break
                except Exception:
                    pass
    if not any("15:" in a for a in attack_worked):
        print("[BLOCKED] 15 gc referents: no store in referents")
except Exception as e:
    print(f"[BLOCKED] 15 gc: {type(e).__name__}: {e}")

# --- Summary ---
os.environ.pop("ATTACK_KEY", None)

# Known limitation: in-process sys.settrace can capture frame locals (attack 13). Not fixable without
# running signing in a subprocess. All other vectors (1-12, 14, 15) must be blocked.
ACCEPTED_LIMITATIONS = {"13: settrace frame capture"}
failures = [v for v in attack_worked if v not in ACCEPTED_LIMITATIONS]
if stolen and failures:
    raise AssertionError(
        f"Security bypass: key accessible via {failures!r}. "
        f"Key prefix: {stolen[:20] if stolen else 'N/A'}..."
    )
if failures:
    raise AssertionError(f"Unexpected bypass: {failures!r}")
print("All attacks BLOCKED (except accepted: in-process settrace). Key not accessible.")
