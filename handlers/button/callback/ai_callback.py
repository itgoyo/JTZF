import os
import traceback
from managers.state_manager import state_manager
import asyncio
from telethon.tl import types

from handlers.button.button_helpers import create_ai_settings_buttons, create_model_buttons, create_summary_time_buttons, create_ai_enhance_settings_buttons
from models.models import ForwardRule, RuleSync
from telethon import Button
import logging
from utils.common import get_main_module, get_ai_settings_text, get_ai_enhance_settings_text
from utils.common import is_admin
from scheduler.summary_scheduler import SummaryScheduler
from utils.constants import DEFAULT_AI_MODEL


logger = logging.getLogger(__name__)


def _resolve_state_user_id(event):
    """统一状态管理中的 user_id 取值，兼容频道场景。"""
    chat = getattr(event, 'chat', None)
    if isinstance(chat, types.Channel):
        return os.getenv('USER_ID')
    return event.sender_id


async def callback_ai_settings(event, rule_id, session, message, data):
    # 显示 AI 设置页面
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            await event.edit(await get_ai_settings_text(rule), buttons=await create_ai_settings_buttons(rule))
    finally:
        session.close()
    return



async def callback_set_summary_time(event, rule_id, session, message, data):
    await event.edit("请选择总结时间：", buttons=await create_summary_time_buttons(rule_id, page=0))
    return

async def callback_set_summary_prompt(event, rule_id, session, message, data):
    """处理设置AI总结提示词的回调"""
    logger.info(f"开始处理设置AI总结提示词回调 - event: {event}, rule_id: {rule_id}")
    
    rule = session.query(ForwardRule).get(rule_id)
    if not rule:
        await event.answer('规则不存在')
        return

    # 检查是否频道消息
    if isinstance(event.chat, types.Channel):
        # 检查是否是管理员
        if not await is_admin(event):
            await event.answer('只有管理员可以修改设置')
            return
        user_id = os.getenv('USER_ID')
    else:
        user_id = event.sender_id

    chat_id = abs(event.chat_id)
    state = f"set_summary_prompt:{rule_id}"
    
    logger.info(f"准备设置状态 - user_id: {user_id}, chat_id: {chat_id}, state: {state}")
    try:
        state_manager.set_state(user_id, chat_id, state, message, state_type="ai")
        # 启动超时取消任务
        asyncio.create_task(cancel_state_after_timeout(user_id, chat_id))
        logger.info("状态设置成功")
    except Exception as e:
        logger.error(f"设置状态时出错: {str(e)}")
        logger.exception(e)

    try:
        current_prompt = rule.summary_prompt or os.getenv('DEFAULT_SUMMARY_PROMPT', '未设置')
        await message.edit(
            f"请发送新的AI总结提示词\n"
            f"当前规则ID: `{rule_id}`\n"
            f"当前AI总结提示词：\n\n`{current_prompt}`\n\n"
            f"5分钟内未设置将自动取消",
            buttons=[[Button.inline("取消", f"cancel_set_summary:{rule_id}")]]
        )
        logger.info("消息编辑成功")
    except Exception as e:
        logger.error(f"编辑消息时出错: {str(e)}")
        logger.exception(e)


async def cancel_state_after_timeout(user_id: int, chat_id: int, timeout_minutes: int = 5):
    """在指定时间后自动取消状态"""
    await asyncio.sleep(timeout_minutes * 60)
    current_state, _, _ = state_manager.get_state(user_id, chat_id)
    if current_state:  # 只有当状态还存在时才清除
        logger.info(f"状态超时自动取消 - user_id: {user_id}, chat_id: {chat_id}")
        state_manager.clear_state(user_id, chat_id)


