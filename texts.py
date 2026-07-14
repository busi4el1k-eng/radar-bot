"""Toate mesajele botului, în română, într-un singur loc.

Mesajele sunt trimise cu parse_mode=HTML, deci conținutul introdus de
utilizatori trebuie escapat (html.escape) înainte de a fi inserat în șabloane.
"""

# ── Fluxul fondatorului ──────────────────────────────────────────────────────

WELCOME = (
    "Salut! 👋\n\n"
    "Aici îți poți prezenta produsul comunității de startup-uri "
    "românești și moldovenești. 🇷🇴🇲🇩\n\n"
    "Apasă butonul de mai jos și completează formularul pas cu pas — "
    "durează un minut. 🚀"
)

BTN_ADD = "🚀 Adaugă produsul tău"

COOLDOWN = (
    "Ai trimis deja un produs recent. 🙌\n\n"
    "Pentru a păstra calitatea canalului, acceptăm o singură submisie "
    "per fondator la 7 zile. Mai încearcă peste aproximativ {days} zi(le)."
)

ASK_PHOTO = (
    "<b>Pasul 1/5 — Imaginea produsului</b> 📸\n\n"
    "Trimite logo-ul sau un screenshot al produsului. "
    "Imaginea e elementul central al postării, așa că alege una clară.\n\n"
    "<i>Trimite-o ca poză (nu ca fișier). Poți anula oricând cu /cancel.</i>"
)

ERR_NOT_PHOTO = (
    "Am nevoie de o poză aici. 🖼️\n\n"
    "Trimite imaginea ca <b>poză</b> (nu ca fișier/document, nu text). "
    "Dacă vrei să renunți, scrie /cancel."
)

ASK_NAME = (
    "Super, imaginea arată bine! ✅\n\n"
    "<b>Pasul 2/5 — Numele produsului</b>\n\n"
    "Cum se numește produsul tău? (maximum 50 de caractere)"
)

ERR_NAME_TOO_LONG = (
    "Numele are {n} caractere, dar maximul e 50. "
    "Încearcă o variantă mai scurtă. ✂️"
)

ASK_DESCRIPTION = (
    "<b>Pasul 3/5 — Descrierea</b> ✍️\n\n"
    "Descrie pe scurt produsul: ce face și pentru cine e. "
    "(maximum 300 de caractere)"
)

ERR_DESC_TOO_LONG = (
    "Descrierea are {n} caractere, dar maximul e 300. "
    "Scurteaz-o puțin — cele mai bune pitch-uri sunt concise. ✂️"
)

ASK_LINK = (
    "<b>Pasul 4/5 — Linkul</b> 🔗\n\n"
    "Trimite linkul către produs (site, pagină de download, App Store etc.)."
)

ERR_BAD_LINK = (
    "Hmm, nu pare un link valid. 🤔\n\n"
    "Trimite un URL de forma <code>https://exemplu.ro</code> "
    "sau <code>exemplu.ro</code>."
)

ASK_CONTACT_WITH_DEFAULT = (
    "<b>Pasul 5/5 — Contactul</b> 💬\n\n"
    "Ce username de Telegram afișăm pentru cei care vor să te contacteze?\n\n"
    "Apasă butonul de mai jos ca să folosești <b>{username}</b> "
    "sau scrie alt username."
)

ASK_CONTACT = (
    "<b>Pasul 5/5 — Contactul</b> 💬\n\n"
    "Scrie username-ul de Telegram pe care îl afișăm pentru cei care vor "
    "să te contacteze (ex: <code>@exemplu</code>)."
)

ERR_BAD_CONTACT = (
    "Nu pare un username de Telegram valid. 🤔\n\n"
    "Trimite ceva de forma <code>@exemplu_123</code> "
    "(5–32 de caractere: litere, cifre, underscore)."
)

ERR_EXPECTED_TEXT = "Aici am nevoie de un mesaj text. 📝 Sau scrie /cancel ca să renunți."

PREVIEW_INTRO = "Așa va arăta postarea ta în canal: 👇"

BTN_SUBMIT = "✅ Trimite"
BTN_CANCEL = "❌ Anulează"

SUBMITTED = (
    "Mulțumim! 🙏 Produsul tău e în moderare.\n\n"
    "Te anunțăm aici imediat ce e aprobat și publicat în canal."
)

CANCELLED = "Am anulat. 👌 Când ești gata, pornește din nou cu /start."

NOTHING_TO_CANCEL = "Nu e nimic de anulat acum. 🙂 Pornește cu /start."

FALLBACK = "Nu am înțeles. 🙂 Scrie /start ca să adaugi produsul tău."

USER_APPROVED = (
    "Vești bune! 🎉 Produsul tău a fost aprobat și publicat în canal:\n\n{url}"
)

USER_APPROVED_NO_LINK = (
    "Vești bune! 🎉 Produsul tău a fost aprobat și publicat în canal."
)

