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


def validate_bool(value: str):
    folded = value.strip().lower()
    if folded in ("da", "true", "yes", "1"):
        return True, "true"
    if folded in ("nu", "false", "no", "0"):
        return True, "false"
    return False, "Răspunde cu „da” sau „nu”."


def validate_openai_key(value: str):
    if re.fullmatch(r"sk-[A-Za-z0-9_-]{20,}", value):
        return True, value
    return False, (
        "Cheia OpenAI începe cu sk-... — o găsești pe platform.openai.com → API keys."
    )


def validate_model(value: str):
    if value.strip():
        return True, value.strip()
    return False, "Scrie numele modelului (ex: gpt-4o-mini)."


def validate_hours(value: str):
    if re.fullmatch(r"\d{1,2}", value) and 1 <= int(value) <= 24:
        return True, value
    return False, "Trebuie să fie un număr de ore între 1 și 24 (ex: 6)."


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

    # ── Agregatorul (opțional) ──
    existing.setdefault("USE_AI_FILTER", "false")
    values["USE_AI_FILTER"] = ask(
        "USE_AI_FILTER",
        "Filtrul AI al agregatorului (da/nu). Cu „da”, itemele agregate sunt\n"
        "  clasificate de un model OpenAI ieftin, care scrie și draftul descrierii.",
        validate_bool,
        existing,
    )
    if values["USE_AI_FILTER"] == "true":
        values["OPENAI_API_KEY"] = ask(
            "OPENAI_API_KEY",
            "Cheia API de la OpenAI (începe cu sk-...).\n"
            "  O creezi pe platform.openai.com → API keys.",
            validate_openai_key,
            existing,
        )
        existing.setdefault("AI_MODEL", "gpt-4o-mini")
        values["AI_MODEL"] = ask(
            "AI_MODEL",
            "Modelul OpenAI folosit (recomandat gpt-4o-mini — foarte ieftin).",
            validate_model,
            existing,
        )
    else:
        values["OPENAI_API_KEY"] = existing.get("OPENAI_API_KEY", "")
        values["AI_MODEL"] = existing.get("AI_MODEL", "gpt-4o-mini")
    existing.setdefault("PULL_INTERVAL_HOURS", "6")
    values["PULL_INTERVAL_HOURS"] = ask(
        "PULL_INTERVAL_HOURS",
        "La câte ore rulează automat agregatorul (recomandat: 6).",
        validate_hours,
        existing,
    )

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
