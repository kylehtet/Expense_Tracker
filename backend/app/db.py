"""SQLite persistence (portable to Postgres later via DATABASE_URL) for linked
items, synced transactions, and per-category budgets."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator, Optional

from sqlalchemy import Float, String, UniqueConstraint, create_engine, delete, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker

from app.config import DATABASE_URL
from app.crypto import decrypt, encrypt

# Some providers (older Heroku-style URLs) still hand out "postgres://", which
# SQLAlchemy 1.4+ rejects outright - psycopg2 accepts either, but SQLAlchemy's
# dialect lookup wants "postgresql://" specifically. Neon's own URLs already
# use the right scheme, so this is just defensive for whatever else ends up
# in DATABASE_URL later.
_database_url = DATABASE_URL
if _database_url.startswith("postgres://"):
    _database_url = _database_url.replace("postgres://", "postgresql://", 1)

_connect_args = {"check_same_thread": False} if _database_url.startswith("sqlite") else {}
engine = create_engine(
    _database_url,
    connect_args=_connect_args,
    # Neon (and most serverless/autosuspending Postgres) can drop an idle
    # connection server-side - e.g. suspending the compute after inactivity -
    # without the pool knowing. Without pool_pre_ping, the next request to
    # reuse that pooled connection fails with "SSL connection has been closed
    # unexpectedly" instead of transparently getting a fresh one. pre_ping
    # issues a cheap liveness check before handing out a pooled connection and
    # silently replaces it if it's dead; pool_recycle proactively retires
    # connections older than 5 minutes so they're not even given the chance
    # to go stale. No-op for the local SQLite fallback (single file, no
    # server-side connection to drop).
    pool_pre_ping=True,
    pool_recycle=300,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class Item(Base):
    """One Plaid Item (linked bank connection) per user. access_token is only
    ever stored encrypted, and there's no way to read it back in plaintext
    except through decrypt_access_token below - never serialized to the API."""

    __tablename__ = "items"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    access_token_encrypted: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class TransactionRecord(Base):
    __tablename__ = "transactions"

    # Plaid's own transaction_id as the primary key means re-syncing the same
    # transaction is a natural upsert, not a duplicate.
    transaction_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    date: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    merchant_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    amount: Mapped[float] = mapped_column(Float)
    category: Mapped[str] = mapped_column(String)


class ProductionLinkEvent(Base):
    """One row per Firebase account that has EVER linked a real (non-Sandbox)
    Plaid Item - at most one row per user_id (enforced by the unique
    constraint below), so an account disconnecting and relinking doesn't
    burn a second slot against this app's own connection limit. Never
    deleted by a disconnect - Plaid's own Trial-plan quota doesn't free up
    when an Item is removed either, so "this account has used a slot" needs
    to stay true forever, not just while currently connected."""

    __tablename__ = "production_link_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


class GoalRecord(Base):
    """A savings goal (e.g. "PS5", "Flight to Tokyo"). monthly_savings_capacity
    is the deterministic savings-capacity estimate computed at creation time
    (see app.goal_tracker) - the original "plan" that later health checks
    compare actual spending pace against, so a goal's baseline doesn't
    silently drift every time its health is recomputed."""

    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    name: Mapped[str] = mapped_column(String)
    target_amount: Mapped[float] = mapped_column(Float)
    target_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    current_saved: Mapped[float] = mapped_column(Float, default=0.0)
    category: Mapped[str] = mapped_column(String)
    monthly_savings_capacity: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String, default="active")


class BudgetRecord(Base):
    __tablename__ = "budgets"
    __table_args__ = (UniqueConstraint("user_id", "category", name="uq_budget_user_category"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String, index=True)
    category: Mapped[str] = mapped_column(String)
    amount: Mapped[float] = mapped_column(Float)


class InterestSignup(Base):
    """An email left on the landing page's 'get notified' form - not a user
    account, no auth, nothing else attached. Kept separate from Firebase
    entirely since expressing interest shouldn't require creating a real
    account before the app is ready for real users beyond the developer."""

    __tablename__ = "interest_signups"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=lambda: datetime.now(timezone.utc))


def init_db() -> None:
    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def save_item(db: Session, user_id: str, access_token: str) -> None:
    existing = db.scalar(select(Item).where(Item.user_id == user_id))
    encrypted = encrypt(access_token)
    if existing:
        existing.access_token_encrypted = encrypted
    else:
        db.add(Item(user_id=user_id, access_token_encrypted=encrypted))
    db.commit()


def get_access_token(db: Session, user_id: str) -> Optional[str]:
    item = db.scalar(select(Item).where(Item.user_id == user_id))
    return decrypt(item.access_token_encrypted) if item else None


def delete_item(db: Session, user_id: str) -> Optional[str]:
    """Removes the linked Item for user_id, returning its decrypted access
    token (so the caller can revoke it with Plaid before it's gone locally),
    or None if there wasn't one."""
    item = db.scalar(select(Item).where(Item.user_id == user_id))
    if item is None:
        return None
    access_token = decrypt(item.access_token_encrypted)
    db.delete(item)
    db.commit()
    return access_token


def delete_transactions_for_user(db: Session, user_id: str) -> int:
    result = db.execute(delete(TransactionRecord).where(TransactionRecord.user_id == user_id))
    db.commit()
    return result.rowcount


def delete_transactions_by_ids(db: Session, user_id: str, transaction_ids: list[str]) -> int:
    """Removes transactions Plaid has reported as reversed/cancelled (sync's "removed"
    list) so a real account doesn't keep showing them after the bank has retracted them."""
    if not transaction_ids:
        return 0
    result = db.execute(
        delete(TransactionRecord).where(
            TransactionRecord.user_id == user_id,
            TransactionRecord.transaction_id.in_(transaction_ids),
        )
    )
    db.commit()
    return result.rowcount


def record_production_link(db: Session, user_id: str) -> None:
    """Idempotent per user_id - a repeat link (e.g. disconnect then reconnect
    the same account) is a no-op here, so this app's own connection-limit
    counter reflects distinct accounts that have ever used a slot, not raw
    link events. Plaid's real Trial-plan quota is a separate, external fact
    this can't change - relinking the same account still consumes a fresh
    slot on Plaid's side every time, since Plaid never frees one back up on
    disconnect. What this fixes is this app's own guardrail undercounting
    headroom for genuinely new accounts because of one account's churn."""
    existing = db.scalar(select(ProductionLinkEvent).where(ProductionLinkEvent.user_id == user_id))
    if existing is not None:
        return
    db.add(ProductionLinkEvent(user_id=user_id))
    db.commit()


def count_production_links(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(ProductionLinkEvent)) or 0


def upsert_transactions(db: Session, user_id: str, categorized_transactions: list[dict]) -> int:
    """categorized_transactions: dicts with transaction_id, date, name,
    merchant_name, amount, category (already run through categorize_transaction)."""
    count = 0
    for txn in categorized_transactions:
        existing = db.get(TransactionRecord, txn["transaction_id"])
        if existing:
            existing.date = str(txn["date"])
            existing.name = txn["name"]
            existing.merchant_name = txn.get("merchant_name")
            existing.amount = txn["amount"]
            existing.category = txn["category"]
        else:
            db.add(
                TransactionRecord(
                    transaction_id=txn["transaction_id"],
                    user_id=user_id,
                    date=str(txn["date"]),
                    name=txn["name"],
                    merchant_name=txn.get("merchant_name"),
                    amount=txn["amount"],
                    category=txn["category"],
                )
            )
        count += 1
    db.commit()
    return count


def get_transactions(
    db: Session,
    user_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    category: Optional[str] = None,
) -> list[TransactionRecord]:
    query = select(TransactionRecord).where(TransactionRecord.user_id == user_id)
    if start_date:
        query = query.where(TransactionRecord.date >= start_date)
    if end_date:
        query = query.where(TransactionRecord.date <= end_date)
    if category:
        query = query.where(TransactionRecord.category == category)
    return list(db.scalars(query.order_by(TransactionRecord.date.desc())))


def set_budget(db: Session, user_id: str, category: str, amount: float) -> BudgetRecord:
    existing = db.scalar(
        select(BudgetRecord).where(BudgetRecord.user_id == user_id, BudgetRecord.category == category)
    )
    if existing:
        existing.amount = amount
    else:
        existing = BudgetRecord(user_id=user_id, category=category, amount=amount)
        db.add(existing)
    db.commit()
    db.refresh(existing)
    return existing


def get_budgets(db: Session, user_id: str) -> dict[str, float]:
    rows = db.scalars(select(BudgetRecord).where(BudgetRecord.user_id == user_id))
    return {row.category: row.amount for row in rows}


def create_goal(
    db: Session,
    user_id: str,
    name: str,
    target_amount: float,
    category: str,
    monthly_savings_capacity: float,
    target_date: Optional[str] = None,
    current_saved: float = 0.0,
) -> GoalRecord:
    goal = GoalRecord(
        user_id=user_id,
        name=name,
        target_amount=target_amount,
        category=category,
        monthly_savings_capacity=monthly_savings_capacity,
        target_date=target_date,
        current_saved=current_saved,
    )
    db.add(goal)
    db.commit()
    db.refresh(goal)
    return goal


def get_goals(db: Session, user_id: str, status: Optional[str] = None) -> list[GoalRecord]:
    query = select(GoalRecord).where(GoalRecord.user_id == user_id)
    if status:
        query = query.where(GoalRecord.status == status)
    return list(db.scalars(query.order_by(GoalRecord.created_at.desc())))


def get_goal(db: Session, user_id: str, goal_id: int) -> Optional[GoalRecord]:
    return db.scalar(select(GoalRecord).where(GoalRecord.user_id == user_id, GoalRecord.id == goal_id))


def update_goal(db: Session, user_id: str, goal_id: int, **fields) -> Optional[GoalRecord]:
    goal = get_goal(db, user_id, goal_id)
    if goal is None:
        return None
    for key, value in fields.items():
        setattr(goal, key, value)
    db.commit()
    db.refresh(goal)
    return goal


def abandon_goal(db: Session, user_id: str, goal_id: int) -> Optional[GoalRecord]:
    return update_goal(db, user_id, goal_id, status="abandoned")


def add_interest_signup(db: Session, email: str) -> bool:
    """Records an email for the "get notified" form. Returns False without
    erroring on a duplicate - resubmitting the same email is a no-op, not a
    failure the visitor needs to see."""
    existing = db.scalar(select(InterestSignup).where(InterestSignup.email == email))
    if existing is not None:
        return False
    db.add(InterestSignup(email=email))
    db.commit()
    return True
