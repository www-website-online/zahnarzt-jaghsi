import os
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

app = FastAPI()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# يمكن لاحقاً جعلها من المتغيرات البيئية لو حبيت
CLINIC_NAME = os.getenv("CLINIC_NAME", "ZAHNARZTPRAXIS – M.Sc. Abdulaziz Jaghsi")
ADDRESS = os.getenv("CLINIC_ADDRESS", "Karl-Marx-Straße 214, 12055 Berlin")
PHONE_LANDLINE = os.getenv("CLINIC_PHONE_LANDLINE", "(030) 685 10 44")
PHONE_MOBILE = os.getenv("CLINIC_PHONE_MOBILE", "015650 555345")


def base_context(request: Request) -> dict:
    """سياق مشترك لكل الصفحات (للفوتر والهيدر)."""
    return {
        "request": request,
        "clinic_name": CLINIC_NAME,
        "address": ADDRESS,
        "phone_landline": PHONE_LANDLINE,
        "phone_mobile": PHONE_MOBILE,
    }


@app.get("/")
def startseite(request: Request):
    ctx = base_context(request)
    return templates.TemplateResponse("index.html", ctx)


@app.get("/leistungen")
def leistungen(request: Request):
    ctx = base_context(request)
    return templates.TemplateResponse("leistungen.html", ctx)


@app.get("/ueber-uns")
def ueber_uns(request: Request):
    ctx = base_context(request)
    return templates.TemplateResponse("ueber_uns.html", ctx)


@app.get("/kontakt")
def kontakt(request: Request):
    ctx = base_context(request)
    return templates.TemplateResponse("kontakt.html", ctx)
