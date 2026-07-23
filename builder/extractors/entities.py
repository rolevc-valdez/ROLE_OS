"""Entity extractors: people, applications, vendors, URLs, files, and
project/tag classification.

Grouped in one module because they are all "spot a known/structured thing in
the text" extractors, as opposed to the free-text extractors (summary,
decisions, todos, prompts).
"""

from __future__ import annotations

import re

from ._util import URL_RE, norm

PROJECT_RULES: dict[str, list[str]] = {
    "SUPER_FACIL": ["super facil", "súper fácil", "chatgpt super", "gemini super"],
    "ROLE_MASTER_FACTORY": ["role master factory"],
    "ROLE_CONTENT_FACTORY": ["role content factory"],
    "ROLE_MASTER": ["role master"],
    "BRAND_CHARACTER_OS": ["brand character os"],
    "ROLE_KNOWLEDGE_OS": ["role knowledge os", "role os builder", "knowledge os"],
    "ROLEVALDEZ": ["rolevaldez", "role valdez", "role rogelio", "role.rogelio"],
    "DESIERTO_CREATIVO": ["desierto creativo"],
    "CHARCOS": ["charcos", "charcos mc"],
    "BOLSA_TRABAJO": ["bolsa de trabajo", "roletrabajo"],
    "FRESHSERVICE": ["freshservice", "freshcaller", "freddy ai", "service catalog", "agent group", "change approval"],
    "DEVICE42": ["device42"],
    "JET_REPORTS": ["jet reports", "jet report"],
    "BARTENDER": ["bartender", "seagull scientific"],
    "BUSINESS_CENTRAL": ["business central", "dynamics nav", "microsoft nav", "navision"],
    "CMDB_SAM": ["cmdb", "software asset management", "sam ", "itam"],
    "POWER_BI_EXCEL": ["power bi", "excel", "dax", "power query"],
    "PERSONAL_FINANCE": ["finanzas", "deuda", "amex", "american express", "banorte", "pensión", "pension", "afore", "crédito", "credito"],
    "HOUSE": ["diseño de casa", "plano arquitectónico", "plano arquitectonico", "fachada", "recámara", "recamara"],
    "PODCAST_CONTENT": ["dando un rol", "podcast", "reel", "tiktok", "facebook post", "meta business", "contenido"],
    "AI_TOOLS": ["claude", "chatgpt", "gemini", "canva", "runway", "higgsfield", "remotion", "veo"],
    "WINDOWS_IT_SUPPORT": ["windows 11", "outlook", "file explorer", "onedrive", "teams", "vpn", "defender", "autocad", "vlc"],
    "VENDORS_APPLICATIONS": ["vendor", "application", "saas", "desktop app", "freshservice vendor"],
    "TRAVEL_LOCAL": ["tienda", "store", "paris", "praha", "magyarorszag", "douglas", "tour", "viaje"],
    "HEALTH_PERSONAL": ["salud", "médico", "medico", "síntoma", "sintoma", "gato", "perro", "nexgard"],
    "DESIGN_ASSETS": ["logo", "imagen", "flyer", "banner", "portada", "fondo transparente", "upscale", "4k"],
    "WEB_DEVELOPMENT": ["github", "vercel", "next.js", "html", "css", "javascript", "website", "sitio web"],
}

CATEGORY_FALLBACKS: list[tuple[str, list[str]]] = [
    ("IT_SUPPORT", ["error", "install", "enable", "fix", "troubleshoot", "configur", "setting"]),
    ("CONTENT", ["copy", "publicación", "publicacion", "post", "video", "imagen", "diseño"]),
    ("RESEARCH", ["busca", "investiga", "información", "informacion", "qué es", "que es", "details"]),
    ("WRITING", ["convert to text", "transcribe", "rewrite", "mejora", "definición", "definicion"]),
    ("PERSONAL", ["quiero", "ayúdame", "ayudame", "mi ", "mis "]),
]

