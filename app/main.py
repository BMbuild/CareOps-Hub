"""Serveur FastAPI de CareOps Hub : API des données (SQLite), API IA et fichiers du front."""

import logging
import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Body, FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

from . import ai, db
from .models import MODELS
from .readiness import compute_all, compute_readiness

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
log = logging.getLogger("careops")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        log.warning("ANTHROPIC_API_KEY absente : les fonctions IA sont désactivées.")
    yield


app = FastAPI(title="CareOps Hub", lifespan=lifespan)


@app.middleware("http")
async def no_stale_front(request: Request, call_next):
    # Le navigateur revalide toujours le front : une modification de CSS ou de JS est visible tout de suite.
    response = await call_next(request)
    if not request.url.path.startswith("/api"):
        response.headers["Cache-Control"] = "no-cache"
    return response


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        self.status, self.message = status, message


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    return JSONResponse({"error": exc.message}, status_code=exc.status)


def today() -> str:
    return date.today().isoformat()


def validate(collection: str, body: dict) -> dict:
    """Valide le corps avec le modèle Pydantic de la collection ; message lisible en cas d'erreur."""
    try:
        return MODELS[collection].model_validate(body).model_dump()
    except ValidationError as e:
        first = e.errors()[0]
        field = ".".join(str(p) for p in first["loc"]) or "corps"
        raise ApiError(400, f"Champ « {field} » invalide : {first['msg']}") from e


def check_collection(collection: str) -> None:
    if collection not in MODELS:
        raise ApiError(404, "Collection inconnue.")


# --- Données partagées --------------------------------------------------------

@app.get("/api/state")
def get_state():
    state = db.load_state()
    return {**state, "readiness": compute_all(state, today()), "today": today(), "aiEnabled": bool(os.environ.get("ANTHROPIC_API_KEY"))}


@app.post("/api/reset")
def reset():
    db.reset()
    return {"ok": True}


@app.get("/api/{collection}")
def list_items(collection: str):
    check_collection(collection)
    return db.load_state()[collection]


@app.post("/api/{collection}", status_code=201)
def create_item(collection: str, body: dict = Body(...)):
    check_collection(collection)
    try:
        return db.create(collection, validate(collection, body))
    except db.InvalidReference as e:
        raise ApiError(400, str(e)) from e


@app.put("/api/{collection}/{item_id}")
def update_item(collection: str, item_id: str, body: dict = Body(...)):
    check_collection(collection)
    existing = db.get(collection, item_id)
    if existing is None:
        raise ApiError(404, "Élément introuvable.")
    # Mise à jour partielle : on fusionne avec l'existant puis on revalide le tout.
    try:
        return db.update(collection, item_id, validate(collection, {**existing, **body}))
    except db.InvalidReference as e:
        raise ApiError(400, str(e)) from e


@app.delete("/api/{collection}/{item_id}", status_code=204)
def delete_item(collection: str, item_id: str):
    check_collection(collection)
    if not db.delete(collection, item_id):
        raise ApiError(404, "Élément introuvable.")
    return Response(status_code=204)


# --- Fonctions IA -------------------------------------------------------------
# Routes en `def` (pas `async`) : FastAPI les exécute dans un thread, l'appel à Claude ne bloque pas le serveur.

def require_ai() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise ApiError(503, "IA indisponible : ANTHROPIC_API_KEY manquante dans .env.")


def find_client(client_id: str):
    state = db.load_state()
    client = next((c for c in state["clients"] if c["id"] == client_id), None)
    if client is None:
        raise ApiError(400, "Client introuvable.")
    return client, state, compute_readiness(client, state, today())


def run_ai(fn, *args):
    try:
        return fn(*args)
    except ai.AIError as e:
        raise ApiError(502, str(e)) from e


@app.post("/api/ai/summary")
def ai_summary(body: dict = Body(...)):
    require_ai()
    client, state, readiness = find_client(str(body.get("clientId", "")))
    return {"text": run_ai(ai.summarize_readiness, client, state, readiness, today())}


@app.post("/api/ai/severity")
def ai_severity(body: dict = Body(...)):
    require_ai()
    title = str(body.get("title", "")).strip()[:160]
    if not title:
        raise ApiError(400, "Donnez un titre au problème avant de demander une gravité.")
    features = {f["id"]: f["name"] for f in db.load_state()["features"]}
    description = str(body.get("description", ""))[:2000]
    return run_ai(ai.suggest_severity, title, description, features.get(body.get("featureId")))


@app.post("/api/ai/email")
def ai_email(body: dict = Body(...)):
    require_ai()
    client, state, readiness = find_client(str(body.get("clientId", "")))
    summary = str(body.get("summary", ""))[:3000]
    return {"text": run_ai(ai.draft_client_email, client, state, readiness, today(), summary)}


# Le front (HTML, CSS, JS) est servi à la racine. Monté en dernier pour ne pas masquer /api.
app.mount("/", StaticFiles(directory=ROOT / "public", html=True), name="public")
