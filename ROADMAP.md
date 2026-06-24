# WOL-F — Roadmap

**WOL-F** = **W**ake **O**n **L**an **F**leet
Eigenständiges, modernes Wake-/Sleep-on-LAN Dashboard fürs Homelab.

- **Herausgeber:** Maik & Nex
- **Basis:** Fork von [gptwol](https://github.com/Misterbabou/gptwol) (Misterbabou)
- **Lizenz:** MIT (Original-Copyright + NOTICE für Misterbabou bleibt erhalten)

---

## ✅ v1.0 — Released

**Identität & Rebranding**
- [x] Eigenständiges Branding „WOL-F" (Name, README, NOTICE für Misterbabou, Herausgeber Maik & Nex)
- [x] Logo: freigestellter Wolf + WOL-F-Wortmarke + Tagline

**UI / Design**
- [x] Komplett überarbeitetes UI — **Dark-** & Light-Theme (Dark als Default)
- [x] Voll responsive (Desktop + Mobile)
- [x] **DE/EN** mit Live-Sprachumschalter
- [x] **Smart On/Off-Switch** (iOS-Toggle): Grün=ON, Rot=OFF, Gelb=Pending · 5s-Poll im Pending · 4-Min-Timeout
- [x] Farbiger Status-Streifen links an der Kachel (folgt dem Status, via `:has()`)
- [x] **„Alle wecken / Alle schlafen"** — Bulk-Wake/Bulk-Shutdown für die ganze Flotte

**Features**
- [x] **Schedule-Wecker** (Killer-Feature): Handy-Wecker-Style statt roher Cron-Syntax
  — Presets (Wochentage · täglich · Wochenende), Wochentag-Toggles, Time-Picker; Experten-Cron bleibt verfügbar
- [x] **Job-Pausetoggle** auf der Kachel — Schedule scharf/unscharf schalten ohne löschen (Default: aktiv; „pausiert"-Label, DE/EN)
- [x] **Live-Status** via ICMP / ARP / TCP + eingebauter **ARP-Netzwerk-Scanner** zum Geräte-Finden
- [x] Optionaler **Login** + optionales eingebautes **HTTPS**
- [x] **Security-Hardening**: CSRF-Tokens, Security-Header, Login-Rate-Limiting, persistenter Secret-Key, **fail-closed**
- [x] `/api/status` JSON-Endpoint → Live-Status-Kachel in Homepage / Heimdall / Homarr

**Packaging**
- [x] Eigenes **Docker-Image**: `ghcr.io/maikimolto/wol-f:latest` (~75 MB RAM, ein Container, kein Cloud/Account/Telemetry)

---

## 🔜 Geplant / Nice-to-have

- [ ] **Geräte-Typ-Badges** (SRV / NAS / PC) — optional beim Hinzufügen, nie automatisch
- [ ] **Footer-Buttons als feine Line-Icons** statt Emoji-Mix (dezent, Hover-Glow)
- [ ] Header-**Live-Übersicht** prominent oben („5 Online · 1 Offline")
- [ ] Weiterer Feinschliff: Design-Tokens, Micro-Animationen, mehr Doku

---

## 📎 Referenz: Footer-Buttons der Kachel
- 🕐 Uhr → CronJobs / Schedule konfigurieren
- ✏️ Stift → Name, IP, Statuscheck (icmp / arp / Port) bearbeiten
- 🗑️ Mülleimer → Kachel/Eintrag löschen
