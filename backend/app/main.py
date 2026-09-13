import json
import logging
import math
from contextlib import asynccontextmanager
from html import escape
from urllib.parse import urlsplit
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import PlainTextResponse, Response, RedirectResponse, JSONResponse
from . import contact, storage
from .storage import DATA_DIR, OPTIMIZED_DIR, MANIFEST_PATH, ARTICLES_PATH
from .translations import I18N
from .security import COOKIE, TOKEN_TTL, make_token, valid_token, verify_csrf, limiter, RequestSizeLimit, BodyTooLarge


@asynccontextmanager
async def lifespan(app):
    storage.initialize()
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(RequestSizeLimit)
logger = logging.getLogger(__name__)


@app.exception_handler(storage.StorageError)
async def storage_failure(request, exc):
    return PlainTextResponse("Content temporarily unavailable. Please try again later.", status_code=503)


@app.exception_handler(BodyTooLarge)
async def body_too_large(request, exc):
    return PlainTextResponse("Request too large", status_code=413)


@app.middleware("http")
async def browser_security(request: Request, call_next):
    if request.url.path in {"/static/sitemap.xml", "/static/robots.txt"}:
        return RedirectResponse("/" + request.url.path.rsplit("/", 1)[1], status_code=308)
    token = request.cookies.get(COOKIE, "")
    if not valid_token(token):
        token = make_token()
    request.state.csrf_token = token
    request.state.csp_nonce = secrets.token_urlsafe(24)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if "text/html" in response.headers.get("content-type", ""):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: https:; "
            "style-src 'self' 'unsafe-inline'; font-src 'self' data:; "
            f"script-src 'self' 'nonce-{request.state.csp_nonce}'; "
            "connect-src 'self'; form-action 'self'; base-uri 'none'; "
            "object-src 'none'; frame-ancestors 'self'"
        )
    if request.url.path.startswith('/admin') or request.url.path == '/kontakt':
        response.headers['Cache-Control'] = 'no-store'
        if request.method == 'GET':
            response.set_cookie(COOKIE, token, max_age=TOKEN_TTL, httponly=True,
                                secure=request.url.scheme == 'https', samesite='strict', path='/')
    return response


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
GALLERY_DIR = STATIC_DIR / "gallery"

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads/optimized", StaticFiles(directory=str(OPTIMIZED_DIR), check_dir=False), name="uploads")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

CLINIC_NAME = os.getenv("CLINIC_NAME", "ZAHNARZTPRAXIS – M.Sc. Abdulaziz Jaghsi")
ADDRESS = os.getenv("CLINIC_ADDRESS", "Karl-Marx-Straße 214, 12055 Berlin")
PHONE_LANDLINE = os.getenv("CLINIC_PHONE_LANDLINE", "(030) 685 10 44")
PHONE_MOBILE = os.getenv("CLINIC_PHONE_MOBILE", "015560 555345")
PHONE_TEL = os.getenv("CLINIC_PHONE_TEL", "+49306851044")
OPENING_HOURS_DE = os.getenv("CLINIC_HOURS_DE", "Mo, Di, Do: 09:00–18:00; Mi, Fr: 09:00–15:00")
OPENING_HOURS_AR = os.getenv("CLINIC_HOURS_AR", "الاثنين والثلاثاء والخميس: 09:00–18:00؛ الأربعاء والجمعة: 09:00–15:00")

ADMIN_USER = os.getenv("ADMIN_UPLOAD_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_UPLOAD_PASSWORD", "")
MAX_UPLOAD_MB = min(10, max(1, int(os.getenv("MAX_UPLOAD_MB", "10"))))
MAX_UPLOAD_FILES = 8
MAX_BATCH_BYTES = 30 * 1024 * 1024
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

SUPPORTED_LANGS = {"de", "ar"}
DEFAULT_LANG = "de"
SITE_URL = (os.getenv("SITE_URL") or "https://zahnarzt-jaghsi.de").rstrip("/")

