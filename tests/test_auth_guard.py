"""Verifiziert den before_request-Guard-Fix gegen die echte App.

Die App hat alle DB-Pfade hart auf /app/db/ — den Ordner legen wir einfach an.
Alles Netzwerk-nahe (WOL/SOL-Senden, Status-Probes) wird gemockt, damit kein
Paket rausgeht und kein subprocess laeuft.

Aufruf:  python test_guard.py <pfad-zum-repo>
"""
import os, sys, shutil, pathlib

REPO  = sys.argv[1] if len(sys.argv) > 1 else "."
TOKEN = "test-token-123"

# Frischer /app/db pro Lauf (App-Pfade sind hartkodiert)
shutil.rmtree("/app/db", ignore_errors=True)
os.makedirs("/app/db", exist_ok=True)

# Echte ENV-Namen laut app/wol.py: USERNAME / PASSWORD (nicht LOGIN_*)
os.environ.update({
    "ENABLE_LOGIN":     "true",
    "USERNAME":         "admin",
    "PASSWORD":         "secret",
    "STATUS_API_TOKEN": TOKEN,
    "SECRET_KEY":       "test-secret-key",
})

sys.path.insert(0, str(pathlib.Path(REPO) / "app"))
import wol

# --- Netzwerk stillegen -----------------------------------------------------
wol.is_computer_awake = lambda *a, **k: False        # -> Pfad: WOL senden
for fn in ("send_magic_packet", "send_wol", "send_sol",
           "send_wol_packet", "send_sol_packet", "send_l2_packet"):
    if hasattr(wol, fn):
        setattr(wol, fn, lambda *a, **k: None)

with wol.app.app_context():
    wol.db.create_all()
    if not wol.Computer.query.filter_by(mac_address="aa:bb:cc:dd:ee:ff").first():
        wol.db.session.add(wol.Computer(
            mac_address="aa:bb:cc:dd:ee:ff", name="testbox",
            ip_address="192.0.2.10", test_type="ping", type="pc", link=""))
        wol.db.session.commit()

wol.app.config["WTF_CSRF_ENABLED"] = True
c   = wol.app.test_client()
MAC = {"mac_address": "aa:bb:cc:dd:ee:ff"}

results = []
def check(name, got, want):
    ok = got == want
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:<44} -> {got}  (erwartet {want})")

print("=== ENABLE_LOGIN=true ===")

# 1+2) DER BUG: Token-Auth auf /wol_or_sol_send  (ohne Fix: 401)
r = c.post("/wol_or_sol_send", data=MAC, headers={"X-API-Key": TOKEN})
check("POST /wol_or_sol_send  X-API-Key", r.status_code, 200)

r = c.post("/wol_or_sol_send", data=MAC, headers={"Authorization": f"Bearer {TOKEN}"})
check("POST /wol_or_sol_send  Bearer", r.status_code, 200)

# 3+4) REGRESSION: falscher / fehlender Token bleibt draussen
r = c.post("/wol_or_sol_send", data=MAC, headers={"X-API-Key": "falsch"})
check("POST /wol_or_sol_send  FALSCHER Token", r.status_code, 401)

r = c.post("/wol_or_sol_send", data=MAC)
check("POST /wol_or_sol_send  ohne Token/Session", r.status_code, 401)

# 5) REGRESSION: /api/status unveraendert erreichbar
r = c.get("/api/status", headers={"X-API-Key": TOKEN})
check("GET  /api/status       mit Token", r.status_code, 200)

# 6) REGRESSION: GET auf UI -> Login-Redirect
r = c.get("/")
check("GET  /                 ohne Session", r.status_code, 302)

# 7) REGRESSION: Whitelist ist eng — anderer POST bleibt token-fest.
#    /add_computer ist nicht csrf.exempt, also faengt der CSRF-Check schon
#    vor dem Login-Guard ab -> 400 (nicht 401). Beides = abgelehnt.
r = c.post("/add_computer", data={"mac_address": "11:22:33:44:55:66"},
           headers={"X-API-Key": TOKEN})
check("POST /add_computer     mit Token (darf NICHT)", r.status_code in (400, 401), True)

# 8) REGRESSION: Browser-Session ohne CSRF -> weiterhin 400
with c.session_transaction() as s:
    s["logged_in"] = True
r = c.post("/wol_or_sol_send", data=MAC)
check("POST /wol_or_sol_send  Session ohne CSRF", r.status_code, 400)

print(f"\n{sum(results)}/{len(results)} gruen")
sys.exit(0 if all(results) else 1)
