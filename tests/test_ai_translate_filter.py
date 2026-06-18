import types
from unittest.mock import AsyncMock, patch

import pytest

from filters.ai_translate_filter import AITranslateFilter


@pytest.mark.asyncio
async def test_translate_non_chinese_success():
    filter_obj = AITranslateFilter()

    rule = types.SimpleNamespace(enable_ai_translate=True)
    context = types.SimpleNamespace(rule=rule, message_text="Hello world")

    fake_provider = AsyncMock()
    fake_provider.process_message.return_value = "你好，世界"

    with patch("filters.ai_translate_filter.get_ai_provider", new=AsyncMock(return_value=fake_provider)):
        should_continue = await filter_obj._process(context)

    assert should_continue is True
    assert context.message_text == "你好，世界"


@pytest.mark.asyncio
async def test_translate_retry_then_fallback_original():
    filter_obj = AITranslateFilter()

    rule = types.SimpleNamespace(enable_ai_translate=True)
    context = types.SimpleNamespace(rule=rule, message_text="Good morning")

    fake_provider = AsyncMock()
    fake_provider.process_message.side_effect = [
        "AI处理失败: Error code: 403",
        "AI处理失败: Error code: 403",
    ]

    with patch("filters.ai_translate_filter.get_ai_provider", new=AsyncMock(return_value=fake_provider)):
        should_continue = await filter_obj._process(context)

    assert should_continue is True
    assert context.message_text == "Good morning"
