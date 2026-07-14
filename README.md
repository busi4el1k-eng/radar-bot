# RADAR — bot de submisii pentru startup-uri 🇷🇴🇲🇩

Bot de Telegram (aiogram 3.x) pentru un canal care prezintă startup-uri
românești și moldovenești. Fondatorii își trimit produsul printr-un formular
pas cu pas, adminul aprobă sau respinge, iar la aprobare botul postează în
canal imaginea produsului cu descrierea și linkul în caption.

## Structura proiectului

```
main.py            # punctul de intrare (long polling)
handlers.py        # formularul fondatorului (FSM) + moderarea adminului
db.py              # PostgreSQL (Neon) prin asyncpg, cu reconectare
texts.py           # toate mesajele, în română, într-un singur loc
setup.py           # configurare interactivă a fișierului .env
radar-bot.service  # unit systemd pentru deploy
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

Anti-spam: o singură submisie per fondator la 7 zile (submisiile respinse nu
blochează — fondatorul poate corecta și retrimite).

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
