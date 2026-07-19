"""Shared helpers: load project frontmatter + closed vocabularies."""
import pathlib, yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "projects"

# Closed vocabularies (keep in sync with templates/_schema.md).
DOMAINS = {"voice-ai", "telephony", "agents-infrastructure", "ai-automation",
           "saas-platform", "devtools", "integration", "erp-automation"}
STACK = {"typescript", "python", "nodejs", "bun", "hono", "nestjs", "react", "fastapi",
         "mysql", "postgresql", "redis", "nats", "drizzle", "trpc", "websockets",
         "jambonz", "bandwidth", "ultravox", "azure-openai", "gemini", "docker",
         "anthropic", "sqlite", "business-central"}
TYPES = {"client-engagement", "own-product"}
ORGS = {"asrp", "osnova"}
ENGAGEMENTS = {"contract", "product", "internal-rnd"}
STATUSES = {"production", "pilot", "active-development", "prototype", "paused", "archived"}
TIERS = {"public", "anonymized", "nda-only"}

REQUIRED_KEYS = {"title", "slug", "type", "org", "domain", "stack", "role", "engagement",
                 "period", "status", "confidentiality", "summary", "highlights",
                 "featured", "verified_against_source", "updated"}
OPTIONAL_KEYS = {"client", "client_context", "links", "metrics",
                 "title_ru", "role_ru", "summary_ru", "highlights_ru", "track"}

# RU labels for closed-vocab enums (README bilingual rendering only; meta.yaml stays English).
STATUS_RU = {"production": "продакшн", "pilot": "пилот", "active-development": "в активной разработке",
             "prototype": "прототип", "paused": "приостановлен", "archived": "в архиве"}
TIER_RU = {"public": "публичный", "anonymized": "анонимизирован", "nda-only": "только по NDA"}
DOMAIN_RU = {"voice-ai": "голосовой ИИ", "telephony": "телефония",
             "agents-infrastructure": "инфраструктура агентов", "ai-automation": "ИИ-автоматизация",
             "saas-platform": "SaaS-платформа", "devtools": "инструменты разработки",
             "integration": "интеграция", "erp-automation": "ERP-автоматизация"}
TYPE_RU = {"client-engagement": "клиентский проект", "own-product": "собственный продукт"}

# Presentation tracks — group projects in the catalog independently of `type`.
TRACKS = {"telephony", "ai-organization"}
TRACK_ORDER = ["telephony", "ai-organization"]
TRACK_LABEL = {"telephony": "Telephony", "ai-organization": "AI-organization"}
TRACK_LABEL_RU = {"telephony": "Телефония", "ai-organization": "AI-organization"}
TRACK_DESC = {"telephony": ("Cloud-telephony platform work",
                            "Работа над платформой облачной телефонии"),
              "ai-organization": ("AI-organization platforms & products",
                                  "Платформы и продукты AI-организаций")}


def split_frontmatter(text):
    if not text.startswith("---"):
        return None, text
    end = text.find("\n---", 3)
    if end == -1:
        return None, text
    fm = text[3:end].strip()
    body = text[end + 4:]
    return yaml.safe_load(fm), body


def load_projects():
    """Return list of dicts: {meta, body, path, slug}. Sorted by (featured desc, slug).

    Frontmatter lives in a sibling ``meta.yaml`` next to ``index.md``; if that file is
    absent we fall back to a legacy inline ``---`` frontmatter block in ``index.md``.
    """
    out = []
    for idx in sorted(PROJECTS.glob("*/index.md")):
        meta_path = idx.parent / "meta.yaml"
        if meta_path.exists():
            meta, body = yaml.safe_load(meta_path.read_text()), idx.read_text()
        else:
            meta, body = split_frontmatter(idx.read_text())
        if meta is None:
            continue
        out.append({"meta": meta, "body": body, "path": idx, "slug": idx.parent.name})
    out.sort(key=lambda p: (-(p["meta"].get("featured") or 0), p["slug"]))
    return out