async def callback_set_ai_prompt(event, rule_id, session, message, data):
    """处理设置AI提示词的回调"""
    logger.info(f"开始处理设置AI提示词回调 - event: {event}, rule_id: {rule_id}")

    rule = session.query(ForwardRule).get(rule_id)
    if not rule:
        await event.answer('规则不存在')
        return

    # 检查是否频道消息
    if isinstance(event.chat, types.Channel):
        # 检查是否是管理员
        if not await is_admin(event):
            await event.answer('只有管理员可以修改设置')
            return
        user_id = os.getenv('USER_ID')
    else:
        user_id = event.sender_id

    chat_id = abs(event.chat_id)
    state = f"set_ai_prompt:{rule_id}"

    logger.info(f"准备设置状态 - user_id: {user_id}, chat_id: {chat_id}, state: {state}")
    try:
        state_manager.set_state(user_id, chat_id, state, message, state_type="ai")
        # 启动超时取消任务
        asyncio.create_task(cancel_state_after_timeout(user_id, chat_id))
        logger.info("状态设置成功")
    except Exception as e:
        logger.error(f"设置状态时出错: {str(e)}")
        logger.exception(e)

    try:
        current_prompt = rule.ai_prompt or os.getenv('DEFAULT_AI_PROMPT', '未设置')
        await message.edit(
            f"请发送新的AI提示词\n"
            f"当前规则ID: `{rule_id}`\n"
            f"当前AI提示词：\n\n`{current_prompt}`\n\n"
            f"5分钟内未设置将自动取消",
            buttons=[[Button.inline("取消", f"cancel_set_prompt:{rule_id}")]]
        )
        logger.info("消息编辑成功")
    except Exception as e:
        logger.error(f"编辑消息时出错: {str(e)}")
        logger.exception(e)


   
            

async def callback_time_page(event, rule_id, session, message, data):
    _, rule_id, page = data.split(':')
    page = int(page)
    await event.edit("请选择总结时间：", buttons=await create_summary_time_buttons(rule_id, page=page))
    return


