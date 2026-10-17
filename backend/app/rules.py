import json
from functools import lru_cache

from app.config import RULES_PATH


@lru_cache
def catalog() -> dict:
    return json.loads(RULES_PATH.read_text(encoding="utf-8"))


def rules() -> list[dict]:
    return catalog()["rules"]


def rule_ids() -> list[str]:
    return [r["id"] for r in rules()]


def rule(rule_id: str) -> dict:
    return next(r for r in rules() if r["id"] == rule_id)


def citation(rule_id: str) -> dict:
    r = rule(rule_id)
    src = catalog()["sources"].get(r["source"]) if r["source"] else None
    return {
        "id": r["id"],
        "code": r.get("code"),
        "document": src["title"] if src else None,
        "clause": r["clause"],
        "requirement": r.get("requirement"),
        "interpretation": r.get("interpretation", False),
        "url": src["url"] if src else None,
    }


def citation_text(rule_id: str) -> str:
    r = rule(rule_id)
    src = catalog()["sources"].get(r["source"]) if r["source"] else None
    if not src:
        return "Нормативный источник не подтверждён."
    ref = f"{src['title']}, {r['clause']}" if r["clause"] else src["title"]
    text = f"{ref}: {r['requirement']}." if r.get("requirement") else f"{ref}."
    return text + (" Норма прямо не описывает это действие и применена по смыслу." if r.get("interpretation") else "")


def prompt_block() -> str:
    return "\n".join(f"- {r['id']}: {r['visual']}" for r in rules())