APP_NAMES = [
    "ChatGPT", "Claude", "Claude Code", "Canva", "Freshservice", "Freshcaller", "Device42",
    "Jet Reports", "BarTender", "Business Central", "Power BI", "Excel", "Outlook", "Teams",
    "Windows 11", "Vercel", "GitHub", "Remotion", "Higgsfield", "Runway", "Gemini", "AutoCAD",
]

# Companies/vendors behind the applications and services referenced above.
# Distinct from APP_NAMES: an application can be made by a vendor (e.g. the
# "BarTender" application is made by the "Seagull Scientific" vendor), and a
# vendor can also be referenced directly (e.g. "Microsoft", "Adobe").
VENDOR_NAMES = [
    "Freshworks", "Seagull Scientific", "Microsoft", "Adobe", "Google", "Anthropic",
    "OpenAI", "Amazon", "AWS", "Jet Global", "Device42 Inc", "Canva", "Vercel Inc",
    "Meta", "Zoom", "Slack", "Atlassian",
]

FILE_RE = re.compile(
    r"\b[^\s/\\]+\.(?:png|jpe?g|webp|gif|pdf|docx?|xlsx?|pptx?|zip|json|md|py|csv|txt)\b",
    re.I,
)

PEOPLE_RE = re.compile(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,2}\b")

PEOPLE_BLOCKED = {
    "Google Drive", "Microsoft Excel", "Windows Notepad", "ChatGPT Plus", "Business Central",
}


def classify_project(title: str, body: str) -> tuple[str, list[str], str, list[str]]:
    """Classify a conversation into a primary project, secondary projects,
    a category, and base tags, using keyword-weighted rules.

    Returns (primary_project, secondary_projects, category, base_tags).
    """
    title_n, body_n = norm(title), norm(body)
    scores: list[tuple[int, str]] = []
    for project, words in PROJECT_RULES.items():
        score = 0
        for word in words:
            score += title_n.count(word) * 8
            score += body_n.count(word)
        if score:
            scores.append((score, project))
    scores.sort(reverse=True)
    if scores:
        primary = scores[0][1]
        secondary = [p for s, p in scores[1:4] if s >= max(2, scores[0][0] * 0.18)]
        category = "PROJECT"
        tags = [primary.lower().replace("_", "-")]
        return primary, secondary, category, tags

    hay = f"{title_n} {body_n[:6000]}"
    for category, words in CATEGORY_FALLBACKS:
        if any(word in hay for word in words):
            return category, [], category, [category.lower().replace("_", "-")]
    return "GENERAL", [], "GENERAL", ["general"]


def extract_people(text: str, limit: int = 12) -> list[str]:
    """Extract likely person names (heuristic: capitalized two/three-word sequences)."""
    candidates = PEOPLE_RE.findall(text)
    counts: dict[str, int] = {}
    for name in candidates:
        if name not in PEOPLE_BLOCKED and len(name) < 50:
            counts[name] = counts.get(name, 0) + 1
    return [n for n, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]]


def extract_applications(title: str, body: str) -> list[str]:
    """Return known applications mentioned in the title or body."""
    hay = f"{title}\n{body}".lower()
    return [app for app in APP_NAMES if app.lower() in hay]


def extract_vendors(title: str, body: str) -> list[str]:
    """Return known vendors/companies mentioned in the title or body."""
    hay = f"{title}\n{body}".lower()
    return [vendor for vendor in VENDOR_NAMES if vendor.lower() in hay]


def extract_urls(body: str, limit: int = 30) -> list[str]:
    """Return unique URLs referenced in the conversation body."""
    return list(dict.fromkeys(URL_RE.findall(body)))[:limit]


def extract_files(body: str, limit: int = 30) -> list[str]:
    """Return unique filenames referenced in the conversation body."""
    return list(dict.fromkeys(FILE_RE.findall(body)))[:limit]


def extract_tags(base_tags: list[str], applications: list[str], limit: int = 8) -> list[str]:
    """Merge project/category base tags with application-derived tags."""
    app_tags = [a.lower().replace(" ", "-") for a in applications[:limit]]
    return list(dict.fromkeys(base_tags + app_tags))
