from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Iterable

URL_RE = re.compile(r"https?://[^\s)\]}>\"']+")

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
    ("CONTENT", ["copy", "publicación", "publicacion", "post", "video", "imagen", "diseño", "diseño"]),
    ("RESEARCH", ["busca", "investiga", "información", "informacion", "qué es", "que es", "details"]),
    ("WRITING", ["convert to text", "transcribe", "rewrite", "mejora", "definición", "definicion"]),
    ("PERSONAL", ["quiero", "ayúdame", "ayudame", "mi ", "mis "])
]

APP_NAMES = [
    "ChatGPT", "Claude", "Claude Code", "Canva", "Freshservice", "Freshcaller", "Device42",
    "Jet Reports", "BarTender", "Business Central", "Power BI", "Excel", "Outlook", "Teams",
    "Windows 11", "Vercel", "GitHub", "Remotion", "Higgsfield", "Runway", "Gemini", "AutoCAD",
]

@dataclass
class KnowledgeCard:
    conversation_id: str
    date: str
    updated: str
    title: str
    project: str
    secondary_projects: list[str] = field(default_factory=list)
    category: str = "GENERAL"
    summary: str = ""
    status: str = "Unknown"
    decisions: list[str] = field(default_factory=list)
    deliverables: list[str] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    people: list[str] = field(default_factory=list)
    applications: list[str] = field(default_factory=list)
    vendors: list[str] = field(default_factory=list)
    urls: list[str] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def _dt(value) -> str:
    if not value:
        return ""
    try:
        return datetime.fromtimestamp(float(value), tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return ""


def classify(title: str, body: str) -> tuple[str, list[str], str, list[str]]:
    title_n, body_n = _norm(title), _norm(body)
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


def _sentences(text: str) -> list[str]:
    lines = [re.sub(r"^[\-*•\d.\s]+", "", x).strip() for x in text.splitlines()]
    return [x for x in lines if 10 <= len(x) <= 500]


def _pick(lines: Iterable[str], patterns: Iterable[str], limit: int = 8) -> list[str]:
    rx = re.compile("|".join(patterns), re.I)
    out: list[str] = []
    for line in lines:
        if rx.search(line) and line not in out:
            out.append(line)
            if len(out) >= limit:
                break
    return out


def _extract_people(text: str) -> list[str]:
    candidates = re.findall(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){1,2}\b", text)
    blocked = {"Google Drive", "Microsoft Excel", "Windows Notepad", "ChatGPT Plus", "Business Central"}
    counts: dict[str, int] = {}
    for name in candidates:
        if name not in blocked and len(name) < 50:
            counts[name] = counts.get(name, 0) + 1
    return [n for n, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:12]]


def _status(text: str) -> str:
    low = text.lower()
    if any(x in low for x in ["completado", "terminado", "listo", "aprobado", "resolved", "fixed"]):
        return "Completed"
    if any(x in low for x in ["en progreso", "trabajando", "in progress", "pendiente", "falta", "todo"]):
        return "In Progress"
    return "Unknown"


def build_card(conversation: dict, messages: list[tuple[str, str]]) -> KnowledgeCard:
    title = conversation.get("title") or "Untitled"
    body = "\n".join(text for _, text in messages)
    primary, secondary, category, tags = classify(title, body)
    lines = _sentences(body)
    user_prompts = [text.strip() for role, text in messages if role == "user" and text.strip()]
    applications = [app for app in APP_NAMES if app.lower() in body.lower() or app.lower() in title.lower()]
    urls = list(dict.fromkeys(URL_RE.findall(body)))[:30]
    assets = list(dict.fromkeys(re.findall(r"\b[^\s/\\]+\.(?:png|jpe?g|webp|gif|pdf|docx?|xlsx?|pptx?|zip|json|md|py)\b", body, re.I)))[:30]
    summary_source = next((x for x in user_prompts if len(x) >= 30), title)
    summary = re.sub(r"\s+", " ", summary_source)[:500]

    return KnowledgeCard(
        conversation_id=str(conversation.get("id") or conversation.get("conversation_id") or ""),
        date=_dt(conversation.get("create_time")),
        updated=_dt(conversation.get("update_time")),
        title=title,
        project=primary,
        secondary_projects=secondary,
        category=category,
        summary=summary,
        status=_status(body),
        decisions=_pick(lines, [r"\bdecid", r"\baprob", r"quedamos", r"vamos a usar", r"se define", r"final"], 10),
        deliverables=_pick(lines, [r"entregable", r"archivo final", r"listo para", r"generad", r"cread", r"completad"], 10),
        todos=_pick(lines, [r"\bpendiente", r"\bfalta", r"\bto-?do\b", r"siguiente", r"después", r"despues"], 10),
        people=_extract_people(body),
        applications=applications,
        vendors=[],
        urls=urls,
        prompts=user_prompts[:25],
        assets=assets,
        tags=list(dict.fromkeys(tags + [a.lower().replace(" ", "-") for a in applications[:8]])),
    )
