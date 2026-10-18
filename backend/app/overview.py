import json

import httpx

from app import config


async def generate(result: dict) -> dict:
    # Only validated event text is sent; evidence images and internal scores stay out.
    facts = {"verdict": result["verdict"], "violations": [
        {k: v[k] for k in ("type", "timecode_sec", "description")} for v in result["violations"]]}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(f"{config.VLM_BASE_URL}/chat/completions", json={
            **config.VLM_EXTRA_BODY, "model": config.VLM_MODEL, "temperature": 0,
            "max_tokens": 300, "messages": [
                {"role": "system", "content": "Кратко обобщи результат анализа видео по-русски. "
                 "Не меняй вердикт, не добавляй событий и фактов. Отсутствие найденных признаков "
                 "не доказывает отсутствие нарушений. Верни только обычный текст обзора."},
                {"role": "user", "content": json.dumps(facts, ensure_ascii=False)},
            ],
        })
        response.raise_for_status()
        summary = response.json()["choices"][0]["message"]["content"].strip()
        if not summary:
            raise ValueError("empty overview")
    return {"summary": summary, "limitations": result.get("limitations", [])}
