import argparse
import asyncio
import collections

from last_translation_benchmark.db import (
    get_submissions,
    get_users,
    init_db,
    save_submission,
    save_user,
)
from last_translation_benchmark.languages import canonicalize_language


async def migrate(apply: bool):
    await init_db()
    submissions = await get_submissions()
    users = await get_users()

    renames: collections.Counter = collections.Counter()

    subs_updated = 0
    for sub in submissions:
        changed = False
        for field in ("source_lang", "target_lang"):
            old = sub.get(field)
            if not old:
                continue
            new = canonicalize_language(old)
            if new != old:
                renames[(old, new)] += 1
                sub[field] = new
                changed = True
        if changed:
            subs_updated += 1
            if apply:
                await save_submission(sub)

    # A reviewer scoped to "Persian" is matched against the submission language
    # by substring, so a stale scope name silently stops routing work to them.
    users_updated = 0
    for user in users:
        review_langs = user.get("review_langs") or []
        new_langs = [canonicalize_language(x) for x in review_langs]
        # dedupe while keeping the reviewer's order
        new_langs = list(dict.fromkeys(new_langs))
        if new_langs != review_langs:
            for old, new in zip(review_langs, new_langs, strict=False):
                if old != new:
                    renames[(old, new)] += 1
            user["review_langs"] = new_langs
            users_updated += 1
            if apply:
                await save_user(user)

    for (old, new), count in renames.most_common():
        print(f"{count:5}  {old!r} -> {new!r}")
    verb = "Updated" if apply else "Would update"
    print(f"{verb} {subs_updated} submission(s) and {users_updated} user(s).")
    if not apply:
        print("Dry run. Re-run with --apply to write.")


if __name__ == "__main__":
    args = argparse.ArgumentParser()
    args.add_argument("--apply", action="store_true")
    args = args.parse_args()
    asyncio.run(migrate(args.apply))
