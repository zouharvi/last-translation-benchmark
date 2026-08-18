"""Convert ISO JSON tables into line-oriented files for OpenAI file search."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TABLE_DIR = ROOT / "data" / "language_tags" / "tables"
RAW_TABLE_DIR = TABLE_DIR / "raw"
SEARCH_DIR = TABLE_DIR / "search"


def clean(value: object) -> str:
    return str(value).replace("\n", " ").replace("|", "/").strip()


def convert(source_name: str, root_key: str, standard: str, fields: list[str]) -> None:
    source = RAW_TABLE_DIR / source_name
    records = json.loads(source.read_text(encoding="utf-8"))[root_key]
    lines = [
        " | ".join(
            [f"standard={standard}"]
            + [f"{field}={clean(record[field])}" for field in fields if record.get(field)]
        )
        for record in records
    ]
    target = SEARCH_DIR / source.with_suffix(".txt").name
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {len(lines):,} records to {target.relative_to(ROOT)}")


def main() -> None:
    SEARCH_DIR.mkdir(parents=True, exist_ok=True)
    convert(
        "iso6393.json",
        "639-3",
        "ISO 639-3 language",
        ["alpha_3", "alpha_2", "name", "inverted_name", "bibliographic", "scope", "type"],
    )
    convert(
        "iso15924.json",
        "15924",
        "ISO 15924 script",
        ["alpha_4", "name", "numeric"],
    )
    convert(
        "iso31661.json",
        "3166-1",
        "ISO 3166-1 region",
        ["alpha_2", "alpha_3", "name", "official_name", "numeric"],
    )


if __name__ == "__main__":
    main()