SEO_META = {
    "de": {
        "home": "Moderne Zahnarztpraxis in Berlin-Neukoelln mit Schwerpunkt Prothetik und Implantatprothetik. Termin online oder telefonisch buchen.",
        "services": "Leistungen der Zahnarztpraxis: Prothetik, Implantatprothetik, Prophylaxe, aesthetische Zahnheilkunde und konservierende Behandlungen.",
        "about": "Lernen Sie M.Sc. Abdulaziz Jaghsi und die Zahnarztpraxis in Berlin-Neukoelln kennen: moderne Behandlung, klare Beratung und mehrsprachige Betreuung.",
        "contact": "Kontakt zur Zahnarztpraxis in Berlin-Neukoelln. Adresse, Telefon, Online-Termin und Anfahrt auf einen Blick.",
        "articles": "Ratgeber und Fachartikel der Zahnarztpraxis zu Implantaten, Prothetik, Prophylaxe und moderner Zahnmedizin in Berlin-Neukoelln.",
    },
    "ar": {
        "home": "عيادة اسنان حديثة في برلين نيوكولن متخصصة في التركيبات وتعويضات الزرعات مع حجز موعد سريع اونلاين او هاتفيا.",
        "services": "خدمات العيادة تشمل التركيبات السنية وتعويضات الزرعات والوقاية والعلاج التجميلي وعلاجات الاسنان المحافظة.",
        "about": "تعرف على عيادة الدكتور عبد العزيز جغصي في برلين نيوكولن ونهجنا العلاجي الحديث والاستشارة الواضحة بلغات متعددة.",
        "contact": "تواصل مع عيادة الاسنان في برلين نيوكولن: العنوان ووسائل الاتصال وحجز المواعيد وخريطة الوصول.",
        "articles": "مقالات ونصائح عيادة الاسنان حول الزرعات والتركيبات والوقاية والعناية اليومية بالاسنان.",
    },
}

security = HTTPBasic()



GALLERY_SLOTS = [
    {"key": "reception", "src": "/static/gallery/praxis-empfang.svg", "label_key": "gallery_i1"},
    {"key": "treatment", "src": "/static/gallery/behandlung-raum.svg", "label_key": "gallery_i2"},
    {"key": "team", "src": "/static/gallery/team-beratung.svg", "label_key": "gallery_i3"},
    {"key": "digital", "src": "/static/gallery/technik-digital.svg", "label_key": "gallery_i4"},
    {"key": "prophylaxis", "src": "/static/gallery/prophylaxe.svg", "label_key": "gallery_i5"},
    {"key": "waiting", "src": "/static/gallery/wartebereich.svg", "label_key": "gallery_i6"},
]

SLOT_KEYS = {slot["key"] for slot in GALLERY_SLOTS}

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
TARGET_SIZES = [320, 480, 800, 1200, 1600]


def get_lang(request: Request) -> str:
    lang = request.query_params.get("lang", DEFAULT_LANG).lower()
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


def sanitize_stem(name: str) -> str:
    stem = Path(name).stem.lower()
    stem = re.sub(r"[^a-z0-9_-]+", "-", stem).strip("-")
    return stem or f"image-{int(time.time())}"


def _to_image_item(raw: dict, section: str) -> dict:
    image_id = raw.get("id") or raw.get("image_id") or f"{section}-{uuid.uuid4().hex[:10]}"
    return {
        "id": image_id,
        "section": section,
        "title_de": raw.get("title_de", ""),
        "title_ar": raw.get("title_ar", ""),
        "full_url": raw.get("full_url", ""),
        "thumb_url": raw.get("thumb_url", raw.get("full_url", "")),
        "srcset": raw.get("srcset", ""),
        "created_at": raw.get("created_at", int(time.time())),
    }


def load_manifest() -> dict[str, dict]:
    raw = storage.read_json(MANIFEST_PATH, {})

    if isinstance(raw, list):
        migrated: dict[str, dict] = {}
        for idx, item in enumerate(raw):
            if idx >= len(GALLERY_SLOTS):
                break
            section = GALLERY_SLOTS[idx]["key"]
            image_item = _to_image_item(item, section)
            migrated[section] = {"main_image_id": image_item["id"], "images": [image_item]}
        return migrated

    if not isinstance(raw, dict):
        raise storage.StorageError("Invalid gallery store")

    normalized: dict[str, dict] = {}
    for section, value in raw.items():
        if section not in SLOT_KEYS:
            continue

        if isinstance(value, dict) and isinstance(value.get("images"), list):
            images = [_to_image_item(img, section) for img in value.get("images", []) if isinstance(img, dict)]
            main_image_id = value.get("main_image_id")
            if images and not any(img["id"] == main_image_id for img in images):
                main_image_id = images[0]["id"]
            normalized[section] = {"main_image_id": main_image_id, "images": images}
        elif isinstance(value, dict):
            image_item = _to_image_item(value, section)
            normalized[section] = {"main_image_id": image_item["id"], "images": [image_item]}

    return normalized


def save_manifest(items: dict[str, dict]) -> None:
    storage.write_json(MANIFEST_PATH, items)


def get_gallery_slots(lang: str) -> list[dict]:
    return [{"key": slot["key"], "label": I18N[lang][slot["label_key"]]} for slot in GALLERY_SLOTS]


def _versioned_url(url: str, version: int | None = None) -> str:
    if not url:
        return url
    if version is None:
        version = int(time.time())
    sep = '&' if '?' in url else '?'
    return f"{url}{sep}v={version}"


def _versioned_srcset(srcset: str, version: int | None = None) -> str:
    if not srcset:
        return srcset
    parts = []
    for raw in srcset.split(','):
        item = raw.strip()
        if not item:
            continue
        segs = item.split()
        if not segs:
            continue
        url = _versioned_url(segs[0], version)
        if len(segs) > 1:
            parts.append(f"{url} {segs[1]}")
        else:
            parts.append(url)
    return ', '.join(parts)


