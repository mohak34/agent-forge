from sqlalchemy import text
from sqlalchemy.engine import Engine


def run_bootstrap_migrations(engine: Engine) -> None:
    statements = [
        "ALTER TABLE runs ADD COLUMN IF NOT EXISTS thread_id VARCHAR(36)",
        "ALTER TABLE runs ADD COLUMN IF NOT EXISTS user_message_id VARCHAR(36)",
        "ALTER TABLE runs ADD COLUMN IF NOT EXISTS assistant_message_id VARCHAR(36)",
        "ALTER TABLE runs ADD COLUMN IF NOT EXISTS turn_index INTEGER DEFAULT 0",
    ]

    with engine.begin() as conn:
        for statement in statements:
            conn.execute(text(statement))
