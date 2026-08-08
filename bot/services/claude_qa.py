"""
Q&A ассистент на Claude. Три режима:
  - ask(question)              свободный вопрос по морской тематике
  - ask_agent(question, ctx)   то же, но с инструментами: модель сама берёт
                               погоду, предупреждения, карточку судна и позицию
  - explain_warning(raw_text)  разбор конкретного текста NAVAREA/NAVTEX простым языком

По умолчанию используется Claude Haiku 4.5 -- он в разы дешевле Sonnet/Opus
и с запасом хватает для вопросов такого рода, а при 100+ активных
подписчиках разница в счёте за API становится ощутимой. Модель можно
поменять в .env (CLAUDE_MODEL), например на claude-sonnet-5 если понадобится
более глубокое рассуждение.
"""
from __future__ import annotations

import logging

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

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
        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._clients: dict = {}

    @property
    def _client(self):
        """Свой клиент на каждый цикл событий.

        Бот живёт в одном цикле, а веб-сервер Mini App -- многопоточный и
        поднимает новый цикл через asyncio.run() на каждый запрос. Клиент
        httpx внутри AsyncAnthropic привязывается к тому циклу, где его
        впервые использовали, и на втором запросе валился с «Event loop is
        closed». Поэтому держим по клиенту на цикл и выбрасываем те,
        чьи циклы уже закрылись."""
        import asyncio

        loop = asyncio.get_running_loop()
        client = self._clients.get(loop)
        if client is None:
            client = AsyncAnthropic(api_key=self._api_key)
            self._clients[loop] = client
            for dead in [k for k in self._clients if k.is_closed()]:
                self._clients.pop(dead, None)
        return client

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

    async def ask_agent(self, question: str, ctx: dict | None = None,
                        history: list[dict] | None = None) -> str:
        """Вопрос с инструментами. Модель сама решает, чего ей не хватает,
        просит данные у бота и отвечает уже по ним.

        Круги ограничены: без ограничения модель на неудачном инструменте
        может ходить по кругу, а каждый круг -- это оплаченный запрос
        и лишние секунды ожидания на судовом канале."""
        from .assistant import MAX_ROUNDS, SYSTEM, TOOLS, context_note, run_tool
        from .prompts import mode_rule

        ctx = ctx or {}
        system = SYSTEM + "\n\nЧто известно и так: " + context_note(ctx)
        rule = mode_rule(ctx.get("mode"))
        if rule:
            system += "\n\nФорма ответа: " + rule
        messages: list[dict] = list(history or [])
        messages.append({"role": "user", "content": question})
        said: list[str] = []          # текст, который модель успела сказать по дороге

        for _ in range(MAX_ROUNDS):
            response = await self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                system=system,
                tools=TOOLS,
                messages=messages,
            )
            if response.stop_reason != "tool_use":
                return _extract_text(response)

            messages.append({"role": "assistant", "content": response.content})
            results = []
            for block in response.content:
                if getattr(block, "type", None) == "text" and block.text.strip():
                    said.append(block.text.strip())
                if getattr(block, "type", None) != "tool_use":
                    continue
                logger.info("Ассистент запросил %s %s", block.name, block.input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": await run_tool(block.name, block.input, ctx),
                })
            if not results:
                return _extract_text(response)
            messages.append({"role": "user", "content": results})

        # Круги кончились -- просим ответить тем, что уже собрано.
        # Просьбу дописываем в то же сообщение с результатами инструментов:
        # два сообщения подряд от роли user Messages API не принимает.
        nudge = {"type": "text",
                 "text": "Ответь по уже полученным данным, больше инструменты не вызывай."}
        last = messages[-1]
        if last["role"] == "user" and isinstance(last["content"], list):
            last["content"].append(nudge)
        else:
            messages.append({"role": "user", "content": nudge["text"]})

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=system,
            messages=messages,
        )
        text = _extract_text(response)
        # Если и последний ответ пуст -- отдаём то, что модель уже говорила
        # по ходу дела: это лучше, чем «не получилось сформировать ответ».
        if text.startswith("Не получилось") and said:
            return "\n\n".join(said)
        return text

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