def _get_main_image(section_data: dict | None) -> dict | None:
    if not section_data:
        return None
    images = section_data.get("images", [])
    if not images:
        return None
    main_id = section_data.get("main_image_id")
    for img in images:
        if img.get("id") == main_id:
            return img
    return images[0]


def _existing_image_url(url: str) -> bool:
    if not isinstance(url, str) or not url.startswith('/uploads/optimized/'):
        return False
    name = urlsplit(url).path.removeprefix('/uploads/optimized/')
    if not name or Path(name).name != name:
        return False
    path = OPTIMIZED_DIR / name
    return not path.is_symlink() and path.is_file()


def _available_image(item: dict, fallback: str) -> dict:
    result = dict(item)
    variants = []
    for part in item.get('srcset', '').split(','):
        fields = part.strip().split()
        if len(fields) == 2 and re.fullmatch(r'[1-9][0-9]*w', fields[1]) and _existing_image_url(fields[0]):
            variants.append((int(fields[1][:-1]), fields[0]))
    variants.sort()
    available = [url for url in (item.get('full_url', ''), item.get('thumb_url', '')) if _existing_image_url(url)]
    available.extend(url for _, url in reversed(variants))
    if not available:
        result.update(full_url=fallback, thumb_url=fallback, srcset='', file_missing=True)
    else:
        result['full_url'] = item.get('full_url') if _existing_image_url(item.get('full_url')) else available[0]
        result['thumb_url'] = item.get('thumb_url') if _existing_image_url(item.get('thumb_url')) else (variants[0][1] if variants else available[0])
        result['srcset'] = ', '.join(f'{url} {width}w' for width, url in variants)
        result['file_missing'] = False
    return result


def load_gallery_images(lang: str) -> list[dict]:
    manifest = load_manifest()
    result = []
    for slot in GALLERY_SLOTS:
        key = slot["key"]
        section_data = manifest.get(key)
        main_image = _get_main_image(section_data)
        if main_image:
            main_image = _available_image(main_image, slot["src"])
            result.append(
                {
                    "slot": key,
                    "src": _versioned_url(main_image.get("thumb_url", main_image.get("full_url", slot["src"])), main_image.get("created_at")),
                    "full": _versioned_url(main_image.get("full_url", slot["src"]), main_image.get("created_at")),
                    "srcset": _versioned_srcset(main_image.get("srcset", ""), main_image.get("created_at")),
                    "alt": (main_image.get("title_ar") if lang == "ar" else main_image.get("title_de")) or I18N[lang][slot["label_key"]],
                }
            )
        else:
            result.append(
                {
                    "slot": key,
                    "src": slot["src"],
                    "full": slot["src"],
                    "srcset": "",
                    "alt": I18N[lang][slot["label_key"]],
                }
            )
    return result


def get_gallery_groups(lang: str) -> dict[str, list[dict]]:
    manifest = load_manifest()
    groups: dict[str, list[dict]] = {}
    for slot in GALLERY_SLOTS:
        key = slot["key"]
        section_data = manifest.get(key, {})
        images = [_available_image(img, slot["src"]) for img in section_data.get("images", [])]
        images = [img for img in images if not img["file_missing"]]
        main_id = section_data.get("main_image_id")
        images.sort(key=lambda img: img.get("id") != main_id)
        if images:
            groups[key] = [
                {
                    "full": _versioned_url(img.get("full_url", slot["src"]), img.get("created_at")),
                    "alt": (img.get("title_ar") if lang == "ar" else img.get("title_de")) or I18N[lang][slot["label_key"]],
                }
                for img in images
            ]
        else:
            groups[key] = [{"full": slot["src"], "alt": I18N[lang][slot["label_key"]]}]
    return groups


def get_section_gallery(lang: str, section: str) -> list[dict]:
    manifest = load_manifest()
    section_data = manifest.get(section, {})
    images = section_data.get("images", [])
    main_id = section_data.get("main_image_id")
    rows = []
    fallback = next(slot["src"] for slot in GALLERY_SLOTS if slot["key"] == section)
    for img in images:
        img = _available_image(img, fallback)
        rows.append(
            {
                "id": img.get("id"),
                "thumb": _versioned_url(img.get("thumb_url", img.get("full_url", "")), img.get("created_at")),
                "full": _versioned_url(img.get("full_url", ""), img.get("created_at")),
                "alt": img.get("title_ar") if lang == "ar" else img.get("title_de"),
                "is_main": img.get("id") == main_id,
                "file_missing": img.get("file_missing", False),
            }
        )
    return rows