async def callback_select_time(event, rule_id, session, message, data):
    parts = data.split(':', 2)  # 最多分割2次
    if len(parts) == 3:
        _, rule_id, time = parts
        logger.info(f"设置规则 {rule_id} 的总结时间为: {time}")
        try:
            rule = session.query(ForwardRule).get(int(rule_id))
            if rule:
                # 记录旧时间
                old_time = rule.summary_time

                # 更新时间
                rule.summary_time = time
                session.commit()
                logger.info(f"数据库更新成功: {old_time} -> {time}")
                
                # 检查是否启用了同步功能
                if rule.enable_sync:
                    logger.info(f"规则 {rule.id} 启用了同步功能，正在同步总结时间设置到关联规则")
                    # 获取需要同步的规则列表
                    sync_rules = session.query(RuleSync).filter(RuleSync.rule_id == rule.id).all()
                    
                    # 为每个同步规则应用相同的总结时间设置
                    for sync_rule in sync_rules:
                        sync_rule_id = sync_rule.sync_rule_id
                        logger.info(f"正在同步总结时间到规则 {sync_rule_id}")
                        
                        # 获取同步目标规则
                        target_rule = session.query(ForwardRule).get(sync_rule_id)
                        if not target_rule:
                            logger.warning(f"同步目标规则 {sync_rule_id} 不存在，跳过")
                            continue
                        
                        # 更新同步目标规则的总结时间设置
                        try:
                            # 记录旧时间
                            old_target_time = target_rule.summary_time
                            
                            # 设置新时间
                            target_rule.summary_time = time
                            
                            # 如果目标规则启用了总结功能，也更新它的调度
                            if target_rule.is_summary:
                                logger.info(f"目标规则 {sync_rule_id} 启用了总结功能，更新其调度任务")
                                main = await get_main_module()
                                if hasattr(main, 'scheduler') and main.scheduler:
                                    await main.scheduler.schedule_rule(target_rule)
                                    logger.info(f"目标规则调度任务更新成功，新时间: {time}")
                                else:
                                    logger.warning("调度器未初始化")
                            
                            logger.info(f"同步规则 {sync_rule_id} 的总结时间从 {old_target_time} 到 {time}")
                        except Exception as e:
                            logger.error(f"同步总结时间到规则 {sync_rule_id} 时出错: {str(e)}")
                            continue
                    
                    # 提交所有同步更改
                    session.commit()
                    logger.info("所有同步总结时间更改已提交")

                # 如果总结功能已开启，重新调度任务
                if rule.is_summary:
                    logger.info("规则已启用总结功能，开始更新调度任务")
                    main = await get_main_module()
                    if hasattr(main, 'scheduler') and main.scheduler:
                        await main.scheduler.schedule_rule(rule)
                        logger.info(f"调度任务更新成功，新时间: {time}")
                    else:
                        logger.warning("调度器未初始化")
                else:
                    logger.info("规则未启用总结功能，跳过调度任务更新")

                await event.edit(await get_ai_settings_text(rule), buttons=await create_ai_settings_buttons(rule))
                logger.info("界面更新完成")
        except Exception as e:
            logger.error(f"设置总结时间时出错: {str(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
        finally:
            session.close()
    return


async def callback_select_model(event, rule_id, session, message, data):
    # AI 模型固定为 .env 的 DEFAULT_AI_MODEL，不支持动态切换
    try:
        rid = int(str(rule_id).split(':', 1)[0])
        rule = session.query(ForwardRule).get(rid)
        if rule:
            await event.answer(f"AI模型已固定为 {os.getenv('DEFAULT_AI_MODEL', DEFAULT_AI_MODEL)}，请在 .env 中修改")
            await event.edit(await get_ai_settings_text(rule), buttons=await create_ai_settings_buttons(rule))
    finally:
        session.close()
    return



async def callback_model_page(event, rule_id, session, message, data):
    await event.answer('AI模型已固定，请在 .env 中修改 DEFAULT_AI_MODEL')
    return



async def callback_change_model(event, rule_id, session, message, data):
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            await event.answer(f"AI模型已固定为 {os.getenv('DEFAULT_AI_MODEL', DEFAULT_AI_MODEL)}，请在 .env 中修改")
            await event.edit(await get_ai_settings_text(rule), buttons=await create_ai_settings_buttons(rule))
    finally:
        session.close()
    return



async def callback_cancel_set_prompt(event, rule_id, session, message, data):
    # 处理取消设置提示词
    rule_id = data.split(':')[1]
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            # 清除状态
            state_manager.clear_state(event.sender_id, abs(event.chat_id))
            # 返回到 AI 设置页面
            await event.edit(await get_ai_settings_text(rule), buttons=await create_ai_settings_buttons(rule))
            await event.answer("已取消设置")
    finally:
        session.close()
    return




async def callback_cancel_set_summary(event, rule_id, session, message, data):
    # 处理取消设置总结
    rule_id = data.split(':')[1]
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            # 清除状态
            state_manager.clear_state(event.sender_id, abs(event.chat_id))
            # 返回到 AI 设置页面
            await event.edit(await get_ai_settings_text(rule), buttons=await create_ai_settings_buttons(rule))
            await event.answer("已取消设置")
    finally:
        session.close()
    return

async def callback_summary_now(event, rule_id, session, message, data):
    # 处理立即执行总结的回调
    logger.info(f"处理立即执行总结回调 - rule_id: {rule_id}")
    
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if not rule:
            await event.answer("规则不存在")
            return
        
        main = await get_main_module()
        user_client = main.user_client
        bot_client = main.bot_client

        scheduler = SummaryScheduler(user_client, bot_client)
        await event.answer("开始执行总结，请稍候...")
        
        await message.edit(
            f"正在为规则 {rule_id}（{rule.source_chat.name} -> {rule.target_chat.name}）生成总结...\n"
            f"处理需要一定时间，请耐心等待。",
            buttons=[[Button.inline("返回", f"ai_settings:{rule_id}")]]
        )
        
        try:
            # 执行总结任务
            await asyncio.create_task(scheduler._execute_summary(rule.id,is_now=True))
            logger.info(f"已启动规则 {rule_id} 的立即总结任务")
        except Exception as e:
            logger.error(f"执行总结任务失败: {str(e)}")
            logger.error(traceback.format_exc())
            await message.edit(
                f"总结生成失败: {str(e)}",
                buttons=[[Button.inline("返回", f"ai_settings:{rule_id}")]]
            )
    except Exception as e:
        logger.error(f"处理总结时出错: {str(e)}")
        logger.error(traceback.format_exc())
        await event.answer(f"处理时出错: {str(e)}")
    finally:
        session.close()
    
    return


# ────────────────────────────────────────────────
# AI 增强设置（去广告 + 改写）
# ────────────────────────────────────────────────

async def callback_ai_enhance_settings(event, rule_id, session, message, data):
    """显示 AI 增强设置页面"""
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            await event.edit(
                await get_ai_enhance_settings_text(rule),
                buttons=await create_ai_enhance_settings_buttons(rule)
            )
    finally:
        session.close()


# ── 去广告：模型选择 ──

async def callback_change_ai_ad_removal_model(event, rule_id, session, message, data):
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            await event.answer(f"AI模型已固定为 {os.getenv('DEFAULT_AI_MODEL', DEFAULT_AI_MODEL)}，请在 .env 中修改")
            await event.edit(await get_ai_enhance_settings_text(rule),
                             buttons=await create_ai_enhance_settings_buttons(rule))
    finally:
        session.close()
    return


async def callback_select_ai_ad_removal_model(event, rule_id, session, message, data):
    try:
        rid = int(str(rule_id).split(':', 1)[0])
        rule = session.query(ForwardRule).get(rid)
        if rule:
            await event.answer(f"AI模型已固定为 {os.getenv('DEFAULT_AI_MODEL', DEFAULT_AI_MODEL)}，请在 .env 中修改")
            await event.edit(await get_ai_enhance_settings_text(rule),
                             buttons=await create_ai_enhance_settings_buttons(rule))
    finally:
        session.close()


# ── 去广告：置信度阈值 ──

async def callback_set_ai_ad_removal_threshold(event, rule_id, session, message, data):
    """进入设置去广告置信度阈值状态"""
    rule = session.query(ForwardRule).get(int(rule_id))
    if not rule:
        await event.answer('规则不存在')
        return

    if isinstance(event.chat, types.Channel):
        if not await is_admin(event):
            await event.answer('只有管理员可以修改设置')
            return
        user_id = os.getenv('USER_ID')
    else:
        user_id = event.sender_id

    chat_id = abs(event.chat_id)
    state = f"set_ai_ad_removal_threshold:{rule_id}"
    state_manager.set_state(user_id, chat_id, state, message, state_type="ai_enhance")
    asyncio.create_task(cancel_state_after_timeout(user_id, chat_id))

    current = getattr(rule, 'ai_ad_removal_threshold', 80)
    try:
        await message.edit(
            f"请发送新的置信度阈值（整数 1-100，当前: {current}）\n"
            f"例如：80 表示 80% 置信度时才去广告\n"
            f"5分钟内未设置将自动取消",
            buttons=[[Button.inline("取消", f"cancel_set_ai_enhance:{rule_id}")]]
        )
    except Exception as e:
        logger.error(f"编辑消息时出错: {str(e)}")
    finally:
        session.close()


# ── 去广告：提示词 ──

async def callback_set_ai_ad_removal_prompt(event, rule_id, session, message, data):
    """进入设置去广告提示词状态"""
    rule = session.query(ForwardRule).get(int(rule_id))
    if not rule:
        await event.answer('规则不存在')
        return

    if isinstance(event.chat, types.Channel):
        if not await is_admin(event):
            await event.answer('只有管理员可以修改设置')
            return
        user_id = os.getenv('USER_ID')
    else:
        user_id = event.sender_id

    chat_id = abs(event.chat_id)
    state = f"set_ai_ad_removal_prompt:{rule_id}"
    state_manager.set_state(user_id, chat_id, state, message, state_type="ai_enhance")
    asyncio.create_task(cancel_state_after_timeout(user_id, chat_id))

    from utils.constants import DEFAULT_AI_AD_REMOVAL_PROMPT
    current_prompt = rule.ai_ad_removal_prompt or DEFAULT_AI_AD_REMOVAL_PROMPT
    try:
        await message.edit(
            f"请发送新的AI去广告提示词\n"
            f"当前规则ID: `{rule_id}`\n"
            f"当前提示词：\n\n`{current_prompt}`\n\n"
            f"5分钟内未设置将自动取消",
            buttons=[[Button.inline("取消", f"cancel_set_ai_enhance:{rule_id}")]]
        )
    except Exception as e:
        logger.error(f"编辑消息时出错: {str(e)}")
    finally:
        session.close()


# ── 改写：模型选择 ──

async def callback_change_ai_rewrite_model(event, rule_id, session, message, data):
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            await event.answer(f"AI模型已固定为 {os.getenv('DEFAULT_AI_MODEL', DEFAULT_AI_MODEL)}，请在 .env 中修改")
            await event.edit(await get_ai_enhance_settings_text(rule),
                             buttons=await create_ai_enhance_settings_buttons(rule))
    finally:
        session.close()
    return


async def callback_select_ai_rewrite_model(event, rule_id, session, message, data):
    try:
        rid = int(str(rule_id).split(':', 1)[0])
        rule = session.query(ForwardRule).get(rid)
        if rule:
            await event.answer(f"AI模型已固定为 {os.getenv('DEFAULT_AI_MODEL', DEFAULT_AI_MODEL)}，请在 .env 中修改")
            await event.edit(await get_ai_enhance_settings_text(rule),
                             buttons=await create_ai_enhance_settings_buttons(rule))
    finally:
        session.close()


# ── 改写：提示词 ──

async def callback_set_ai_rewrite_prompt(event, rule_id, session, message, data):
    """进入设置改写提示词状态"""
    rule = session.query(ForwardRule).get(int(rule_id))
    if not rule:
        await event.answer('规则不存在')
        return

    if isinstance(event.chat, types.Channel):
        if not await is_admin(event):
            await event.answer('只有管理员可以修改设置')
            return
        user_id = os.getenv('USER_ID')
    else:
        user_id = event.sender_id

    chat_id = abs(event.chat_id)
    state = f"set_ai_rewrite_prompt:{rule_id}"
    state_manager.set_state(user_id, chat_id, state, message, state_type="ai_enhance")
    asyncio.create_task(cancel_state_after_timeout(user_id, chat_id))

    from utils.constants import DEFAULT_AI_REWRITE_PROMPT
    current_prompt = rule.ai_rewrite_prompt or DEFAULT_AI_REWRITE_PROMPT
    try:
        await message.edit(
            f"请发送新的AI改写提示词\n"
            f"当前规则ID: `{rule_id}`\n"
            f"当前提示词：\n\n`{current_prompt}`\n\n"
            f"5分钟内未设置将自动取消",
            buttons=[[Button.inline("取消", f"cancel_set_ai_enhance:{rule_id}")]]
        )
    except Exception as e:
        logger.error(f"编辑消息时出错: {str(e)}")
    finally:
        session.close()


# ── 取消设置 ──

async def callback_cancel_set_ai_enhance(event, rule_id, session, message, data):
    """取消AI增强设置输入状态"""
    rule_id = data.split(':')[1]
    try:
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            user_id = _resolve_state_user_id(event)
            state_manager.clear_state(user_id, abs(event.chat_id))
            await event.edit(await get_ai_enhance_settings_text(rule),
                             buttons=await create_ai_enhance_settings_buttons(rule))
            await event.answer("已取消设置")
    finally:
        session.close()



# ── 确认/取消 AI 改写提示词 ──

async def callback_confirm_set_ai_rewrite_prompt(event, rule_id, session, message, data):
    """确认保存AI改写提示词"""
    try:
        rid = int(rule_id)
        user_id = _resolve_state_user_id(event)
        chat_id = abs(event.chat_id)
        
        # 获取待确认数据
        pending = state_manager.get_pending_data(user_id, chat_id)
        if not pending or pending.get("rule_id") != rid:
            await event.edit("确认超时或数据不匹配，请重新设置")
            await event.answer("确认失败")
            state_manager.clear_state(user_id, chat_id)
            return
        
        # 加载规则
        rule = session.query(ForwardRule).get(rid)
        if not rule:
            await event.edit("规则不存在")
            await event.answer("规则不存在")
            state_manager.clear_state(user_id, chat_id)
            return
        
        # 提交修改
        rule.ai_rewrite_prompt = pending.get('new_prompt', '')
        session.commit()
        
        # 清理状态
        state_manager.clear_state(user_id, chat_id)
        
        # 返回AI增强设置页面
        await event.edit(
            await get_ai_enhance_settings_text(rule),
            buttons=await create_ai_enhance_settings_buttons(rule)
        )
        await event.answer("AI改写提示词已保存")
    except Exception as e:
        logger.error(f"确认AI改写提示词时出错: {str(e)}")
        await event.answer("保存失败")
    finally:
        session.close()


async def callback_cancel_confirm_ai_rewrite_prompt(event, rule_id, session, message, data):
    """取消保存AI改写提示词"""
    try:
        user_id = _resolve_state_user_id(event)
        chat_id = abs(event.chat_id)
        
        # 清理状态
        state_manager.clear_state(user_id, chat_id)
        
        # 如果规则存在，返回AI增强设置页面
        rule = session.query(ForwardRule).get(int(rule_id))
        if rule:
            await event.edit(
                await get_ai_enhance_settings_text(rule),
                buttons=await create_ai_enhance_settings_buttons(rule)
            )
        
        await event.answer("已取消设置")
    except Exception as e:
        logger.error(f"取消确认AI改写提示词时出错: {str(e)}")
        await event.answer("取消失败")
    finally:
        session.close()
