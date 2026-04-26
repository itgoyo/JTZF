import os
import asyncio
import logging

from telethon import Button
from telethon.tl import types

from handlers.button.button_helpers import create_ai_tag_settings_buttons, create_model_buttons
from models.models import ForwardRule
from managers.state_manager import state_manager
from utils.common import is_admin

logger = logging.getLogger(__name__)

# ─────────────────────────── helpers ────────────────────────────

async def cancel_state_after_timeout(user_id: int, chat_id: int, timeout_minutes: int = 5):
    await asyncio.sleep(timeout_minutes * 60)
    current_state, _, _ = state_manager.get_state(user_id, chat_id)
    if current_state:
        logger.info(f'[ai_tag] 状态超时自动取消 - user_id: {user_id}, chat_id: {chat_id}')
        state_manager.clear_state(user_id, chat_id)


def _get_ai_tag_text(rule: ForwardRule) -> str:
    model = rule.ai_tag_model or os.getenv('DEFAULT_AI_MODEL', '默认')
    enabled = '✅ 开启' if rule.enable_ai_tag else '❌ 关闭'
    return (
        f'🏷️ AI自动打标签设置\n\n'
        f'开关: {enabled}\n'
        f'使用模型: {model}\n'
        f'最多标签数: {rule.ai_tag_max_count or 3}\n'
        f'最短触发字数: {rule.ai_tag_min_length or 100}'
    )


# ─────────────────────────── page entry ────────────────────────────

async def callback_ai_tag_settings(event, rule_id, session, message, data):
    """显示 AI 标签设置页面"""
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            await event.edit(_get_ai_tag_text(rule), buttons=await create_ai_tag_settings_buttons(rule))
    finally:
        session.close()


# ─────────────────────────── toggle on/off ────────────────────────────

async def callback_toggle_ai_tag(event, rule_id, session, message, data):
    """切换 AI 标签开关"""
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if not rule:
            await event.answer('规则不存在')
            return
        rule.enable_ai_tag = not rule.enable_ai_tag
        session.commit()
        status = '已开启' if rule.enable_ai_tag else '已关闭'
        await event.answer(f'AI自动打标签 {status}')
        await event.edit(_get_ai_tag_text(rule), buttons=await create_ai_tag_settings_buttons(rule))
    finally:
        session.close()


# ─────────────────────────── model selection ────────────────────────────

async def callback_change_ai_tag_model(event, rule_id, session, message, data):
    """打开模型选择页面（复用现有 create_model_buttons，使用 ai_tag 专属 prefix）"""
    try:
        buttons = await create_model_buttons(rule_id, page=0, prefix='select_ai_tag_model')
        await event.edit('请选择AI标签使用的模型：', buttons=buttons)
    finally:
        session.close()


async def callback_select_ai_tag_model(event, rule_id, session, message, data):
    """确认选择的模型"""
    # data 格式: select_ai_tag_model:<rule_id>:<model_name>
    parts = data.split(':', 2)
    if len(parts) != 3:
        await event.answer('参数错误')
        session.close()
        return
    _, rid, model = parts
    try:
        rule = session.query(ForwardRule).get(int(rid))
        if not rule:
            await event.answer('规则不存在')
            return
        rule.ai_tag_model = model
        session.commit()
        await event.answer(f'AI标签模型已设置为: {model}')
        await event.edit(_get_ai_tag_text(rule), buttons=await create_ai_tag_settings_buttons(rule))
    finally:
        session.close()


# ─────────────────────────── max count ────────────────────────────

async def callback_set_ai_tag_max_count(event, rule_id, session, message, data):
    """提示用户输入最多标签数"""
    rule = session.query(ForwardRule).get(int(rule_id))
    if not rule:
        await event.answer('规则不存在')
        session.close()
        return

    if isinstance(event.chat, types.Channel):
        if not await is_admin(event):
            await event.answer('只有管理员可以修改设置')
            session.close()
            return
        user_id = os.getenv('USER_ID')
    else:
        user_id = event.sender_id

    chat_id = abs(event.chat_id)
    state = f'set_ai_tag_max_count:{rule_id}'
    state_manager.set_state(user_id, chat_id, state, message, state_type='ai_tag')
    asyncio.create_task(cancel_state_after_timeout(user_id, chat_id))

    try:
        await message.edit(
            f'请输入最多标签数（1-10）\n'
            f'当前规则ID: `{rule_id}`\n'
            f'当前值: {rule.ai_tag_max_count or 3}\n\n'
            f'5分钟内未设置将自动取消',
            buttons=[[Button.inline('取消', f'cancel_ai_tag_input:{rule_id}')]]
        )
    finally:
        session.close()


# ─────────────────────────── min length ────────────────────────────

async def callback_set_ai_tag_min_length(event, rule_id, session, message, data):
    """提示用户输入最短触发字数"""
    rule = session.query(ForwardRule).get(int(rule_id))
    if not rule:
        await event.answer('规则不存在')
        session.close()
        return

    if isinstance(event.chat, types.Channel):
        if not await is_admin(event):
            await event.answer('只有管理员可以修改设置')
            session.close()
            return
        user_id = os.getenv('USER_ID')
    else:
        user_id = event.sender_id

    chat_id = abs(event.chat_id)
    state = f'set_ai_tag_min_length:{rule_id}'
    state_manager.set_state(user_id, chat_id, state, message, state_type='ai_tag')
    asyncio.create_task(cancel_state_after_timeout(user_id, chat_id))

    try:
        await message.edit(
            f'请输入最短触发字数（如100）\n'
            f'当前规则ID: `{rule_id}`\n'
            f'当前值: {rule.ai_tag_min_length or 100}\n\n'
            f'5分钟内未设置将自动取消',
            buttons=[[Button.inline('取消', f'cancel_ai_tag_input:{rule_id}')]]
        )
    finally:
        session.close()


# ─────────────────────────── cancel ────────────────────────────

async def callback_cancel_ai_tag_input(event, rule_id, session, message, data):
    """取消输入状态并回到 AI 标签设置页"""
    try:
        if isinstance(event.chat, types.Channel):
            user_id = os.getenv('USER_ID')
        else:
            user_id = event.sender_id
        state_manager.clear_state(user_id, abs(event.chat_id))

        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            await event.edit(_get_ai_tag_text(rule), buttons=await create_ai_tag_settings_buttons(rule))
    finally:
        session.close()