def verify_admin(request: Request, credentials: HTTPBasicCredentials = Depends(security)) -> str:
    if not ADMIN_PASSWORD:
        raise HTTPException(503, "Administration is not configured")
    key = ('admin', request.client.host if request.client else 'unknown')
    if not limiter.allow(key, 5, 300, record=False):
        raise HTTPException(429, "Too many login attempts", headers={"Retry-After": "300"})
    valid_user = secrets.compare_digest(credentials.username.encode(), ADMIN_USER.encode())
    valid_pass = secrets.compare_digest(credentials.password.encode(), ADMIN_PASSWORD.encode())
    if not (valid_user and valid_pass):
        limiter.allow(key, 5, 300)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def _delete_optimized_files(item: dict) -> None:
    """Archive removed images outside the public mount, retaining rollback files."""
    urls = [item.get('full_url', ''), item.get('thumb_url', '')]
    urls.extend(part.strip().split()[0] for part in item.get('srcset', '').split(',') if part.strip())
    files = {OPTIMIZED_DIR / urlsplit(url).path.rsplit('/', 1)[-1]
             for url in urls if _existing_image_url(url)}
    if not files:
        return
    archive = DATA_DIR / 'deleted-images' / uuid.uuid4().hex
    archive.mkdir(parents=True, mode=0o700)
    for path in files:
        os.replace(path, archive / path.name)


def _render_admin_page(request: Request, user: str, selected_section: str = "reception", upload_success: str | None = None, upload_errors: list[str] | None = None) -> object:
    if selected_section not in SLOT_KEYS:
        selected_section = "reception"

    ctx = base_context(request, noindex=True)
    ctx.update(
        {
            "admin_user": user,
            "upload_success": upload_success,
            "upload_errors": upload_errors or [],
            "selected_section": selected_section,
            "section_images": get_section_gallery(ctx["lang"], selected_section),
        }
    )
    return templates.TemplateResponse(request, "admin_upload_images.html", ctx)


def process_upload_image(file: UploadFile, section: str, title_de: str | None = None, title_ar: str | None = None) -> dict:
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported extension for {file.filename}")
    if file.content_type not in ALLOWED_TYPES:
        raise ValueError(f"Unsupported content type for {file.filename}")

    if section not in SLOT_KEYS:
        raise ValueError("Invalid section")
    if file.size is not None and file.size > MAX_UPLOAD_BYTES:
        raise ValueError(f"Image exceeds {MAX_UPLOAD_MB}MB")
    content = file.file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"{file.filename} exceeds {MAX_UPLOAD_MB}MB")

    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow is not installed") from exc

    from io import BytesIO

    try:
        image = Image.open(BytesIO(content))
        if image.width * image.height > 25_000_000:
            raise ValueError("Image dimensions exceed 25 megapixels")
        image = ImageOps.exif_transpose(image).convert("RGB")
    except Exception as exc:
        raise ValueError(f"Invalid image file: {file.filename}") from exc

    stem = sanitize_stem(file.filename or "image")
    unique = f"{stem}-{uuid.uuid4().hex}"

    width, height = image.size
    generated = []
    for size in TARGET_SIZES:
        if size > width:
            continue
        new_height = int((size / width) * height)
        resized = image.resize((size, new_height), Image.Resampling.LANCZOS)
        out_name = f"{unique}-{size}.webp"
        out_path = OPTIMIZED_DIR / out_name
        resized.save(out_path, "WEBP", quality=82, method=6)
        generated.append((size, out_name))

    if not generated:
        out_name = f"{unique}-{width}.webp"
        out_path = OPTIMIZED_DIR / out_name
        image.save(out_path, "WEBP", quality=82, method=6)
        generated.append((width, out_name))

    generated.sort(key=lambda x: x[0])
    full_name = generated[-1][1]
    thumb_name = generated[0][1]
    srcset = ", ".join([f"/uploads/optimized/{name} {size}w" for size, name in generated])

    pretty = sanitize_stem(file.filename or "image").replace("-", " ").title()

    return {
        "id": f"{section}-{uuid.uuid4().hex[:10]}",
        "section": section,
        "title_de": title_de or pretty,
        "title_ar": title_ar or pretty,
        "full_url": f"/uploads/optimized/{full_name}",
        "thumb_url": f"/uploads/optimized/{thumb_name}",
        "srcset": srcset,
        "created_at": int(time.time()),
    }



def _page_key_from_path(path: str) -> str:
    if path == "/leistungen":
        return "services"
    if path == "/ueber-uns":
        return "about"
    if path == "/kontakt":
        return "contact"
    if path == "/articles" or path.startswith("/articles/"):
        return "articles"
    return "home"


