"""Integration tests: ledger posting invariants (real PostgreSQL)."""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domains.identity.models import Role
from app.domains.identity.service import create_user, ensure_default_company
from app.domains.ledger.models import (
    AccountType,
    JournalEntry,
    JournalStatus,
    PeriodAction,
    PeriodEvent,
    PeriodStatus,
)
from app.domains.ledger.service import (
    LedgerError,
    close_period,
    create_account,
    create_draft_entry,
    get_period,
    post_entry,
    reopen_period,
    seed_chart_of_accounts,
    void_entry,
)

ENTRY_DATE = dt.date(2026, 8, 13)  # 1405/05/22


@pytest.fixture
def company(db: Session) -> int:
    return ensure_default_company(db).id


@pytest.fixture
def actor(db: Session) -> int:
    user = create_user(
        db,
        email="acct-ledger@example.com",
        full_name="حسابدار",
        password="test-pass-12345",
        role=Role.ACCOUNTANT,
    )
    db.commit()
    return user.id


@pytest.fixture
def chart(db: Session, company: int) -> None:
    seed_chart_of_accounts(db, company)
    db.commit()


def _draft(db: Session, company: int, actor_id: int, **kw):
    return create_draft_entry(
        db,
        company_id=company,
        actor_id=actor_id,
        entry_date=kw.get("entry_date", ENTRY_DATE),
        memo=kw.get("memo", "هزینه اداری"),
        lines=kw.get("lines", [("603", 48_500_000, 0), ("102", 0, 48_500_000)]),
        idempotency_key=kw.get("idempotency_key"),
    )


class TestChartOfAccounts:
    def test_starter_chart_seeded(self, db: Session, company: int) -> None:
        assert seed_chart_of_accounts(db, company) == 13
        assert seed_chart_of_accounts(db, company) == 0  # idempotent

    def test_create_account(self, db: Session, company: int) -> None:
        acc = create_account(db, company, "103", "بانک سپرده", AccountType.ASSET, None)
        assert acc.code == "103" and acc.type.value == "asset"

    def test_duplicate_code_rejected(self, db: Session, company: int) -> None:
        create_account(db, company, "103", "یک", AccountType.ASSET, None)
        with pytest.raises(LedgerError) as exc:
            create_account(db, company, "103", "دو", AccountType.LIABILITY, None)
        assert exc.value.status_code == 409

    def test_parent_lookup(self, db: Session, company: int) -> None:
        create_account(db, company, "100", "دارایی‌ها", AccountType.ASSET, None)
        child = create_account(db, company, "101", "صندوق", AccountType.ASSET, "100")
        assert child.parent_id is not None


