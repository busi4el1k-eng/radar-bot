#!/usr/bin/env python3
"""Configurare interactivă: îți cere pe rând fiecare variabilă și scrie .env.

Rulează: python setup.py
Dacă .env există deja, valorile curente sunt oferite ca implicite (apasă Enter
ca să le păstrezi).
"""

import re
import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent / ".env"


def load_existing() -> dict[str, str]:
    values: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                values[key.strip()] = value.strip()
    return values


def validate_token(value: str):
    if re.fullmatch(r"\d{6,12}:[A-Za-z0-9_-]{30,}", value):
        return True, value
    return False, (
        "Nu pare un token valid de bot. Are forma 123456789:AAF...xyz "
        "— îl primești de la @BotFather cu comanda /newbot."
    )


def validate_channel(value: str):
    if re.fullmatch(r"-100\d{5,}", value) or re.fullmatch(r"@[A-Za-z0-9_]{4,32}", value):
        return True, value
    if re.fullmatch(r"\d+", value):
        return False, (
            "ID-ul unui canal începe cu -100 (ex: -1001234567890). "
            "Verifică din nou cu @userinfobot."
        )
    return False, (
        "Format acceptat: -1001234567890 sau @numecanal. "
        "Redirecționează un mesaj din canal către @userinfobot ca să afli ID-ul."
    )


def validate_admins(value: str):
    parts = [p.strip() for p in value.split(",") if p.strip()]
    if parts and all(re.fullmatch(r"\d{5,15}", p) for p in parts):
        return True, ",".join(parts)
    return False, (
        "Trebuie să fie unul sau mai multe ID-uri numerice, separate prin "
        "virgulă (ex: 123456789 sau 123456789,987654321). "
        "Îți afli ID-ul scriindu-i lui @userinfobot."
    )


def validate_database_url(value: str):
    if not value.startswith(("postgresql://", "postgres://")):
        return False, (
            "Connection string-ul trebuie să înceapă cu postgresql:// — "
            "îl copiezi din dashboard-ul Neon (Connection Details)."
        )
    if "sslmode=" not in value:
        separator = "&" if "?" in value else "?"
        value = f"{value}{separator}sslmode=require"
        print("ℹ️  Am adăugat sslmode=require la URL (Neon cere conexiune SSL).")
    return True, value


STEPS = [
    (
        "BOT_TOKEN",
        "Token-ul botului de la @BotFather.\n"
        "  Deschide @BotFather în Telegram → /newbot (sau /token pentru un bot existent).",
        validate_token,
    ),
    (
        "CHANNEL_ID",
        "ID-ul canalului (ex: -1001234567890). Cum îl afli: redirecționează un mesaj\n"
        "  din canal către @userinfobot. Merge și formatul @numecanal (canal public).",
        validate_channel,
    ),
    (
        "ADMIN_IDS",
        "ID-ul tău de Telegram (poți pune mai multe, separate prin virgulă).\n"
        "  Îl afli de la @userinfobot — scrie-i orice mesaj și îți răspunde cu ID-ul.",
        validate_admins,
    ),
    (
        "DATABASE_URL",
        "Connection string-ul de la Neon (începe cu postgresql://...).\n"
        "  Îl găsești în dashboard-ul Neon → proiectul tău → Connection Details.",
        validate_database_url,
    ),
]


def ask(name: str, explanation: str, validator, existing: dict[str, str]) -> str:
    print(f"\n─── {name} " + "─" * max(1, 60 - len(name)))
    print(f"  {explanation}")
    default = existing.get(name, "")
    while True:
        if default:
            shown = default if len(default) <= 60 else default[:57] + "..."
            print(f"  Valoare existentă: {shown}")
            raw = input(f"{name} [Enter = păstrează]: ").strip()
            if not raw:
                raw = default
        else:
            raw = input(f"{name}: ").strip()
        ok, result = validator(raw)
        if ok:
            print("  ✅ OK")
            return result
        print(f"  ❌ {result}")


def main() -> None:
    print("🛠  Configurarea botului RADAR — hai să setăm variabilele de mediu.")
    existing = load_existing()
    if existing:
        print("(am găsit un .env existent — apasă Enter ca să păstrezi valorile curente)")

    values = {name: ask(name, explanation, validator, existing)
              for name, explanation, validator in STEPS}

    ENV_PATH.write_text(
        "".join(f"{key}={value}\n" for key, value in values.items()),
        encoding="utf-8",
    )
    try:
        ENV_PATH.chmod(0o600)
    except OSError:
        pass

    print(f"\n📄 Am scris {ENV_PATH}")
    print("✅ Configurare completă. Pornește botul cu: python main.py")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nConfigurare anulată. Poți relua oricând cu: python setup.py")
        sys.exit(1)