USER_REJECTED = (
    "Din păcate, submisia ta nu a fost aprobată de această dată. 😔\n\n"
    "<b>Motiv:</b> {reason}\n\n"
    "Poți corecta și trimite din nou cu /start."
)

# ── Formatul postării în canal ───────────────────────────────────────────────

POST_TEMPLATE = (
    "🚀 <b>{name}</b>\n"
    "\n"
    "{description}\n"
    "\n"
    "🔗 {link}\n"
    "💬 Fondator: {contact}"
)

# ── Fluxul adminului ─────────────────────────────────────────────────────────

ADMIN_NEW_HEADER = "📥 <b>Submisie nouă #{sub_id}</b> de la {sender}\n\n"

BTN_APPROVE = "✅ Aprobă"
BTN_REJECT = "❌ Respinge"

ADMIN_ALREADY_PROCESSED = "Submisia asta a fost deja procesată."

ADMIN_ASK_REASON = (
    "Scrie pe scurt motivul respingerii pentru „{name}” — "
    "îl trimit automat fondatorului. (sau /cancel ca să renunți)"
)

ADMIN_APPROVED_OK = "✅ Submisia #{sub_id} a fost publicată în canal, iar fondatorul a fost anunțat."

ADMIN_REJECTED_OK = "❌ Submisia a fost respinsă, iar fondatorul a primit motivul."

ADMIN_CHANNEL_ERROR = (
    "⚠️ Nu am putut posta în canal. Verifică dacă botul este membru și "
    "administrator al canalului, cu dreptul de a publica mesaje.\n\n"
    "Submisia rămâne în moderare — poți încerca din nou după ce rezolvi.\n\n"
    "Eroare: {error}"
)

ADMIN_BOT_REMOVED = (
    "🚨 Atenție: botul nu mai are drepturi de administrator în canal! "
    "Nu voi putea publica submisii aprobate până nu îl adaugi înapoi ca admin."
)

PENDING_EMPTY = "Nicio submisie în moderare. 🎉"

PENDING_HEADER = "🗂 Submisii în moderare: {count}. Ți le trimit pe rând: 👇"

# ── Agregatorul (inbox) ──────────────────────────────────────────────────────

PULL_STARTED = "📡 Rulez agregatorul pe toate sursele... poate dura 1-2 minute."

PULL_ALREADY_RUNNING = "⏳ Un pull rulează deja — așteaptă să se termine."

PULL_SUMMARY = (
    "📡 Gata! Am găsit <b>{new}</b> iteme noi "
    "({filtered} filtrate ca irelevante, {duplicates} duplicate).\n"
    "{per_source}"
    "Vezi-le cu /inbox"
)

PULL_ERROR_LINE = "⚠️ Sursa {source} a eșuat: {error}"

SCRAPE_NOTIFY = "📡 {n} startup-uri noi în inbox — /inbox"

INBOX_EMPTY = "Inboxul e gol. 🎉 Rulează /pull sau așteaptă următorul pull automat."

INBOX_HEADER = "📥 {count} iteme în inbox. Primul: 👇"

INBOX_META_LINE = "📡 {source} • {date} • scor {score}"

INBOX_NO_IMAGE_TAG = (
    "🖼 <i>Fără imagine proprie — se publică cu preview-ul linkului "
    "(sau atașează o poză cu 🖼).</i>\n\n"
)

BTN_INBOX_PUBLISH = "📤 Publică"
BTN_INBOX_EDIT = "✏️ Editează descrierea"
BTN_INBOX_PHOTO = "🖼 Schimbă poza"
BTN_INBOX_IGNORE = "🗑 Ignoră"
BTN_INBOX_NEXT = "⏭ Următorul"

INBOX_ALREADY_PROCESSED = "Itemul ăsta a fost deja procesat."

INBOX_PUBLISHED = "✅ Publicat în canal: {url}"

INBOX_PUBLISHED_NO_LINK = "✅ Publicat în canal."

INBOX_IGNORED = "🗑 Ignorat — nu-ți mai apare."

INBOX_ASK_DESCRIPTION = (
    "Trimite noua descriere pentru „{title}” (max 600 de caractere; "
    "paragrafe separate prin linie goală). Sau /cancel ca să renunți."
)

INBOX_DESC_TOO_LONG = "Descrierea are {n} caractere, maximul e 600. Mai scurt. ✂️"

INBOX_ASK_PHOTO = (
    "Trimite poza pe care o folosim pentru „{title}” (ca poză, nu ca fișier). "
    "Sau /cancel ca să renunți."
)

INBOX_NOT_A_PHOTO = "Am nevoie de o poză. 🖼 Sau /cancel ca să renunți."

INBOX_UPDATED = "Am actualizat. Uite cardul: 👇"

INBOX_STATS_HEADER = "📊 <b>Statistici inbox</b>\n"

INBOX_STATS_EMPTY = "Încă nu există iteme agregate. Rulează /pull."