class TestPosting:
    def test_post_balanced_entry(self, db: Session, company: int, actor: int, chart: None) -> None:
        entry = _draft(db, company, actor)
        posted = post_entry(db, company, entry.id, actor)
        assert posted.status == JournalStatus.POSTED
        assert posted.reference == "J-1405-0001"
        assert posted.posted_by_id == actor
        assert posted.posted_at is not None

    def test_unbalanced_entry_rejected(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        entry = _draft(db, company, actor, lines=[("603", 50_000_000, 0), ("102", 0, 48_500_000)])
        with pytest.raises(LedgerError) as exc:
            post_entry(db, company, entry.id, actor)
        assert exc.value.code == "unbalanced_entry"
        # nothing was posted
        fresh = db.get(JournalEntry, entry.id)
        assert fresh.status == JournalStatus.DRAFT
        assert fresh.reference is None

    def test_zero_amount_entry_rejected(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        with pytest.raises(LedgerError) as exc:
            _draft(db, company, actor, lines=[("603", 0, 0), ("102", 0, 0)])
        assert exc.value.code == "line_invalid"

    def test_double_sided_line_rejected(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        with pytest.raises(LedgerError) as exc:
            _draft(db, company, actor, lines=[("603", 100, 100), ("102", 0, 0)])
        assert exc.value.code == "line_invalid"

    def test_unknown_account_rejected(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        with pytest.raises(LedgerError) as exc:
            _draft(db, company, actor, lines=[("999", 100, 0), ("102", 0, 100)])
        assert exc.value.code == "account_missing"

    def test_inactive_account_rejected(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        from app.domains.ledger.models import Account

        acc = db.scalar(select(Account).where(Account.code == "603"))
        assert acc is not None
        acc.is_active = False
        db.flush()
        with pytest.raises(LedgerError) as exc:
            _draft(db, company, actor, lines=[("603", 100, 0), ("102", 0, 100)])
        assert exc.value.code == "account_inactive"

    def test_references_sequential_per_period(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        e1 = post_entry(db, company, _draft(db, company, actor).id, actor)
        e2 = post_entry(db, company, _draft(db, company, actor).id, actor)
        assert (e1.reference, e2.reference) == ("J-1405-0001", "J-1405-0002")

    def test_references_reset_per_period(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        post_entry(db, company, _draft(db, company, actor).id, actor)
        # Same jalali period -> continues; a different month starts a new sequence.
        e_other = post_entry(
            db,
            company,
            _draft(db, company, actor, entry_date=dt.date(2026, 4, 10)).id,  # 1405/01/21
            actor,
        )
        assert e_other.reference == "J-1405-0001"

    def test_posted_entry_immutable_reference(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        posted = post_entry(db, company, _draft(db, company, actor).id, actor)
        # No service path mutates a posted entry; double-post is rejected.
        with pytest.raises(LedgerError) as exc:
            post_entry(db, company, posted.id, actor)
        assert exc.value.code == "entry_already_posted"


class TestIdempotency:
    def test_idempotency_key_prevents_duplicate(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        key = "expense-2026-08-13-1"
        e1 = post_entry(db, company, _draft(db, company, actor, idempotency_key=key).id, actor)
        e2 = post_entry(db, company, _draft(db, company, actor, idempotency_key=key).id, actor)
        assert e1.id == e2.id
        count = len(
            list(db.scalars(select(JournalEntry).where(JournalEntry.company_id == company)))
        )
        assert count == 1


class TestVoid:
    def test_void_creates_balanced_reversal(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        posted = post_entry(db, company, _draft(db, company, actor).id, actor)
        reversal = void_entry(db, company, posted.id, actor)
        assert reversal.status == JournalStatus.POSTED
        assert reversal.reversal_of_id == posted.id
        # mirror lines: debit/credit swapped
        original = {(ln.account.code, ln.debit, ln.credit) for ln in posted.lines}
        mirrored = {(ln.account.code, ln.credit, ln.debit) for ln in reversal.lines}
        assert mirrored == original
        # original unchanged
        fresh = db.get(JournalEntry, posted.id)
        assert fresh.reference == posted.reference
        assert fresh.status == JournalStatus.POSTED

    def test_void_draft_rejected(self, db: Session, company: int, actor: int, chart: None) -> None:
        draft = _draft(db, company, actor)
        with pytest.raises(LedgerError) as exc:
            void_entry(db, company, draft.id, actor)
        assert exc.value.code == "entry_not_posted"

    def test_void_reversal_again_rejected(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        posted = post_entry(db, company, _draft(db, company, actor).id, actor)
        reversal = void_entry(db, company, posted.id, actor)
        with pytest.raises(LedgerError) as exc:
            void_entry(db, company, reversal.id, actor)
        assert exc.value.code == "entry_is_reversal"

    def test_second_reversal_of_original_rejected(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        posted = post_entry(db, company, _draft(db, company, actor).id, actor)
        void_entry(db, company, posted.id, actor)
        with pytest.raises(LedgerError) as exc:
            void_entry(db, company, posted.id, actor)
        assert exc.value.code == "entry_already_reversed"
        assert exc.value.status_code == 409

    def test_entry_mutations_are_company_scoped(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        from app.domains.identity.models import Company

        other = Company(name="شرکت دیگر", fiscal_year_start=1405)
        db.add(other)
        db.flush()
        draft = _draft(db, company, actor)
        with pytest.raises(LedgerError) as exc:
            post_entry(db, other.id, draft.id, actor)
        assert exc.value.code == "entry_missing"


class TestPeriods:
    def test_post_into_closed_period_rejected(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        period = get_period(db, company, 1405, 5)
        close_period(db, company, period.id, actor)
        db.commit()
        draft = _draft(db, company, actor)  # 1405/05/22
        with pytest.raises(LedgerError) as exc:
            post_entry(db, company, draft.id, actor)
        assert exc.value.code == "period_closed"

    def test_post_into_open_period_ok(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        draft = _draft(db, company, actor)
        assert post_entry(db, company, draft.id, actor).status == JournalStatus.POSTED

    def test_close_and_reopen_recorded(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        period = get_period(db, company, 1405, 5)
        close_period(db, company, period.id, actor)
        db.flush()
        assert period.status == PeriodStatus.CLOSED
        events = list(db.scalars(select(PeriodEvent).where(PeriodEvent.period_id == period.id)))
        assert [e.action for e in events] == [PeriodAction.CLOSE]

        reopen_period(db, company, period.id, actor)
        db.flush()
        assert period.status == PeriodStatus.OPEN
        events = list(db.scalars(select(PeriodEvent).where(PeriodEvent.period_id == period.id)))
        assert [e.action for e in events] == [PeriodAction.CLOSE, PeriodAction.REOPEN]
        assert events[1].actor_id == actor

    def test_close_closed_period_rejected(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        period = get_period(db, company, 1405, 5)
        close_period(db, company, period.id, actor)
        with pytest.raises(LedgerError) as exc:
            close_period(db, company, period.id, actor)
        assert exc.value.code == "period_already_closed"

    def test_reopen_open_period_rejected(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        period = get_period(db, company, 1405, 5)
        with pytest.raises(LedgerError) as exc:
            reopen_period(db, company, period.id, actor)
        assert exc.value.code == "period_already_open"

    def test_period_rows_are_independent(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        m5 = get_period(db, company, 1405, 5)
        m6 = get_period(db, company, 1405, 6)
        close_period(db, company, m5.id, actor)
        db.flush()
        assert m5.status == PeriodStatus.CLOSED
        assert m6.status == PeriodStatus.OPEN


class TestCoverageGaps:
    """Targeted tests for remaining service paths (parent missing, 404s,
    list filters, idempotent race, totals)."""

    def test_create_account_missing_parent(self, db: Session, company: int, actor: int) -> None:
        with pytest.raises(LedgerError) as exc:
            create_account(db, company, "111", "زیرشاخه", AccountType.ASSET, "999")
        assert exc.value.code == "account_parent_missing"

    def test_close_reopen_missing_period(self, db: Session, company: int, actor: int) -> None:
        with pytest.raises(LedgerError) as exc:
            close_period(db, company, 999_999, actor)
        assert exc.value.code == "period_missing"
        with pytest.raises(LedgerError) as exc:
            reopen_period(db, company, 999_999, actor)
        assert exc.value.code == "period_missing"

    def test_post_missing_entry(self, db: Session, company: int, actor: int) -> None:
        with pytest.raises(LedgerError) as exc:
            post_entry(db, company, 999_999, actor)
        assert exc.value.code == "entry_missing"

    def test_void_missing_entry(self, db: Session, company: int, actor: int) -> None:
        with pytest.raises(LedgerError) as exc:
            void_entry(db, company, 999_999, actor)
        assert exc.value.code == "entry_missing"

    def test_idempotency_duplicate_key_blocked_by_db(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        # The DB unique constraint is the backstop: two drafts cannot both claim
        # the same key, so the idempotency guarantee holds even under concurrency.
        import sqlalchemy.exc

        key = "race-key-1"
        _draft(db, company, actor, idempotency_key=key)
        other = _draft(db, company, actor)  # no key
        other.idempotency_key = key  # concurrent claim -> rejected
        with pytest.raises(sqlalchemy.exc.IntegrityError):
            db.flush()

    def test_list_entries_filters(self, db: Session, company: int, actor: int, chart: None) -> None:
        from app.domains.ledger.service import list_entries

        # one entry in 1405/05 and one in 1405/01
        post_entry(db, company, _draft(db, company, actor).id, actor)
        post_entry(
            db,
            company,
            _draft(db, company, actor, entry_date=dt.date(2026, 4, 10)).id,
            actor,
        )
        assert len(list_entries(db, company)) == 2
        by_year = list_entries(db, company, period_year=1405)
        assert len(by_year) == 2
        by_month = list_entries(db, company, period_year=1405, period_month=5)
        assert len(by_month) == 1
        assert by_month[0].entry_date == ENTRY_DATE
        assert list_entries(db, company, period_year=1404) == []
        assert list_entries(db, company, period_year=1405, period_month=12) == []

    def test_entry_totals(self, db: Session, company: int, actor: int, chart: None) -> None:
        from app.domains.ledger.service import entry_totals

        entry = _draft(db, company, actor)
        assert entry_totals(entry) == (48_500_000, 48_500_000)


class TestAccountBalances:
    def test_balances_from_posted_entries(
        self, db: Session, company: int, actor: int, chart: None
    ) -> None:
        from app.domains.ledger.service import account_balances

        # expense paid from bank: Dr 603 48.5M / Cr 102 48.5M
        post_entry(db, company, _draft(db, company, actor).id, actor)
        # cash sale: Dr 101 5M / Cr 401 5M
        post_entry(
            db,
            company,
            _draft(
                db,
                company,
                actor,
                memo="فروش نقدی",
                lines=[("101", 5_000_000, 0), ("401", 0, 5_000_000)],
            ).id,
            actor,
        )
        db.commit()
        balances = {b["code"]: b for b in account_balances(db, company)}
        assert balances["101"]["balance"] == 5_000_000
        assert balances["102"]["balance"] == -48_500_000
        assert balances["401"]["balance"] == 5_000_000
        assert balances["603"]["balance"] == 48_500_000
        # cash & bank = 101 + 102
        from app.domains.ledger.service import cash_and_bank_balance

        assert cash_and_bank_balance(db, company) == -43_500_000

    def test_drafts_are_excluded(self, db: Session, company: int, actor: int, chart: None) -> None:
        from app.domains.ledger.service import account_balances

        post_entry(db, company, _draft(db, company, actor).id, actor)
        _draft(db, company, actor)  # draft, never posted
        db.commit()
        balances = {b["code"]: b for b in account_balances(db, company)}
        assert balances["102"]["balance"] == -48_500_000  # draft not counted

    def test_balances_empty(self, db: Session, company: int) -> None:
        from app.domains.ledger.service import account_balances

        assert account_balances(db, company) == []
