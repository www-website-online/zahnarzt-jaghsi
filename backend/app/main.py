import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

CLINIC_NAME = os.getenv("CLINIC_NAME", "ZAHNARZTPRAXIS – M.Sc. Abdulaziz Jaghsi")
ADDRESS = os.getenv("CLINIC_ADDRESS", "Karl-Marx-Straße 214, 12055 Berlin")
PHONE_LANDLINE = os.getenv("CLINIC_PHONE_LANDLINE", "(030) 685 10 44")
PHONE_MOBILE = os.getenv("CLINIC_PHONE_MOBILE", "015560 555345")

SUPPORTED_LANGS = {"de", "ar"}
DEFAULT_LANG = "de"

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
        "gallery_p": "Professionelle Galerie mit Beispielbildern. Ersetzen Sie diese Platzhalter durch echte Praxisfotos in /static/gallery.",
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
        "gallery_p": "معرض احترافي بصور تجريبية. يمكن استبدالها لاحقًا بصور العيادة الحقيقية داخل /static/gallery.",
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


def get_lang(request: Request) -> str:
    lang = request.query_params.get("lang", DEFAULT_LANG).lower()
    return lang if lang in SUPPORTED_LANGS else DEFAULT_LANG


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
