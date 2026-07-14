# RADAR — bot de submisii pentru startup-uri 🇷🇴🇲🇩

Bot de Telegram (aiogram 3.x) pentru un canal care prezintă startup-uri
românești și moldovenești. Fondatorii își trimit produsul printr-un formular
pas cu pas, adminul aprobă sau respinge, iar la aprobare botul postează în
canal imaginea produsului cu descrierea și linkul în caption.

Pe lângă submisiile manuale, botul are un **agregator**: adună automat
articole despre startup-uri din presa de profil (RSS/scraping politicos),
le filtrează după relevanță (cuvinte-cheie + opțional AI), le deduplică și
le pune într-un inbox pe care adminul îl răsfoiește în privat, alegând ce
se publică. Nimic nu ajunge în canal automat.

## Structura proiectului

```
main.py             # punctul de intrare (long polling + pull automat la 6h)
handlers.py         # formularul fondatorului (FSM) + moderarea adminului
handlers_inbox.py   # comenzile agregatorului: /pull, /inbox, /inboxstats
scraper.py          # pipeline-ul agregatorului: fetch → dedup → filtru → DB
ai_filter.py        # scorul de relevanță + filtrul AI opțional (OpenAI)
sources/            # un fișier per sursă (base.py = clasa comună + HTTP politicos)
db.py               # PostgreSQL (Neon) prin asyncpg, cu reconectare
texts.py            # toate mesajele, în română, într-un singur loc
setup.py            # configurare interactivă a fișierului .env
radar-bot.service   # unit systemd pentru deploy
requirements.txt
.env.example
```

## Cerințe

- Python 3.11+
- O bază de date PostgreSQL pe [Neon](https://neon.tech) (planul gratuit e suficient)
- Un bot creat la [@BotFather](https://t.me/BotFather)
- Botul adăugat ca **administrator** în canal, cu dreptul de a publica mesaje

## Rulare locală

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python setup.py        # îți cere pe rând BOT_TOKEN, CHANNEL_ID, ADMIN_IDS, DATABASE_URL
python main.py
```

Tabelul `submissions` se creează automat la prima pornire.

## Comenzi

| Comandă | Cine | Ce face |
|---|---|---|
| `/start` | fondator | mesaj de bun venit + buton de adăugare produs |
| `/cancel` | oricine | anulează formularul/acțiunea curentă |
| `/pending` | admin | listează submisiile aflate în moderare |
| `/pull` | admin | rulează agregatorul acum, pe toate sursele |
| `/inbox` | admin | răsfoiește itemele agregate, unul pe rând, cu butoane |
| `/inboxstats` | admin | statistici pe surse și statusuri |

Anti-spam: o singură submisie per fondator la 7 zile (submisiile respinse nu
blochează — fondatorul poate corecta și retrimite).

## Agregatorul

- **Surse active** (în `sources/`): **GitHub Trending** (produse open-source:
  descriere, limbaje cu procente, stele, imagine de social preview, README
  pentru draftul AI) și **Product Hunt** (lansările zilei, RSS). Postarea are
  format „sec”: titlu – esență, ce face, ce rezolvă, limbaje, ⭐ stele, link,
  semnătura canalului (`POST_FOOTER` din .env).
- **Surse de presă RO/MD** (The Recursive, StartupCafe.ro, start-up.ro,
  Startarium, EU-Startups, Startup Moldova, NewsMaker.md, Logos-Press,
  SeedBlink): păstrate în cod, dar dezactivate — decomentează-le în
  `ACTIVE_SOURCES` dacă le vrei înapoi.
- **Politețe HTTP**: max 1 request/secundă per domeniu, robots.txt respectat,
  timeout 15s. O sursă căzută e logată și raportată în sumarul /pull, fără să
  oprească restul.
- **Deduplicare**: pe URL normalizat (fără utm_*) + similaritate de titlu
  (rapidfuzz ≥85%) pe ultimele 30 de zile; câștigă sursa cu prioritate mai
  mare, celelalte URL-uri se atașează ca „surse suplimentare”.
- **Pull automat** la fiecare `PULL_INTERVAL_HOURS` ore (APScheduler, același
  proces). La iteme noi, adminii primesc o notificare. Publicarea e mereu
  manuală, din /inbox.

### Cum adaug o sursă nouă

1. Creezi `sources/numesursa.py` cu o clasă care moștenește `RssSource`
   (setezi `name`, `display_name`, `priority`, `feed_candidates` și opțional
   `listing_url`/`listing_pattern` ca fallback) sau `Source` (implementezi
   `fetch()` manual pentru site-uri fără feed).
2. O adaugi în `ACTIVE_SOURCES` din `sources/__init__.py`. Gata.

Dezactivarea unei surse = comentezi linia ei din `ACTIVE_SOURCES`.

### Cum calibrez filtrul de relevanță

Totul e în `ai_filter.py`: listele `POSITIVE_SIGNALS`/`NEGATIVE_SIGNALS`,
ponderile și pragul `THRESHOLD` (default 1.0 — un semnal pozitiv net e
suficient). Itemele respinse apar în log cu scorul lor
(`Filtrat (scor ...)`) — urmărește logurile după câteva pull-uri și ajustează.
Cu `USE_AI_FILTER=true`, itemele care trec pragul sunt verificate și de un
model OpenAI (`AI_MODEL`, default gpt-4o-mini), care scrie și draftul
descrierii în română; la erori API filtrul e fail-open (itemul intră în inbox
cu draftul din og:description).

## Deploy pe DigitalOcean droplet (Ubuntu)

### 1. Copiază proiectul pe droplet

```bash
# de pe mașina ta (sau clonează din git direct pe droplet):
scp -r radar_project root@IP_DROPLET:/opt/radar-bot
```

### 2. Creează utilizatorul, venv-ul și instalează dependențele

```bash
ssh root@IP_DROPLET
apt update && apt install -y python3-venv
adduser --system --group --home /opt/radar-bot radar
cd /opt/radar-bot
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

### 3. Configurează variabilele de mediu

```bash
.venv/bin/python setup.py
chown -R radar:radar /opt/radar-bot
```

### 4. Instalează serviciul systemd

Fișierul `radar-bot.service` e gata scris în proiect (pornește automat la
reboot și repornește singur dacă botul pică):

```ini
[Unit]
Description=RADAR Telegram bot (submisii startup-uri RO/MD)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=radar
WorkingDirectory=/opt/radar-bot
ExecStart=/opt/radar-bot/.venv/bin/python main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
cp /opt/radar-bot/radar-bot.service /etc/systemd/system/radar-bot.service
systemctl daemon-reload
systemctl enable radar-bot
systemctl start radar-bot
systemctl status radar-bot
```

### 5. Loguri

```bash
journalctl -u radar-bot -f          # urmărește logurile live
journalctl -u radar-bot -n 100      # ultimele 100 de linii
journalctl -u radar-bot --since today
```

### Actualizare cod

```bash
# după ce copiezi/tragi noul cod în /opt/radar-bot:
systemctl restart radar-bot
```

## Note operaționale

- **Neon + SSL**: connection string-ul trebuie să conțină `?sslmode=require`
  — `setup.py` îl adaugă automat dacă lipsește. Dacă instanța Neon e
  suspendată (idle), botul reîncearcă automat conexiunea.
- **Botul scos din adminii canalului**: botul loghează eroarea și îi anunță
  pe admini în privat; submisia rămâne în moderare și poate fi aprobată din
  nou după ce botul redevine admin.
- **Adminii trebuie să dea /start botului** o singură dată, altfel Telegram
  nu-i lasă pe boți să le scrie primii.