def _seo_context(request: Request, lang: str, noindex: bool = False) -> dict:
    path = request.url.path
    page_key = _page_key_from_path(path)
    canonical = f"{SITE_URL}{path}"
    return {
        "meta_description": SEO_META[lang][page_key],
        "canonical_url": f"{canonical}?lang={lang}",
        "alt_de": f"{canonical}?lang=de",
        "alt_ar": f"{canonical}?lang=ar",
        "meta_robots": "noindex, nofollow" if noindex else "index, follow",
        "schema_json": {
            "@context": "https://schema.org",
            "@type": "Dentist",
            "name": CLINIC_NAME,
            "url": SITE_URL,
            "telephone": PHONE_LANDLINE,
            "address": {
                "@type": "PostalAddress",
                "streetAddress": ADDRESS.split(',')[0].strip(),
                "postalCode": "12055",
                "addressLocality": "Berlin",
                "addressCountry": "DE"
            },
            "areaServed": "Berlin",
            "sameAs": [
                "https://www.doctolib.de/zahnmedizin/berlin/abdulaziz-jaghsi"
            ]
        }
    }

def _slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9\s-]", "", value).strip().lower()
    value = re.sub(r"[\s_-]+", "-", value)
    return value or f"article-{int(time.time())}"


def load_articles() -> list[dict]:
    raw = storage.read_json(ARTICLES_PATH, [])
    if not isinstance(raw, list):
        raise storage.StorageError("Invalid article store")
    items = [x for x in raw if isinstance(x, dict)]
    items.sort(key=lambda x: x.get("updated_at", x.get("created_at", 0)), reverse=True)
    return items


def save_articles(items: list[dict]) -> None:
    storage.write_json(ARTICLES_PATH, items)


def get_article(slug: str) -> dict | None:
    for item in load_articles():
        if item.get("slug") == slug:
            return item
    return None


def _article_public(item: dict, lang: str) -> dict:
    content_lang = lang if item.get(f"title_{lang}") and item.get(f"content_{lang}") else "de"
    title = item.get(f"title_{content_lang}")
    excerpt = item.get(f"excerpt_{content_lang}")
    content = item.get(f"content_{content_lang}")
    return {
        "slug": item.get("slug", ""),
        "title": title or item.get("title_de", ""),
        "excerpt": excerpt or "",
        "content": content or "",
        "cover_url": item.get("cover_url", ""),
        "category": (("عام" if lang == "ar" else "Allgemein") if item.get("category", "General") == "General" else item["category"]),
        "updated_at": item.get("updated_at", item.get("created_at", 0)),
        "reading_minutes": max(1, math.ceil(len((content or "").split()) / 180)),
        "content_lang": content_lang,
    }


def list_published_articles(lang: str) -> list[dict]:
    return [_article_public(a, lang) for a in load_articles() if a.get("status") == "published"]


def article_admin_ctx(request: Request, user: str, message: str | None = None, error: str | None = None, edit_article: dict | None = None) -> dict:
    ctx = base_context(request, noindex=True)
    ctx.update({
        "admin_user": user,
        "admin_message": message,
        "admin_error": error,
        "articles_admin": load_articles(),
        "edit_article": edit_article,
        "original_slug": edit_article.get("slug", "") if edit_article else "",
    })
    return ctx


def base_context(request: Request, noindex: bool = False) -> dict:
    lang = get_lang(request)
    ctx = {
        "request": request,
        "clinic_name": CLINIC_NAME,
        "address": ADDRESS,
        "phone_landline": PHONE_LANDLINE,
        "phone_mobile": PHONE_MOBILE,
        "phone_tel": PHONE_TEL,
        "opening_hours": OPENING_HOURS_AR if lang == "ar" else OPENING_HOURS_DE,
        "csrf_token": request.state.csrf_token,
        "contact_enabled": contact.configured(),
        "max_upload_mb": MAX_UPLOAD_MB,
        "max_upload_files": MAX_UPLOAD_FILES,
        "lang": lang,
        "is_rtl": lang == "ar",
        "t": I18N[lang],
        "gallery_images": load_gallery_images(lang),
        "gallery_groups": get_gallery_groups(lang),
        "gallery_slots": get_gallery_slots(lang),
        "site_url": SITE_URL,
    }
    ctx.update(_seo_context(request, lang, noindex=noindex))
    return ctx




@app.get("/robots.txt", response_class=PlainTextResponse)
def robots_txt() -> str:
    return f"User-agent: *\nAllow: /\nDisallow: /admin/\nSitemap: {SITE_URL}/sitemap.xml\n"


@app.get("/healthz")
def health():
    load_manifest()
    load_articles()
    if not os.access(DATA_DIR, os.W_OK):
        return JSONResponse({"status": "unavailable"}, status_code=503)
    return {"status": "ok"}


