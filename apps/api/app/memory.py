from sqlalchemy.orm import Session

from app.models import MemoryItem, Run


def scope_key_for_run(run: Run) -> str:
    return "default-workspace"


def get_recent_memory(db: Session, run: Run, limit: int = 5) -> list[MemoryItem]:
    scope_key = scope_key_for_run(run)
    return (
        db.query(MemoryItem)
        .filter(MemoryItem.scope_key == scope_key)
        .order_by(MemoryItem.created_at.desc())
        .limit(limit)
        .all()
    )


def store_memory(db: Session, run: Run, content: str, kind: str = "summary") -> MemoryItem:
    item = MemoryItem(
        scope_key=scope_key_for_run(run),
        run_id=run.id,
        kind=kind,
        content=content,
    )
    db.add(item)
    return item
