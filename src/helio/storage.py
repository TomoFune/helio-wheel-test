"""Local storage (SQLite) for saved birth data, so a chart can be
re-run later without re-typing date/time/place -- same pattern as
horoscope-app's `storage.py` (its `Person`/`Storage` design, including
the free-text `category` field for user-defined grouping, e.g. "家族",
"偉人", "芸能人" -- not a fixed enum, whatever text the user types
becomes a usable category). Everything stays local to this PC; no
network calls happen here.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "helio.db"
DEFAULT_BACKUP_DIR = PROJECT_ROOT / "data" / "backups"

SCHEMA = """
CREATE TABLE IF NOT EXISTS person (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    birth_date TEXT NOT NULL,       -- 'YYYY-MM-DD' (local date)
    birth_time TEXT,                -- 'HH:MM:SS' (local time; NULL if time_unknown)
    time_unknown INTEGER NOT NULL DEFAULT 0,
    timezone TEXT NOT NULL,         -- IANA name, e.g. 'Asia/Tokyo'
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    place_name TEXT,
    category TEXT NOT NULL DEFAULT '',  -- free-text user grouping (家族/偉人/芸能人/...)
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@dataclass
class Person:
    id: int | None
    name: str
    birth_date: str  # 'YYYY-MM-DD'
    birth_time: str | None  # 'HH:MM:SS' or None
    time_unknown: bool
    timezone: str
    latitude: float
    longitude: float
    place_name: str = ""
    category: str = ""
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""


class Storage:
    def __init__(self, db_path: Path | str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Storage":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # --- CRUD ---

    def add_person(self, person: Person) -> int:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            """INSERT INTO person
               (name, birth_date, birth_time, time_unknown, timezone,
                latitude, longitude, place_name, category, notes,
                created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (person.name, person.birth_date, person.birth_time,
             int(person.time_unknown), person.timezone,
             person.latitude, person.longitude, person.place_name,
             person.category, person.notes, now, now),
        )
        self._conn.commit()
        return cur.lastrowid

    def get_person(self, person_id: int) -> Person | None:
        row = self._conn.execute("SELECT * FROM person WHERE id = ?", (person_id,)).fetchone()
        return self._row_to_person(row) if row else None

    def find_by_name(self, query: str) -> list[Person]:
        """Case-insensitive substring match on name -- lets the CLI take
        a name instead of forcing the user to remember numeric ids."""
        rows = self._conn.execute(
            "SELECT * FROM person WHERE name LIKE ? ORDER BY name COLLATE NOCASE",
            (f"%{query}%",),
        ).fetchall()
        return [self._row_to_person(r) for r in rows]

    def list_people(self, category: str | None = None) -> list[Person]:
        if category is not None:
            rows = self._conn.execute(
                "SELECT * FROM person WHERE category = ? ORDER BY name COLLATE NOCASE",
                (category,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM person ORDER BY category COLLATE NOCASE, name COLLATE NOCASE"
            ).fetchall()
        return [self._row_to_person(r) for r in rows]

    def list_categories(self) -> list[str]:
        """Distinct in-use category names (blank excluded), sorted."""
        rows = self._conn.execute(
            "SELECT DISTINCT category FROM person WHERE category != '' ORDER BY category COLLATE NOCASE"
        ).fetchall()
        return [r["category"] for r in rows]

    def update_person(self, person_id: int, **fields) -> None:
        if not fields:
            return
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [person_id]
        self._conn.execute(f"UPDATE person SET {set_clause} WHERE id = ?", values)
        self._conn.commit()

    def delete_person(self, person_id: int) -> None:
        self._conn.execute("DELETE FROM person WHERE id = ?", (person_id,))
        self._conn.commit()

    @staticmethod
    def _row_to_person(row: sqlite3.Row) -> Person:
        return Person(
            id=row["id"],
            name=row["name"],
            birth_date=row["birth_date"],
            birth_time=row["birth_time"],
            time_unknown=bool(row["time_unknown"]),
            timezone=row["timezone"],
            latitude=row["latitude"],
            longitude=row["longitude"],
            place_name=row["place_name"] or "",
            category=row["category"] or "",
            notes=row["notes"] or "",
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # --- backup / restore ---

    def backup_file_copy(self, backup_dir: Path | str = DEFAULT_BACKUP_DIR) -> Path:
        backup_dir = Path(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        self._conn.commit()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = backup_dir / f"helio_{timestamp}.db"
        shutil.copy2(self.db_path, dest)
        return dest

    def export_json(self, path: Path | str) -> Path:
        path = Path(path)
        people = [asdict(p) for p in self.list_people()]
        payload = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "format_version": 1,
            "people": people,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def import_json(self, path: Path | str, replace_existing: bool = False) -> int:
        path = Path(path)
        payload = json.loads(path.read_text(encoding="utf-8"))

        if replace_existing:
            self._conn.execute("DELETE FROM person")
            self._conn.commit()

        count = 0
        for entry in payload.get("people", []):
            person = Person(
                id=None,
                name=entry["name"],
                birth_date=entry["birth_date"],
                birth_time=entry.get("birth_time"),
                time_unknown=bool(entry.get("time_unknown", False)),
                timezone=entry["timezone"],
                latitude=entry["latitude"],
                longitude=entry["longitude"],
                place_name=entry.get("place_name", ""),
                category=entry.get("category", ""),
                notes=entry.get("notes", ""),
            )
            self.add_person(person)
            count += 1
        return count