@app.get("/sitemap.xml")
def sitemap_xml() -> Response:
    pages = ["/", "/leistungen", "/ueber-uns", "/kontakt", "/articles"]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for page in pages:
        for lang in ("de", "ar"):
            loc = f"{SITE_URL}{page}?lang={lang}"
            lines.extend(["  <url>", f"    <loc>{escape(loc)}</loc>", "    <changefreq>weekly</changefreq>", "    <priority>0.8</priority>", "  </url>"])
    for article in load_articles():
        if article.get("status") != "published":
            continue
        slug = article.get("slug", "")
        if not slug:
            continue
        for lang in ("de", "ar"):
            if not article.get(f"title_{lang}") or not article.get(f"content_{lang}"):
                continue
            loc = f"{SITE_URL}/articles/{slug}?lang={lang}"
            lines.extend(["  <url>", f"    <loc>{escape(loc)}</loc>", "    <changefreq>monthly</changefreq>", "    <priority>0.7</priority>", "  </url>"])
    lines.append('</urlset>')
    return Response(content="\n".join(lines), media_type="application/xml")

@app.get("/")
def startseite(request: Request):
    return templates.TemplateResponse(request, "index.html", base_context(request))


@app.get("/leistungen")
def leistungen(request: Request):
    return templates.TemplateResponse(request, "leistungen.html", base_context(request))


@app.get("/ueber-uns")
def ueber_uns(request: Request):
    return templates.TemplateResponse(request, "ueber_uns.html", base_context(request))


@app.get("/kontakt")
def kontakt(request: Request):
    return templates.TemplateResponse(request, "kontakt.html", base_context(request))




@app.post("/kontakt", dependencies=[Depends(verify_csrf)])
def contact_submit(request: Request, name: str = Form("", max_length=120),
                   email: str = Form("", max_length=254),
                   message: str = Form("", max_length=10000),
                   website: str = Form("", max_length=200)):
    ctx = base_context(request)
    lang = ctx['lang']
    def failed(key, code):
        ctx.update(contact_error=I18N[lang][key], form_values={"name": name, "email": email, "message": message})
        return templates.TemplateResponse(request, "kontakt.html", ctx, status_code=code)
    if not contact.configured():
        return failed('contact_unavailable', 503)
    client = request.client.host if request.client else 'unknown'
    if not limiter.allow(('contact', client), 5, 600):
        return failed('contact_rate_limit', 429)
    name, email, message = name.strip(), email.strip(), message.strip()
    if website or not name or '\n' in name or '\r' in name or not contact.valid_email(email) or not message:
        return failed('contact_invalid', 422)
    if not contact.deliver(name, email, message):
        return failed('contact_failed', 502)
    ctx['success'] = True
    return templates.TemplateResponse(request, "kontakt.html", ctx)


@app.get("/articles")
def articles_list(request: Request):
    ctx = base_context(request)
    lang = ctx["lang"]
    ctx.update({
        "articles": list_published_articles(lang),
        "articles_title": "Artikel & Ratgeber" if lang == "de" else "مقالات ونصائح",
        "articles_intro": "Praxiswissen zu Zahnmedizin, Prothetik und Vorsorge." if lang == "de" else "محتوى طبي مبسط حول علاجات الأسنان والوقاية.",
    })
    return templates.TemplateResponse(request, "articles.html", ctx)


@app.get("/articles/{slug}")
def article_detail(request: Request, slug: str):
    raw = get_article(slug)
    if not raw or raw.get("status") != "published":
        raise HTTPException(status_code=404, detail="Article not found")

    ctx = base_context(request)
    lang = ctx["lang"]
    article = _article_public(raw, lang)
    article_path = f"/articles/{slug}"
    canonical = f"{SITE_URL}{article_path}"
    article_schema = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": article["title"],
        "description": article["excerpt"],
        "datePublished": datetime.fromtimestamp(raw.get("created_at", int(time.time())), timezone.utc).isoformat(),
        "dateModified": datetime.fromtimestamp(raw.get("updated_at", raw.get("created_at", int(time.time()))), timezone.utc).isoformat(),
        "author": {"@type": "Person", "name": "M.Sc. Abdulaziz Jaghsi"},
        "publisher": {"@type": "Dentist", "name": CLINIC_NAME, "url": SITE_URL},
        "mainEntityOfPage": f"{canonical}?lang={article['content_lang']}",
        "inLanguage": article["content_lang"],
    }
    if article.get("cover_url"):
        article_schema["image"] = f"{SITE_URL}{article['cover_url']}"

    ctx.update({
        "article": article,
        "related_articles": [a for a in list_published_articles(lang) if a["slug"] != slug][:3],
        "meta_description": article["excerpt"] or ctx.get("meta_description"),
        "canonical_url": f"{canonical}?lang={lang}",
        "alt_de": f"{canonical}?lang=de",
        "alt_ar": f"{canonical}?lang=ar",
        "article_schema": article_schema,
        "alt_ar": f"{canonical}?lang=ar" if raw.get("title_ar") and raw.get("content_ar") else None,
        "meta_robots": "index, follow" if article["content_lang"] == lang else "noindex, follow",
    })
    return templates.TemplateResponse(request, "article_detail.html", ctx)


@app.get("/admin/articles")
def admin_articles_page(request: Request, user: str = Depends(verify_admin)):
    return templates.TemplateResponse(request, "admin_articles.html", article_admin_ctx(request, user))


