"""Native bounded local history purge. Run at least daily; never a model tool."""

import argparse

from sqlalchemy import text

from careflow.identity import IdentityError, now, transaction


def purge(*, dry_run: bool = True, limit: int = 1000, confirmed: bool = False) -> int:
    if not 1 <= limit <= 1000:
        raise ValueError("Limit must be between 1 and 1000")
    with transaction(local_confirmation=confirmed) as connection:
        rows = (
            connection.execute(
                text("""
            SELECT c.id FROM conversations c
            LEFT JOIN sessions s ON s.token_hash=c.guest_hash
            WHERE c.expires_at <= :now OR (c.guest_hash IS NOT NULL
                AND (s.token_hash IS NULL OR s.expires_at <= :now))
            ORDER BY c.expires_at,c.id LIMIT :limit FOR UPDATE OF c SKIP LOCKED
        """),
                {"now": now(), "limit": limit},
            )
            .scalars()
            .all()
        )
        if not dry_run:
            for identifier in rows:
                connection.execute(
                    text("DELETE FROM conversations WHERE id=:id"), {"id": identifier}
                )
        return len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delete", action="store_true")
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--confirm-local-synthetic", action="store_true")
    options = parser.parse_args()
    try:
        count = purge(
            dry_run=not options.delete,
            limit=options.limit,
            confirmed=options.confirm_local_synthetic,
        )
    except (IdentityError, ValueError):
        print("History purge refused or unavailable.")
        return 1
    print(
        f"{'Deleted' if options.delete else 'Eligible in batch'} conversations: {count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
