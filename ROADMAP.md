# WOL-F — Roadmap

**WOL-F** = **W**ake **O**n **L**an **F**leet
Eigenständiges, modernes Wake-/Sleep-on-LAN Dashboard fürs Homelab.

- **Herausgeber:** Maik & Nex
- **Basis:** Fork von [gptwol](https://github.com/Misterbabou/gptwol) (Misterbabou)
- **Lizenz:** MIT (Original-Copyright + NOTICE für Misterbabou bleibt erhalten)

---

## ✅ Erledigt (v1.0)
- **Smart On/Off-Switch** — iOS-Toggle ersetzt Power-Button. Grün=ON, Rot=OFF, Gelb=Pending. 5s-Poll im Pending, 4-Min-Timeout.
- **Farbiger Status-Streifen** links an der Kachel (folgt dem Status, via `:has()`).
- Live getestet auf .6:5000, gesichert (Tag `smart-switch-v1.0`).

## 🛠️ Reihenfolge

### 1. Identität  ✅ (Logo)
- [x] Logo: freigestellter Wolf + WOL-F-Wortmarke + Tagline → `wol-f-logo.html` / `wol-f-logo-final.png`
- [ ] Repo-Rebranding auf WOL-F (Name, README, NOTICE für Misterbabou, Herausgeber Maik & Nex)

### 2. Design-Fundament  ✅ Mockup abgenommen (`wol-f-app-mockup-v2.html` / v2d-Render) — jetzt Einbau in Fork (Branch `feature/wol-f-redesign`)
- [ ] Dark-Mode als Default
- [ ] Header mit Logo + **Live-Übersicht** („5 Online · 1 Offline“)  ✅ Konzept bestätigt
- [ ] **„Alle wecken / Alle schlafen“-Button** neben der Übersicht (Bulk, mit Sicherheitsabfrage)  ← NEU
- [ ] **DE/EN-Sprachumschalter** oben in der Leiste  ← NEU
- [ ] **Footer-Buttons neu**: einheitliche feine Line-Icons statt Emoji-Mix (dezent, Hover-Glow)  ← NEU
- [ ] Geräte-Typ-Badges (SRV / NAS / PC) — **optional beim Hinzufügen**, nie automatisch  ← präzisiert
- [ ] Farb-/Design-Tokens, mehr Luft, weichere Schatten, Micro-Animationen

### 3. Features
- [ ] **Schedule-Wecker** (Killer-Feature): Handy-Wecker-Style statt roher Cron-Syntax
  - Zeiten in 5-Min-Schritten (z.B. 17:35)
  - Wochentage anklickbar; pro Tag(esgruppe) eigene Wake/Sleep-Zeiten
  - **Label auf der Kachel zeigt Wochentage + Zeit** (z.B. „Mo–Fr · 08:50 / 23:30“)  ← NEU
  - **Mehrere Schedule-Blöcke pro Gerät** müssen auf der Kachel sauber/kompakt gestapelt aussehen (nicht überladen)  ← NEU (Maik 21.06.)
- [ ] **Job-Pausetoggle** auf der Kachel (Default OFF, kleiner als Hauptschalter ✅): Schedule scharf/unscharf ohne löschen

### 4. Feinschliff
- [ ] Politur, Doku, eigenes Docker-Image

---

## 📎 Referenz: Footer-Buttons der Kachel (Bestand)
- 🕐 Uhr → CronJobs konfigurieren
- ✏️ Stift → Name, IP, Statuscheck (icmp / arp / Port) bearbeiten
- 🗑️ Mülleimer → Kachel/Eintrag löschen