@app.post("/admin/articles", dependencies=[Depends(verify_csrf)])
@storage.serialized("articles")
def admin_articles_save(
    request: Request,
    slug: str = Form("", max_length=160),
    original_slug: str = Form("", max_length=160),
    revision: str = Form(""),
    title_de: str = Form("", max_length=200),
    title_ar: str = Form("", max_length=200),
    excerpt_de: str = Form("", max_length=1000),
    excerpt_ar: str = Form("", max_length=1000),
    content_de: str = Form("", max_length=100000),
    content_ar: str = Form("", max_length=100000),
    category: str = Form("General", max_length=100),
    status: str = Form("draft"),
    user: str = Depends(verify_admin),
):
    title_de = title_de.strip()
    if not title_de:
        return templates.TemplateResponse(request, "admin_articles.html", article_admin_ctx(request, user, error="German title is required."))

    items = load_articles()
    clean_slug = _slugify(slug or title_de)
    now = int(time.time())

    def invalid(message):
        submitted = {"slug": slug, "title_de": title_de, "title_ar": title_ar,
                     "excerpt_de": excerpt_de, "excerpt_ar": excerpt_ar,
                     "content_de": content_de, "content_ar": content_ar,
                     "category": category, "status": status, "revision": revision}
        ctx = article_admin_ctx(request, user, error=message, edit_article=submitted)
        ctx['original_slug'] = original_slug
        return templates.TemplateResponse(request, "admin_articles.html", ctx, status_code=409)

    existing = next((it for it in items if it.get('slug') == original_slug), None) if original_slug else None
    if original_slug and not existing:
        return invalid("The original article was not found. Reload before saving.")
    if original_slug and clean_slug != original_slug:
        return invalid("Published links are stable. Keep the original slug when editing.")
    if existing and revision != str(existing.get('revision', existing.get('updated_at', ''))):
        return invalid("This article changed since you opened it. Reload before saving.")
    if not existing and any(it.get('slug') == clean_slug for it in items):
        return invalid("This slug already exists. Choose another slug or edit that article.")
    if status == 'published' and not content_de.strip():
        return invalid("German content is required before publishing.")
    if status == 'published' and bool(title_ar.strip()) != bool(content_ar.strip()):
        return invalid("Provide both Arabic title and Arabic content, or leave both empty.")
    if existing:
        existing.update({
            "title_de": title_de, "title_ar": title_ar.strip(),
            "excerpt_de": excerpt_de.strip(), "excerpt_ar": excerpt_ar.strip(),
            "content_de": content_de.strip(), "content_ar": content_ar.strip(),
            "category": category.strip() or "General",
            "status": "published" if status == "published" else "draft",
            "updated_at": now, "revision": uuid.uuid4().hex,
        })
        msg = "Article updated."
    else:
        items.append({
            "slug": clean_slug,
            "title_de": title_de,
            "title_ar": title_ar.strip(),
            "excerpt_de": excerpt_de.strip(),
            "excerpt_ar": excerpt_ar.strip(),
            "content_de": content_de.strip(),
            "content_ar": content_ar.strip(),
            "category": category.strip() or "General",
            "status": "published" if status == "published" else "draft",
            "cover_url": "",
            "created_at": now,
            "updated_at": now, "revision": uuid.uuid4().hex,
        })
        msg = "Article created."

    save_articles(items)
    return templates.TemplateResponse(request, "admin_articles.html", article_admin_ctx(request, user, message=msg))


@app.post("/admin/articles/edit", dependencies=[Depends(verify_csrf)])
@storage.serialized("articles")
def admin_articles_edit(request: Request, slug: str = Form(""), user: str = Depends(verify_admin)):
    art = get_article(slug)
    if not art:
        return templates.TemplateResponse(request, "admin_articles.html", article_admin_ctx(request, user, error="Article not found."))
    return templates.TemplateResponse(request, "admin_articles.html", article_admin_ctx(request, user, edit_article=art))


@app.post("/admin/articles/delete", dependencies=[Depends(verify_csrf)])
@storage.serialized("articles")
def admin_articles_delete(request: Request, slug: str = Form(""), user: str = Depends(verify_admin)):
    items = load_articles()
    new_items = [a for a in items if a.get("slug") != slug]
    if len(new_items) == len(items):
        return templates.TemplateResponse(request, "admin_articles.html", article_admin_ctx(request, user, error="Article not found."))
    save_articles(new_items)
    return templates.TemplateResponse(request, "admin_articles.html", article_admin_ctx(request, user, message="Article deleted."))

@app.get("/admin/upload-images")
def admin_upload_page(request: Request, section: str = "reception", user: str = Depends(verify_admin)):
    return _render_admin_page(request, user=user, selected_section=section)


