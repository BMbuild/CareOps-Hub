"""Base SQLite partagée par les deux espaces (fichier data/careops.db)."""

import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_FILE = ROOT / "data" / "seed.json"

SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    go_live_date  TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS features (
    id           TEXT PRIMARY KEY,
    name         TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL CHECK (status IN ('Planifiée', 'En développement', 'Livrée'))
);
CREATE TABLE IF NOT EXISTS issues (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    severity     TEXT NOT NULL CHECK (severity IN ('Critique', 'Moyenne', 'Faible')),
    state        TEXT NOT NULL CHECK (state IN ('Ouvert', 'En cours', 'Résolu')),
    feature_id   TEXT REFERENCES features(id) ON DELETE SET NULL,
    created_at   TEXT NOT NULL,
    -- 1 = touche tous les clients, y compris ceux ajoutés plus tard (issue_clients reste vide).
    all_clients  INTEGER NOT NULL DEFAULT 0 CHECK (all_clients IN (0, 1)),
    -- Étape retardée par le problème (facultatif). Son client est toujours ajouté aux clients touchés.
    milestone_id TEXT REFERENCES milestones(id) ON DELETE SET NULL
);
-- Un problème peut toucher plusieurs clients : c'est ce lien qui alimente la préparation.
CREATE TABLE IF NOT EXISTS issue_clients (
    issue_id   TEXT NOT NULL REFERENCES issues(id) ON DELETE CASCADE,
    client_id  TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    PRIMARY KEY (issue_id, client_id)
);
CREATE TABLE IF NOT EXISTS milestones (
    id         TEXT PRIMARY KEY,
    client_id  TEXT NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    due_date   TEXT NOT NULL DEFAULT '',
    owner      TEXT NOT NULL DEFAULT '',
    status     TEXT NOT NULL CHECK (status IN ('À faire', 'En cours', 'Terminé', 'Bloqué')),
    blocker    TEXT NOT NULL DEFAULT ''
);
"""

# Champ de l'API (camelCase) -> colonne SQL, par table.
COLUMNS = {
    "clients": {"name": "name", "goLiveDate": "go_live_date"},
    "features": {"name": "name", "description": "description", "status": "status"},
    "issues": {"title": "title", "description": "description", "severity": "severity", "state": "state", "featureId": "feature_id", "allClients": "all_clients", "milestoneId": "milestone_id"},
    "milestones": {"clientId": "client_id", "name": "name", "dueDate": "due_date", "owner": "owner", "status": "status", "blocker": "blocker"},
}


def db_path() -> Path:
    return Path(os.environ.get("CAREOPS_DB", ROOT / "data" / "careops.db"))


@contextmanager
def connect():
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Crée les tables et charge les données de démo si la base est vide."""
    with connect() as conn:
        conn.executescript(SCHEMA)
        # Base créée avant l'option « Tous les clients » : on ajoute la colonne.
        if "all_clients" not in {r["name"] for r in conn.execute("PRAGMA table_info(issues)")}:
            conn.execute("ALTER TABLE issues ADD COLUMN all_clients INTEGER NOT NULL DEFAULT 0 CHECK (all_clients IN (0, 1))")
        # Base créée avant le lien vers une étape : on ajoute la colonne.
        if "milestone_id" not in {r["name"] for r in conn.execute("PRAGMA table_info(issues)")}:
            conn.execute("ALTER TABLE issues ADD COLUMN milestone_id TEXT REFERENCES milestones(id) ON DELETE SET NULL")
        if conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0] == 0:
            _seed(conn)


def reset() -> None:
    with connect() as conn:
        conn.executescript("DELETE FROM issue_clients; DELETE FROM milestones; DELETE FROM issues; DELETE FROM features; DELETE FROM clients;")
        _seed(conn)


def _seed(conn: sqlite3.Connection) -> None:
    seed = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    # Étapes avant problèmes : un problème peut pointer vers l'étape qu'il retarde.
    for collection in ("clients", "features", "milestones", "issues"):
        for item in seed[collection]:
            _insert(conn, collection, item["id"], item, created_at=item.get("createdAt"))


def _insert(conn, collection: str, item_id: str, values: dict, created_at: str | None = None) -> None:
    cols = COLUMNS[collection]
    row = {col: _sql_value(field, values.get(field, "")) for field, col in cols.items()}
    row["id"] = item_id
    if collection == "issues":
        row["created_at"] = created_at or date.today().isoformat()
    names = ", ".join(row)
    conn.execute(f"INSERT INTO {collection} ({names}) VALUES ({', '.join('?' * len(row))})", list(row.values()))
    if collection == "issues":
        _set_issue_clients(conn, item_id, _client_ids(values))


def _client_ids(values: dict) -> list[str]:
    # « Tous les clients » remplace la liste : on ne garde pas de liens individuels.
    return [] if values.get("allClients") else values.get("clientIds", [])


