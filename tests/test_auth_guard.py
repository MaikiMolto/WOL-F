"""Auth-guard and token-auth tests.

Covers the before_request session guard, the token bypass for headless clients,
and the CSRF path used by the browser UI.

Runs against a temporary DB_DIR — it never touches real application data.

Usage:
    python tests/test_auth_guard.py [path-to-repo]

With no argument it tests the repo it lives in. Pass another checkout to compare
behaviour (e.g. an unfixed tree, to confirm a test actually detects the bug).
"""
import os
import pathlib
import sys
import tempfile

REPO = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else
                    pathlib.Path(__file__).resolve().parent.parent)
TOKEN = "test-token-123"

# Isolate all persistent state in a temp dir. MUST be set before importing the app:
# DB_DIR is read at import time. Never point this at a real deployment directory.
_tmp = tempfile.mkdtemp(prefix="wolf-test-")
os.environ.update({
    "DB_DIR":           _tmp,
    "SECRET_KEY":       "test-secret-key",
    "ENABLE_LOGIN":     "true",
    "USERNAME":         "admin",
    "PASSWORD":         "secret",
    "STATUS_API_TOKEN": TOKEN,
})

sys.path.insert(0, str(REPO / "app"))
import wol  # noqa: E402

assert wol.DB_DIR == _tmp, f"test isolation failed: DB_DIR is {wol.DB_DIR!r}, refusing to run"

# No packets, no subprocesses, no network.
wol.is_computer_awake = lambda *a, **k: False          # deterministic: always 'asleep'
for _fn in ("send_magic_packet", "send_wol", "send_sol", "send_l2_packet"):
    if hasattr(wol, _fn):
        setattr(wol, _fn, lambda *a, **k: None)

MAC = {"mac_address": "aa:bb:cc:dd:ee:ff"}

with wol.app.app_context():
    wol.db.create_all()
    if not wol.Computer.query.filter_by(mac_address=MAC["mac_address"]).first():
        wol.db.session.add(wol.Computer(
            mac_address=MAC["mac_address"], name="testbox",
            ip_address="192.0.2.10", test_type="ping", type="pc", link=""))
        wol.db.session.commit()

wol.app.config["WTF_CSRF_ENABLED"] = True

results = []


def check(name, got, want):
    ok = got == want
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:<46} -> {got}  (expected {want})")


def client(logged_in=False):
    c = wol.app.test_client()
    if logged_in:
        with c.session_transaction() as s:
            s["logged_in"] = True
    return c


def csrf_token(c):
    """The token the UI's global fetch patch reads from the page's meta tag."""
    import re
    html = c.get("/").get_data(as_text=True)
    m = re.search(r'<meta name="csrf-token" content="([^"]+)"', html)
    assert m, "page did not render a csrf-token meta tag"
    return m.group(1)


print("=== headless clients: token auth on the control route ===")
c = client()
check("POST /wol_or_sol_send  X-API-Key",
      c.post("/wol_or_sol_send", data=MAC, headers={"X-API-Key": TOKEN}).status_code, 200)
check("POST /wol_or_sol_send  Bearer",
      c.post("/wol_or_sol_send", data=MAC,
             headers={"Authorization": f"Bearer {TOKEN}"}).status_code, 200)

print("\n=== the control route must NOT accept a query token ===")
# ?token= leaks the secret into access logs and browser history. The session guard
# rejects it first (401), so the request never even reaches the route's CSRF check.
check("POST /wol_or_sol_send  ?token= (must be rejected)",
      c.post(f"/wol_or_sol_send?token={TOKEN}", data=MAC).status_code, 401)
check("GET  /api/status       ?token= (legacy, still allowed)",
      c.get(f"/api/status?token={TOKEN}").status_code, 200)

print("\n=== rejected without a valid token ===")
check("POST /wol_or_sol_send  wrong token",
      c.post("/wol_or_sol_send", data=MAC, headers={"X-API-Key": "wrong"}).status_code, 401)
check("POST /wol_or_sol_send  no token, no session",
      c.post("/wol_or_sol_send", data=MAC).status_code, 401)
check("GET  /api/status       wrong token",
      c.get("/api/status", headers={"X-API-Key": "wrong"}).status_code, 302)
check("GET  /                 no session -> login",
      c.get("/").status_code, 302)

print("\n=== the whitelist is narrow: other routes stay session-only ===")
# /add_computer is not csrf-exempt, so its CSRF check fires before the login guard.
# 400 and 401 both mean rejected; the point is that a token does NOT let you in.
check("POST /add_computer     with token (must NOT pass)",
      c.post("/add_computer", data={"mac_address": "11:22:33:44:55:66"},
             headers={"X-API-Key": TOKEN}).status_code in (400, 401), True)

print("\n=== browser UI: CSRF still enforced, and still works ===")
b = client(logged_in=True)
check("POST /wol_or_sol_send  session, no CSRF token",
      b.post("/wol_or_sol_send", data=MAC).status_code, 400)
# The UI patches window.fetch to inject X-CSRFToken from the meta tag (wol_form.html).
check("POST /wol_or_sol_send  session + CSRF header (real UI path)",
      b.post("/wol_or_sol_send", data=MAC,
             headers={"X-CSRFToken": csrf_token(b)}).status_code, 200)

print("\n=== no token configured: the bypass is impossible ===")
_saved = wol.STATUS_API_TOKEN
wol.STATUS_API_TOKEN = ""
try:
    n = client()
    check("POST /wol_or_sol_send  token unset, header sent",
          n.post("/wol_or_sol_send", data=MAC,
                 headers={"X-API-Key": TOKEN}).status_code, 401)
    check("GET  /api/status       token unset",
          n.get("/api/status", headers={"X-API-Key": TOKEN}).status_code, 302)
finally:
    wol.STATUS_API_TOKEN = _saved

print("\n=== ENABLE_LOGIN=false: guard is off, route still decides ===")
_saved_login = wol.ENABLE_LOGIN
wol.ENABLE_LOGIN = False
try:
    a = client()
    check("POST /wol_or_sol_send  no login, valid token",
          a.post("/wol_or_sol_send", data=MAC,
                 headers={"X-API-Key": TOKEN}).status_code, 200)
    # Without a token the route still demands CSRF, even with the guard disabled.
    check("POST /wol_or_sol_send  no login, no token -> CSRF",
          a.post("/wol_or_sol_send", data=MAC).status_code, 400)
    check("GET  /                 no login, no session",
          a.get("/").status_code, 200)
finally:
    wol.ENABLE_LOGIN = _saved_login

print(f"\n{sum(results)}/{len(results)} green")
sys.exit(0 if all(results) else 1)