@app.post("/admin/upload-images", dependencies=[Depends(verify_csrf)])
@storage.serialized("manifest")
def admin_upload_images(
    request: Request,
    section: str = Form("reception"),
    images: list[UploadFile] = File(...),
    title_de: str = Form(""),
    title_ar: str = Form(""),
    user: str = Depends(verify_admin),
):
    manifest = load_manifest()
    created = []
    errors = []

    if section not in SLOT_KEYS:
        return _render_admin_page(request, user, upload_errors=["Invalid section selected."])
    if len(images) > MAX_UPLOAD_FILES or sum(image.size or 0 for image in images) > MAX_BATCH_BYTES:
        return _render_admin_page(request, user, selected_section=section,
                                  upload_errors=[f"Upload up to {MAX_UPLOAD_FILES} files and 30 MB in total."])


    for image in images:
        if not image.filename:
            continue
        try:
            item = process_upload_image(image, section=section, title_de=title_de or None, title_ar=title_ar or None)
            created.append(item)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Image processing failed (%s)", type(exc).__name__)
            errors.append("Image could not be processed. Check its format, dimensions and size.")

    if created:
        section_data = manifest.get(section, {"main_image_id": None, "images": []})
        existing_images = section_data.get("images", [])
        existing_images.extend(created)
        section_data["images"] = existing_images
        if not section_data.get("main_image_id"):
            section_data["main_image_id"] = created[0]["id"]
        manifest[section] = section_data
        save_manifest(manifest)

    return _render_admin_page(
        request,
        user=user,
        selected_section=section,
        upload_success=f"Uploaded and optimized {len(created)} image(s) for section: {section}." if created else None,
        upload_errors=errors,
    )


@app.post("/admin/upload-images/set-main", dependencies=[Depends(verify_csrf)])
@storage.serialized("manifest")
def admin_set_main_image(
    request: Request,
    section: str = Form("reception"),
    image_id: str = Form(""),
    user: str = Depends(verify_admin),
):
    manifest = load_manifest()
    section_data = manifest.get(section)
    if not section_data:
        return _render_admin_page(request, user=user, selected_section=section, upload_errors=["Section has no uploaded images."])

    images = section_data.get("images", [])
    if not any(img.get("id") == image_id for img in images):
        return _render_admin_page(request, user=user, selected_section=section, upload_errors=["Image not found in this section."])

    section_data["main_image_id"] = image_id
    manifest[section] = section_data
    save_manifest(manifest)

    return _render_admin_page(request, user=user, selected_section=section, upload_success=f"Main image updated for section: {section}.")


@app.post("/admin/upload-images/delete-image", dependencies=[Depends(verify_csrf)])
@storage.serialized("manifest")
def admin_delete_single_image(
    request: Request,
    section: str = Form("reception"),
    image_id: str = Form(""),
    user: str = Depends(verify_admin),
):
    manifest = load_manifest()
    section_data = manifest.get(section)
    if not section_data:
        return _render_admin_page(request, user=user, selected_section=section, upload_errors=["Section has no uploaded images."])

    images = section_data.get("images", [])
    kept = []
    deleted_item = None
    for img in images:
        if img.get("id") == image_id:
            deleted_item = img
        else:
            kept.append(img)

    if not deleted_item:
        return _render_admin_page(request, user=user, selected_section=section, upload_errors=["Image not found."])

    if kept:
        section_data["images"] = kept
        if section_data.get("main_image_id") == image_id:
            section_data["main_image_id"] = kept[0].get("id")
        manifest[section] = section_data
    else:
        manifest.pop(section, None)

    save_manifest(manifest)
    _delete_optimized_files(deleted_item)
    return _render_admin_page(request, user=user, selected_section=section, upload_success=f"Deleted one image from section: {section}.")


@app.post("/admin/upload-images/delete-section", dependencies=[Depends(verify_csrf)])
@storage.serialized("manifest")
def admin_delete_section_image(
    request: Request,
    section: str = Form("reception"),
    user: str = Depends(verify_admin),
):
    manifest = load_manifest()
    if section not in SLOT_KEYS:
        return _render_admin_page(request, user=user, selected_section="reception", upload_errors=["Invalid section selected."])

    section_data = manifest.pop(section, None)
    if section_data:
        save_manifest(manifest)
        for img in section_data.get("images", []):
            _delete_optimized_files(img)
        msg = f"Deleted all images for section: {section}."
    else:
        msg = f"No uploaded images found for section: {section}."

    return _render_admin_page(request, user=user, selected_section=section, upload_success=msg)


@app.post("/admin/upload-images/delete-all", dependencies=[Depends(verify_csrf)])
@storage.serialized("manifest")
def admin_delete_all_images(request: Request, user: str = Depends(verify_admin)):
    manifest = load_manifest()
    save_manifest({})
    for section_data in manifest.values():
        for img in section_data.get("images", []):
            _delete_optimized_files(img)

    return _render_admin_page(request, user=user, upload_success="Deleted all uploaded gallery images.")
