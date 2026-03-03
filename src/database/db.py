import sqlite3

DB_PATH = "cdss.db"


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS recommendation_run (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                patient_id TEXT NOT NULL,
                disease_state TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS recommendation_score (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                action_name TEXT NOT NULL,
                score REAL NOT NULL,
                confidence REAL NOT NULL,
                FOREIGN KEY(run_id) REFERENCES recommendation_run(id)
            )
        """)

        conn.commit()


def save_recommendation_run(patient_id: str, disease_state: str, recs: list[dict]):
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO recommendation_run (patient_id, disease_state) VALUES (?, ?)",
            (patient_id, disease_state),
        )
        run_id = cur.lastrowid

        for r in recs:
            cur.execute(
                """
                INSERT INTO recommendation_score (run_id, action_name, score, confidence)
                VALUES (?, ?, ?, ?)
                """,
                (run_id, r["action"], r["score"], r["confidence"]),
            )

        conn.commit()