def _sql_value(field: str, value):
    # Une fonctionnalité absente est stockée en NULL pour respecter la clé étrangère.
    if field in ("featureId", "milestoneId"):
        return value or None
    if field == "allClients":
        return int(bool(value))
    return value


def _set_issue_clients(conn, issue_id: str, client_ids: list[str]) -> None:
    conn.execute("DELETE FROM issue_clients WHERE issue_id = ?", (issue_id,))
    known = {r[0] for r in conn.execute("SELECT id FROM clients")}
    for client_id in dict.fromkeys(client_ids):  # dédoublonne en gardant l'ordre
        if client_id in known:
            conn.execute("INSERT INTO issue_clients (issue_id, client_id) VALUES (?, ?)", (issue_id, client_id))


# --- Lecture ------------------------------------------------------------------

def _to_api(collection: str, row: sqlite3.Row) -> dict:
    item = {"id": row["id"]}
    for field, col in COLUMNS[collection].items():
        item[field] = row[col] if row[col] is not None else ""
    return item


def load_state() -> dict:
    with connect() as conn:
        state = {
            "clients": [_to_api("clients", r) for r in conn.execute("SELECT * FROM clients ORDER BY rowid")],
            "features": [_to_api("features", r) for r in conn.execute("SELECT * FROM features ORDER BY rowid")],
            "milestones": [_to_api("milestones", r) for r in conn.execute("SELECT * FROM milestones ORDER BY rowid")],
            "issues": [],
        }
        links: dict[str, list[str]] = {}
        for r in conn.execute("SELECT issue_id, client_id FROM issue_clients ORDER BY rowid"):
            links.setdefault(r["issue_id"], []).append(r["client_id"])
        for r in conn.execute("SELECT * FROM issues ORDER BY rowid"):
            issue = _to_api("issues", r)
            issue["createdAt"] = r["created_at"]
            issue["allClients"] = bool(r["all_clients"])
            issue["clientIds"] = [] if issue["allClients"] else links.get(r["id"], [])
            state["issues"].append(issue)
    return state


def get(collection: str, item_id: str) -> dict | None:
    return next((x for x in load_state()[collection] if x["id"] == item_id), None)


# --- Écriture -----------------------------------------------------------------

class InvalidReference(Exception):
    pass


def create(collection: str, values: dict) -> dict:
    item_id = uuid.uuid4().hex[:8]
    with connect() as conn:
        _check_refs(conn, collection, values)
        _insert(conn, collection, item_id, values)
    return get(collection, item_id)


def update(collection: str, item_id: str, values: dict) -> dict | None:
    with connect() as conn:
        if not conn.execute(f"SELECT 1 FROM {collection} WHERE id = ?", (item_id,)).fetchone():
            return None
        _check_refs(conn, collection, values)
        cols = COLUMNS[collection]
        assignments = ", ".join(f"{col} = ?" for col in cols.values())
        params = [_sql_value(f, values.get(f, "")) for f in cols] + [item_id]
        conn.execute(f"UPDATE {collection} SET {assignments} WHERE id = ?", params)
        if collection == "issues":
            _set_issue_clients(conn, item_id, _client_ids(values))
    return get(collection, item_id)


def delete(collection: str, item_id: str) -> bool:
    with connect() as conn:
        return conn.execute(f"DELETE FROM {collection} WHERE id = ?", (item_id,)).rowcount > 0


def _check_refs(conn, collection: str, values: dict) -> None:
    if collection == "milestones" and not conn.execute("SELECT 1 FROM clients WHERE id = ?", (values["clientId"],)).fetchone():
        raise InvalidReference("Client inconnu.")
    if collection == "issues" and values.get("featureId") and not conn.execute("SELECT 1 FROM features WHERE id = ?", (values["featureId"],)).fetchone():
        raise InvalidReference("Fonctionnalité inconnue.")
    if collection == "issues" and values.get("milestoneId"):
        row = conn.execute("SELECT client_id FROM milestones WHERE id = ?", (values["milestoneId"],)).fetchone()
        if not row:
            raise InvalidReference("Étape inconnue.")
        # Lier une étape lie aussi son client : c'est le client qui porte le blocage.
        if not values.get("allClients") and row["client_id"] not in (values.get("clientIds") or []):
            values["clientIds"] = [*(values.get("clientIds") or []), row["client_id"]]
    # Un problème peut n'être lié à aucun client (« À trier ») : voir readiness.untriaged_critical.
    # Les clients indiqués, eux, doivent exister.
    ids = list(dict.fromkeys(_client_ids(values) or [])) if collection == "issues" else []
    if ids:
        placeholders = ", ".join("?" * len(ids))
        found = conn.execute(f"SELECT COUNT(*) FROM clients WHERE id IN ({placeholders})", ids).fetchone()[0]
        if found != len(ids):
            raise InvalidReference("Client inconnu.")
