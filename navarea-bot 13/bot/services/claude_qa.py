"""
Q&A ассистент на Claude. Два режима:
  - ask(question)              свободный вопрос по морской тематике
  - explain_warning(raw_text)  разбор конкретного текста NAVAREA/NAVTEX простым языком

По умолчанию используется Claude Haiku 4.5 -- он в разы дешевле Sonnet/Opus
и с запасом хватает для вопросов такого рода, а при 100+ активных
подписчиках разница в счёте за API становится ощутимой. Модель можно
поменять в .env (CLAUDE_MODEL), например на claude-sonnet-5 если понадобится
более глубокое рассуждение.
"""
from __future__ import annotations

from anthropic import AsyncAnthropic

SYSTEM_PROMPT = """Ты -- ассистент внутри Telegram-бота для моряков (второй помощник капитана \
и другие члены экипажа торгового флота). Отвечай по-русски, кратко и по делу, без вежливых \
предисловий. Тематика: судовождение, NAVAREA/NAVTEX предупреждения, ИМО-требования, погода, \
портовые формальности, жизнь на судне.

Правила:
- Если вопрос касается конкретного маршрута/позиции судна, а данных нет -- прямо скажи, \
чего не хватает, и дай общий ответ по существу.
- Если тебя просят разобрать текст предупреждения NAVAREA/NAVTEX -- переведи суть простым \
языком: что произошло, где (перескажи координаты словами, не выдумывай новых), чем опасно, \
что делать судоводителю. Не сокращай числовые координаты и даты, они должны остаться точными.
- Всегда напоминай, если это уместно, что бот не заменяет получение MSI через штатное \
оборудование GMDSS/NAVTEX -- это только вспомогательный инструмент.
- Не выдумывай факты (номера предупреждений, даты, регламенты) если не уверен -- лучше \
скажи, что стоит свериться с первоисточником.
"""

EXPLAIN_PROMPT_TEMPLATE = """Разбери это предупреждение простым языком для судоводителя:

---
{warning_text}
---

Формат ответа:
1. Суть (1-2 предложения)
2. Где именно (своими словами, координаты сохрани точно)
3. Что делать / на что обратить внимание
"""


class ClaudeQA:
    def __init__(self, api_key: str, model: str, max_tokens: int = 700):
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._max_tokens = max_tokens

    async def ask(self, question: str, history: list[dict] | None = None) -> str:
        messages = list(history or [])
        messages.append({"role": "user", "content": question})
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        return _extract_text(response)

    async def explain_warning(self, warning_text: str) -> str:
        prompt = EXPLAIN_PROMPT_TEMPLATE.format(warning_text=warning_text.strip())
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return _extract_text(response)


def _extract_text(response) -> str:
    parts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    return "\n".join(parts).strip() or "Не получилось сформировать ответ, попробуй переформулировать вопрос."
