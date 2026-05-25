import json
import os
import re
import secrets
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
GALLERY_DIR = STATIC_DIR / "gallery"
RUNTIME_UPLOAD_ROOT = Path("/tmp/zahnarzt-gallery")
OPTIMIZED_DIR = RUNTIME_UPLOAD_ROOT / "optimized"
MANIFEST_PATH = RUNTIME_UPLOAD_ROOT / "manifest.json"

RUNTIME_UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
OPTIMIZED_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(RUNTIME_UPLOAD_ROOT)), name="uploads")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

CLINIC_NAME = os.getenv("CLINIC_NAME", "ZAHNARZTPRAXIS – M.Sc. Abdulaziz Jaghsi")
ADDRESS = os.getenv("CLINIC_ADDRESS", "Karl-Marx-Straße 214, 12055 Berlin")
PHONE_LANDLINE = os.getenv("CLINIC_PHONE_LANDLINE", "(030) 685 10 44")
PHONE_MOBILE = os.getenv("CLINIC_PHONE_MOBILE", "015560 555345")

ADMIN_USER = os.getenv("ADMIN_UPLOAD_USER", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_UPLOAD_PASSWORD", "ChangeMeNow123!")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

SUPPORTED_LANGS = {"de", "ar"}
DEFAULT_LANG = "de"

security = HTTPBasic()

I18N = {
    "de": {
        "clinic_tag": "Zahnarztpraxis Berlin",
        "nav_home": "Startseite",
        "nav_services": "Leistungen",
        "nav_about": "Über uns",
        "nav_contact": "Kontakt",
        "book_btn": "Termin buchen",
        "phone_label": "Telefon",
        "mobile_label": "Mobil",
        "switch_lang": "العربية",
        "home_title_suffix": " – Ihre Zahnarztpraxis in Neukölln",
        "home_eyebrow": "Moderne Zahnmedizin in Berlin-Neukölln",
        "home_h1": "Ihr Lächeln in erfahrenen Händen",
        "home_intro": "Präzise Diagnostik, hochwertige Prothetik und ein einfühlsames Team: Wir begleiten Sie von der ersten Beratung bis zum langfristigen Behandlungserfolg.",
        "home_call": "Jetzt anrufen",
        "home_contact": "Kontakt aufnehmen",
        "home_b1": "Schwerpunkt: Prothetik & Implantatprothetik",
        "home_b2": "Termine schnell online über Doctolib",
        "home_b3": "Deutsch, Arabisch und Englisch",
        "home_kpi1": "Behandlungssprachen",
        "home_kpi2": "Individuelle Beratung",
        "home_kpi3": "Lage in Neukölln",
        "home_glance": "Praxis auf einen Blick",
        "address_label": "Adresse",
        "hours_label": "Sprechzeiten",
        "route_btn": "Route in Google Maps öffnen",
        "home_why_h": "Warum Patientinnen und Patienten uns vertrauen",
        "home_why_p": "Wir kombinieren wissenschaftlich fundierte Zahnmedizin mit klarer Kommunikation und einem ruhigen Behandlungserlebnis.",
        "home_c1_h": "Individuelle Therapiepläne",
        "home_c1_p": "Jeder Befund ist einzigartig. Deshalb planen wir strukturiert, transparent und passend zu Ihrem Alltag.",
        "home_c2_h": "Funktion trifft Ästhetik",
        "home_c2_p": "Von Kronen bis Implantatprothetik achten wir auf langfristige Stabilität und ein natürliches Erscheinungsbild.",
        "home_c3_h": "Kurze Wege, klare Abläufe",
        "home_c3_p": "Direkte Terminbuchung, gute Erreichbarkeit und verständliche Aufklärung sorgen für einen entspannten Praxisbesuch.",
        "gallery_h": "Einblicke in unsere Praxis",
        "gallery_p": "Professionelle Galerie mit Beispielbildern. Neue Bilder können im Admin-Bereich hochgeladen werden.",
        "gallery_zoom": "Bild vergrößern",
        "gallery_i1": "Empfangsbereich",
        "gallery_i2": "Behandlungsraum",
        "gallery_i3": "Beratung mit Patient",
        "gallery_i4": "Digitale Diagnostik",
        "gallery_i5": "Prophylaxe-Behandlung",
        "gallery_i6": "Wartebereich",
        "services_title_suffix": " – Leistungen",
        "services_h1": "Unsere Leistungen",
        "services_intro": "Moderne Zahnmedizin mit Schwerpunkt Prothetik: Wir entwickeln für Sie präzise, nachhaltige und ästhetisch überzeugende Lösungen.",
        "about_title_suffix": " – Über uns",
        "about_h1": "Über unsere Praxis",
        "about_intro": "Bei uns stehen Fachkompetenz, Respekt und verständliche Kommunikation im Mittelpunkt. Unser Ziel ist eine langfristig gesunde und ästhetische Zahnsituation für Sie.",
        "contact_title_suffix": " – Kontakt",
        "contact_h1": "Kontakt & Termin",
        "contact_intro": "Sie möchten einen Termin vereinbaren oder haben eine Frage zu einer Behandlung? Wir beraten Sie gerne persönlich.",
        "contact_form_h": "Kontaktformular",
        "contact_success": "Vielen Dank. Ihre Nachricht wurde erfolgreich gesendet.",
        "name_label": "Ihr Name",
        "email_label": "E-Mail",
        "message_label": "Ihre Nachricht",
        "send_btn": "Nachricht senden",
        "contact_hint": "Bitte senden Sie keine Notfälle per E-Mail. In dringenden Fällen rufen Sie uns direkt an.",
        "contact_data_h": "Praxisdaten",
        "online_booking_h": "Online-Termin",
        "online_booking_p": "Buchen Sie Ihren Termin bequem online über Doctolib.",
        "service_1_h": "Prothetik (Schwerpunkt)",
        "service_1_p": "Individuelle Konzepte für festen und herausnehmbaren Zahnersatz.",
        "service_1_l1": "Kronen und Brücken",
        "service_1_l2": "Teil- und Vollprothesen",
        "service_1_l3": "Kombinationsversorgungen",
        "service_2_h": "Implantatprothetik",
        "service_2_p": "Stabiler Zahnersatz auf Implantaten mit natürlicher Funktion.",
        "service_2_l1": "Einzelzahnersatz",
        "service_2_l2": "Implantatgetragene Brücken",
        "service_2_l3": "Festsitzende und herausnehmbare Lösungen",
        "service_3_h": "Ästhetische Zahnheilkunde",
        "service_3_p": "Harmonische Ergebnisse für ein gesundes und selbstbewusstes Lächeln.",
        "service_3_l1": "Zahnfarbene Füllungen",
        "service_3_l2": "Veneers",
        "service_3_l3": "Rekonstruktionen im Frontzahnbereich",
        "service_4_h": "Prophylaxe & Zahnreinigung",
        "service_4_p": "Professionelle Vorsorge zum Schutz von Zähnen und Zahnfleisch.",
        "service_4_l1": "Professionelle Zahnreinigung",
        "service_4_l2": "Mundhygiene-Beratung",
        "service_4_l3": "Regelmäßige Kontrollen",
        "service_5_h": "Schmerzbehandlung",
        "service_5_p": "Schnelle und strukturierte Hilfe bei akuten Beschwerden.",
        "service_5_l1": "Akutdiagnostik",
        "service_5_l2": "Entzündungs- und Schmerztherapie",
        "service_5_l3": "Planung der Folgetherapie",
        "service_6_h": "Beratung & Zweitmeinung",
        "service_6_p": "Klare Einschätzung Ihrer Situation mit transparenten Optionen.",
        "service_6_l1": "Ausführliche Befundbesprechung",
        "service_6_l2": "Therapiealternativen im Überblick",
        "service_6_l3": "Verständliche Kostenaufklärung",
        "about_doctor_h": "M.Sc. Abdulaziz Jaghsi",
        "about_doctor_p": "Mit Spezialisierung in Prothetik bietet Herr Jaghsi hochwertige, wissenschaftlich fundierte Behandlungskonzepte für funktionelle und ästhetische Ergebnisse.",
        "about_focus_h": "Behandlungsschwerpunkte",
        "about_focus_l1": "Prothetische Versorgungen",
        "about_focus_l2": "Implantatgetragener Zahnersatz",
        "about_focus_l3": "Ästhetische Rekonstruktionen",
        "about_philosophy_h": "Unsere Philosophie",
        "about_philosophy_l1": "Individuelle Konzepte statt Standardlösungen",
        "about_philosophy_l2": "Ausführliche Aufklärung vor jeder Behandlung",
        "about_philosophy_l3": "Einfühlsame Betreuung in ruhiger Atmosphäre",
        "about_languages_h": "Sprachen",
        "about_languages_l1": "Deutsch",
        "about_languages_l2": "Arabisch",
        "about_languages_l3": "Englisch",
    },
    "ar": {
        "clinic_tag": "عيادة أسنان في برلين",
        "nav_home": "الرئيسية",
        "nav_services": "الخدمات",
        "nav_about": "من نحن",
        "nav_contact": "التواصل",
        "book_btn": "احجز موعدًا",
        "phone_label": "الهاتف",
        "mobile_label": "الجوال",
        "switch_lang": "Deutsch",
        "home_title_suffix": " - عيادتكم في نويكولن",
        "home_eyebrow": "طب أسنان حديث في برلين نويكولن",
        "home_h1": "ابتسامتكم بين أيدٍ خبيرة",
        "home_intro": "تشخيص دقيق، وتعويضات سنية عالية الجودة، وفريق متفهم: نرافقكم من الاستشارة الأولى حتى نجاح العلاج على المدى الطويل.",
        "home_call": "اتصل الآن",
        "home_contact": "تواصل معنا",
        "home_b1": "تركيزنا: التعويضات السنية وزراعة الأسنان",
        "home_b2": "حجز سريع عبر Doctolib",
        "home_b3": "الألمانية والعربية والإنجليزية",
        "home_kpi1": "لغات العلاج",
        "home_kpi2": "استشارة فردية",
        "home_kpi3": "موقع مميز",
        "home_glance": "معلومات سريعة",
        "address_label": "العنوان",
        "hours_label": "ساعات العمل",
        "route_btn": "افتح المسار في خرائط Google",
        "home_why_h": "لماذا يثق بنا المرضى",
        "home_why_p": "نجمع بين طب أسنان مبني على العلم وتواصل واضح وتجربة علاج مريحة.",
        "home_c1_h": "خطط علاج شخصية",
        "home_c1_p": "كل حالة مختلفة، لذلك نخطط بشكل واضح وشفاف ومناسب لحياتكم اليومية.",
        "home_c2_h": "وظيفة وجمال",
        "home_c2_p": "من التيجان إلى التعويضات على الزرعات نركز على الثبات الطويل والمظهر الطبيعي.",
        "home_c3_h": "خطوات واضحة",
        "home_c3_p": "حجز مباشر، سهولة وصول، وشرح مفهوم قبل العلاج لتجربة أكثر راحة.",
        "gallery_h": "جولة داخل العيادة",
        "gallery_p": "معرض احترافي. يمكن رفع صور جديدة ومعالجتها تلقائيًا من لوحة الإدارة.",
        "gallery_zoom": "تكبير الصورة",
        "gallery_i1": "منطقة الاستقبال",
        "gallery_i2": "غرفة العلاج",
        "gallery_i3": "استشارة مع المريض",
        "gallery_i4": "تشخيص رقمي",
        "gallery_i5": "جلسة وقاية",
        "gallery_i6": "منطقة الانتظار",
        "services_title_suffix": " - الخدمات",
        "services_h1": "خدماتنا",
        "services_intro": "طب أسنان حديث مع تركيز على التعويضات السنية: نطوّر حلولًا دقيقة ومستدامة وجمالية.",
        "about_title_suffix": " - من نحن",
        "about_h1": "عن العيادة",
        "about_intro": "نضع الخبرة والاحترام والتواصل الواضح في قلب كل زيارة. هدفنا صحة فموية وجمالية طويلة الأمد.",
        "contact_title_suffix": " - التواصل",
        "contact_h1": "التواصل وحجز الموعد",
        "contact_intro": "هل ترغبون بحجز موعد أو لديكم سؤال علاجي؟ يسعدنا مساعدتكم.",
        "contact_form_h": "نموذج التواصل",
        "contact_success": "شكرًا لكم، تم إرسال رسالتكم بنجاح.",
        "name_label": "الاسم",
        "email_label": "البريد الإلكتروني",
        "message_label": "الرسالة",
        "send_btn": "إرسال الرسالة",
        "contact_hint": "يرجى عدم إرسال الحالات الإسعافية عبر البريد. للحالات العاجلة اتصلوا بنا مباشرة.",
        "contact_data_h": "بيانات العيادة",
        "online_booking_h": "حجز أونلاين",
        "online_booking_p": "احجز موعدك بسهولة عبر Doctolib.",
        "service_1_h": "التعويضات السنية (الاختصاص)",
        "service_1_p": "حلول فردية للتعويضات الثابتة والمتحركة.",
        "service_1_l1": "تيجان وجسور",
        "service_1_l2": "أطقم جزئية وكاملة",
        "service_1_l3": "تركيبات مشتركة",
        "service_2_h": "تعويضات على الزرعات",
        "service_2_p": "تعويضات ثابتة ومريحة على الزرعات بوظيفة طبيعية.",
        "service_2_l1": "تعويض سن مفرد",
        "service_2_l2": "جسور مدعومة بالزرعات",
        "service_2_l3": "حلول ثابتة ومتحركة",
        "service_3_h": "طب الأسنان التجميلي",
        "service_3_p": "نتائج متناغمة لابتسامة صحية وواثقة.",
        "service_3_l1": "حشوات بلون الأسنان",
        "service_3_l2": "فينير",
        "service_3_l3": "ترميمات تجميلية للأسنان الأمامية",
        "service_4_h": "الوقاية والتنظيف",
        "service_4_p": "وقاية احترافية لحماية الأسنان واللثة.",
        "service_4_l1": "تنظيف احترافي للأسنان",
        "service_4_l2": "إرشادات العناية الفموية",
        "service_4_l3": "فحوصات دورية",
        "service_5_h": "علاج الألم",
        "service_5_p": "مساعدة سريعة ومنظمة للحالات الحادة.",
        "service_5_l1": "تشخيص الحالات العاجلة",
        "service_5_l2": "علاج الالتهاب والألم",
        "service_5_l3": "خطة متابعة علاجية",
        "service_6_h": "استشارة ورأي ثانٍ",
        "service_6_p": "تقييم واضح وخيارات علاج شفافة.",
        "service_6_l1": "مناقشة مفصلة للحالة",
        "service_6_l2": "عرض بدائل العلاج",
        "service_6_l3": "توضيح التكاليف بشكل مفهوم",
        "about_doctor_h": "ماجستير عبد العزيز جغصي",
        "about_doctor_p": "بخبرة متخصصة في التعويضات السنية يقدّم الدكتور خطط علاج عالية الجودة مبنية على أسس علمية.",
        "about_focus_h": "محاور العلاج",
        "about_focus_l1": "التعويضات السنية",
        "about_focus_l2": "تعويضات مدعومة بالزرعات",
        "about_focus_l3": "ترميمات تجميلية",
        "about_philosophy_h": "فلسفتنا",
        "about_philosophy_l1": "خطط فردية بدل الحلول الموحدة",
        "about_philosophy_l2": "شرح واضح قبل كل إجراء",
        "about_philosophy_l3": "رعاية متفهمة في أجواء هادئة",
        "about_languages_h": "اللغات",
        "about_languages_l1": "الألمانية",
        "about_languages_l2": "العربية",
        "about_languages_l3": "الإنجليزية",
    },
}


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
    if not MANIFEST_PATH.exists():
        return {}
    try:
        raw = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

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
        return {}

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
    MANIFEST_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


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


def load_gallery_images(lang: str) -> list[dict]:
    manifest = load_manifest()
    result = []
    for slot in GALLERY_SLOTS:
        key = slot["key"]
        section_data = manifest.get(key)
        main_image = _get_main_image(section_data)
        if main_image:
            result.append(
                {
                    "slot": key,
                    "src": _versioned_url(main_image.get("thumb_url", main_image.get("full_url", slot["src"])), main_image.get("created_at")),
                    "full": _versioned_url(main_image.get("full_url", slot["src"]), main_image.get("created_at")),
                    "srcset": _versioned_srcset(main_image.get("srcset", ""), main_image.get("created_at")),
                    "alt": main_image.get("title_ar") if lang == "ar" else main_image.get("title_de"),
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
        images = section_data.get("images", [])
        if images:
            groups[key] = [
                {
                    "full": _versioned_url(img.get("full_url", slot["src"]), img.get("created_at")),
                    "alt": img.get("title_ar") if lang == "ar" else img.get("title_de") or I18N[lang][slot["label_key"]],
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
    for img in images:
        rows.append(
            {
                "id": img.get("id"),
                "thumb": _versioned_url(img.get("thumb_url", img.get("full_url", "")), img.get("created_at")),
                "full": _versioned_url(img.get("full_url", ""), img.get("created_at")),
                "alt": img.get("title_ar") if lang == "ar" else img.get("title_de"),
                "is_main": img.get("id") == main_id,
            }
        )
    return rows


def verify_admin(credentials: HTTPBasicCredentials = Depends(security)) -> str:
    valid_user = secrets.compare_digest(credentials.username, ADMIN_USER)
    valid_pass = secrets.compare_digest(credentials.password, ADMIN_PASSWORD)
    if not (valid_user and valid_pass):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


def _delete_optimized_files(item: dict) -> None:
    urls = [item.get("full_url", ""), item.get("thumb_url", ""), *[u.strip().split(" ")[0] for u in item.get("srcset", "").split(",") if u.strip()]]
    seen = set()
    for url in urls:
        if not url.startswith("/uploads/optimized/"):
            continue
        name = url.split("/uploads/optimized/")[-1]
        if not name or name in seen:
            continue
        seen.add(name)
        fp = OPTIMIZED_DIR / name
        if fp.exists() and fp.is_file():
            fp.unlink()


def _render_admin_page(request: Request, user: str, selected_section: str = "reception", upload_success: str | None = None, upload_errors: list[str] | None = None) -> object:
    if selected_section not in SLOT_KEYS:
        selected_section = "reception"

    ctx = base_context(request)
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

    content = file.file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError(f"{file.filename} exceeds {MAX_UPLOAD_MB}MB")

    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("Pillow is not installed") from exc

    from io import BytesIO

    try:
        image = Image.open(BytesIO(content))
        image = ImageOps.exif_transpose(image).convert("RGB")
    except Exception as exc:
        raise ValueError(f"Invalid image file: {file.filename}") from exc

    stem = sanitize_stem(file.filename or "image")
    unique = f"{stem}-{int(time.time())}"

    width, height = image.size
    generated = []
    for size in TARGET_SIZES:
        if size > width:
            continue
        new_height = int((size / width) * height)
        resized = image.resize((size, new_height))
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


def base_context(request: Request) -> dict:
    lang = get_lang(request)
    return {
        "request": request,
        "clinic_name": CLINIC_NAME,
        "address": ADDRESS,
        "phone_landline": PHONE_LANDLINE,
        "phone_mobile": PHONE_MOBILE,
        "lang": lang,
        "is_rtl": lang == "ar",
        "t": I18N[lang],
        "gallery_images": load_gallery_images(lang),
        "gallery_groups": get_gallery_groups(lang),
        "gallery_slots": get_gallery_slots(lang),
    }


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


@app.get("/admin/upload-images")
def admin_upload_page(request: Request, section: str = "reception", user: str = Depends(verify_admin)):
    return _render_admin_page(request, user=user, selected_section=section)


@app.post("/admin/upload-images")
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
        errors.append("Invalid section selected.")

    for image in images:
        if not image.filename:
            continue
        try:
            item = process_upload_image(image, section=section, title_de=title_de or None, title_ar=title_ar or None)
            created.append(item)
        except Exception as exc:  # noqa: BLE001
            errors.append(str(exc))

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


@app.post("/admin/upload-images/set-main")
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


@app.post("/admin/upload-images/delete-image")
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

    _delete_optimized_files(deleted_item)

    if kept:
        section_data["images"] = kept
        if section_data.get("main_image_id") == image_id:
            section_data["main_image_id"] = kept[0].get("id")
        manifest[section] = section_data
    else:
        manifest.pop(section, None)

    save_manifest(manifest)
    return _render_admin_page(request, user=user, selected_section=section, upload_success=f"Deleted one image from section: {section}.")


@app.post("/admin/upload-images/delete-section")
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
        for img in section_data.get("images", []):
            _delete_optimized_files(img)
        save_manifest(manifest)
        msg = f"Deleted all images for section: {section}."
    else:
        msg = f"No uploaded images found for section: {section}."

    return _render_admin_page(request, user=user, selected_section=section, upload_success=msg)


@app.post("/admin/upload-images/delete-all")
def admin_delete_all_images(request: Request, user: str = Depends(verify_admin)):
    manifest = load_manifest()
    for section_data in manifest.values():
        for img in section_data.get("images", []):
            _delete_optimized_files(img)

    if OPTIMIZED_DIR.exists():
        for fp in OPTIMIZED_DIR.iterdir():
            if fp.is_file():
                fp.unlink()

    if MANIFEST_PATH.exists():
        MANIFEST_PATH.unlink()

    return _render_admin_page(request, user=user, upload_success="Deleted all uploaded gallery images.")
