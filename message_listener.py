from telethon import events
from models.models import get_session, Chat, ForwardRule
import logging
from handlers import user_handler, bot_handler
from handlers.prompt_handlers import handle_prompt_setting
import asyncio
import os
from dotenv import load_dotenv
from telethon.tl.types import ChannelParticipantsAdmins
from managers.state_manager import state_manager
from telethon.tl import types
from filters.process import process_forward_rule
from sqlalchemy.orm import joinedload
# 加载环境变量
load_dotenv()

# 获取logger
logger = logging.getLogger(__name__)

# 添加一个缓存来存储已处理的媒体组
PROCESSED_GROUPS = set()

BOT_ID = None

async def setup_listeners(user_client, bot_client):
    """
    设置消息监听器
    
    Args:
        user_client: 用户客户端（用于监听消息和转发）
        bot_client: 机器人客户端（用于处理命令和转发）
    """
    global BOT_ID
    
    # 直接获取机器人ID
    try:
        me = await bot_client.get_me()
        BOT_ID = me.id
        logger.info(f"获取到机器人ID: {BOT_ID} (类型: {type(BOT_ID)})")
    except Exception as e:
        logger.error(f"获取机器人ID时出错: {str(e)}")
    
    # 过滤器，排除机器人自己的消息
    async def not_from_bot(event):
        if BOT_ID is None:
            return True  # 如果未获取到机器人ID，不进行过滤
        
        sender = event.sender_id
        try:
            sender_id = int(sender) if sender is not None else None
            is_not_bot = sender_id != BOT_ID
            if not is_not_bot:
                logger.info(f"过滤器识别到机器人消息，忽略处理: {sender_id}")
            return is_not_bot
        except (ValueError, TypeError):
            return True  # 转换失败时不过滤
    
    # 用户客户端监听器 - 使用过滤器，避免处理机器人消息
    @user_client.on(events.NewMessage(func=not_from_bot))
    async def user_message_handler(event):
        await handle_user_message(event, user_client, bot_client)
    
    # 机器人客户端监听器 - 使用过滤器
    @bot_client.on(events.NewMessage(func=not_from_bot))
    async def bot_message_handler(event):
        # logger.info(f"机器人收到非自身消息, 发送者ID: {event.sender_id}")
        await handle_bot_message(event, bot_client)
        
    # 注册机器人回调处理器
    bot_client.add_event_handler(bot_handler.callback_handler)

async def handle_user_message(event, user_client, bot_client):
    """处理用户客户端收到的消息"""
    # logger.info("handle_user_message:开始处理用户消息")
    
    chat = await event.get_chat()
    # db_chat_id 始终用于数据库查询，不加 100 前缀
    db_chat_id = abs(chat.id)
    # logger.info(f"handle_user_message:获取到聊天ID: {db_chat_id}")

    # 检查是否频道消息
    # state_chat_id 仅用于状态管理查询，频道消息加 100 前缀与存储时保持一致
    if isinstance(event.chat, types.Channel) and state_manager.check_state():
        # logger.info("handle_user_message:检测到频道消息且存在状态")
        sender_id = os.getenv('USER_ID')
        state_chat_id = int(f"100{db_chat_id}")
        # logger.info(f"handle_user_message:频道消息处理: sender_id={sender_id}, state_chat_id={state_chat_id}")
        # 频道广播消息绝不能被当作 prompt 输入消费，直接跳过 state 检查，进入转发逻辑
    else:
        sender_id = event.sender_id
        state_chat_id = db_chat_id
        # logger.info(f"handle_user_message:非频道消息处理: sender_id={sender_id}")

        # 仅对非频道消息检查用户状态（避免被监听频道的普通消息误触发 prompt 输入）
        current_state, message, state_type = state_manager.get_state(sender_id, state_chat_id)
        # logger.info(f'handle_user_message：当前是否有状态: {state_manager.check_state()}')
        # logger.info(f"handle_user_message：当前用户ID和聊天ID: {sender_id}, {state_chat_id}")
        # logger.info(f"handle_user_message：获取当前聊天窗口的用户状态: {current_state}")

        if current_state:
            # logger.info(f"检测到用户状态: {current_state}")
            # 处理提示词设置
            # logger.info("准备处理提示词设置")
            if await handle_prompt_setting(event, bot_client, sender_id, state_chat_id, current_state, message):
                # logger.info("提示词设置处理完成，返回")
                return
            # logger.info("提示词设置处理未完成，继续执行")

    # 检查是否是媒体组消息（使用 db_chat_id 保持一致性）
    if event.message.grouped_id:
        # 如果这个媒体组已经处理过，就跳过
        group_key = f"{db_chat_id}:{event.message.grouped_id}"
        if group_key in PROCESSED_GROUPS:
            return
        # 标记这个媒体组为已处理
        PROCESSED_GROUPS.add(group_key)
        asyncio.create_task(clear_group_cache(group_key))
    
    # 首先检查数据库中是否有该聊天的转发规则（使用 db_chat_id，绝不加 100 前缀）
    session = get_session()
    # 防止对象在session关闭后过期
    session.expire_on_commit = False
    try:
        # 查询源聊天（用 db_chat_id）
        source_chat = session.query(Chat).filter(
            Chat.telegram_chat_id == str(db_chat_id)
        ).first()
        
        if not source_chat:
            return
            
        # 添加日志：查询转发规则
        logger.info(f'找到源聊天: {source_chat.name} (ID: {source_chat.id})')
        
        # 查找以当前聊天为源的规则，并预加载所有关联数据
        rules = session.query(ForwardRule).options(
            joinedload(ForwardRule.replace_rules),
            joinedload(ForwardRule.target_chat),
            joinedload(ForwardRule.keywords),
            joinedload(ForwardRule.source_chat)
        ).filter(
            ForwardRule.source_chat_id == source_chat.id
        ).all()
        
        if not rules:
            logger.info(f'聊天 {source_chat.name} 没有转发规则')
            return
        
        # 有转发规则时，才记录消息信息
        if event.message.grouped_id:
            logger.info(f'[用户] 收到媒体组消息 来自聊天: {source_chat.name} ({db_chat_id}) 组ID: {event.message.grouped_id}')
        else:
            logger.info(f'[用户] 收到新消息 来自聊天: {source_chat.name} ({db_chat_id}) 内容: {event.message.text}')
            
        # 添加日志：处理规则
        logger.info(f'找到 {len(rules)} 条转发规则')
        
        # 强制加载所有需要的数据到内存
        for rule in rules:
            # 强制访问所有属性以确保它们被加载到内存
            rule_id = rule.id
            rule_is_replace = rule.is_replace
            
            # 访问聊天属性
            if rule.target_chat:
                target_name = rule.target_chat.name
                target_id = rule.target_chat.telegram_chat_id
            if rule.source_chat:
                source_name = rule.source_chat.name
                source_id = rule.source_chat.telegram_chat_id
            
            # 强制加载替换规则列表
            replace_rules_data = []
            if rule.replace_rules:
                for rr in rule.replace_rules:
                    # 访问每个替换规则的属性
                    rr_pattern = rr.pattern
                    rr_content = rr.content
                    replace_rules_data.append((rr_pattern, rr_content))
                logger.info(f'规则 {rule_id} 预加载了 {len(replace_rules_data)} 条替换规则')
            
            # 强制加载关键字列表
            keywords_data = []
            if rule.keywords:
                for kw in rule.keywords:
                    kw_keyword = kw.keyword
                    kw_is_regex = kw.is_regex
                    kw_is_blacklist = kw.is_blacklist
                    keywords_data.append((kw_keyword, kw_is_regex, kw_is_blacklist))
        
        # 使所有对象脱离session，这样在session关闭后仍可访问已加载的数据
        session.expunge_all()
        
        # 处理每条转发规则
        for rule in rules:
            target_chat = rule.target_chat
            if not rule.enable_rule:
                logger.info(f'规则 {rule.id} 未启用')
                continue
            
            # 记录替换规则信息
            replace_count = len(rule.replace_rules) if rule.replace_rules else 0
            
            logger.info(f'处理转发规则 ID: {rule.id} (从 {rule.source_chat.name if rule.source_chat else "未知"} 转发到: {target_chat.name if target_chat else "未知"})')
            logger.info(f'规则 {rule.id} 的替换规则数量: {replace_count}')
            
            if rule.use_bot:
                # 直接使用过滤器模块中的process_forward_rule函数
                await process_forward_rule(bot_client, event, str(db_chat_id), rule)
            else:
                await user_handler.process_forward_rule(user_client, event, str(db_chat_id), rule, session)
        
    except Exception as e:
        logger.error(f'处理用户消息时发生错误: {str(e)}')
        logger.exception(e)  # 添加详细的错误堆栈
    finally:
        session.close()

async def handle_bot_message(event, bot_client):
    """处理机器人客户端收到的消息（命令）"""
    try:
            
        # logger.info("handle_bot_message:开始处理机器人消息")
        
        chat = await event.get_chat()
        chat_id = abs(chat.id)
        # logger.info(f"handle_bot_message:获取到聊天ID: {chat_id}")

        # 检查是否频道消息
        # state_chat_id 仅用于状态管理，频道消息加 100 前缀
        if isinstance(event.chat, types.Channel) and state_manager.check_state():
            # logger.info("handle_bot_message:检测到频道消息且存在状态")
            sender_id = os.getenv('USER_ID')
            state_chat_id = int(f"100{chat_id}")
            # logger.info(f"handle_bot_message:频道消息处理: sender_id={sender_id}, state_chat_id={state_chat_id}")
        else:
            sender_id = event.sender_id
            state_chat_id = chat_id
            # logger.info(f"handle_bot_message:非频道消息处理: sender_id={sender_id}")

        # 检查用户状态
        current_state, message, state_type = state_manager.get_state(sender_id, state_chat_id)
        # logger.info(f'handle_bot_message：当前是否有状态: {state_manager.check_state()}')
        # logger.info(f"handle_bot_message：当前用户ID和聊天ID: {sender_id}, {chat_id}")
        # logger.info(f"handle_bot_message：获取当前聊天窗口的用户状态: {current_state}")

        
        
        # 处理提示词设置
        if current_state:
            await handle_prompt_setting(event, bot_client, sender_id, state_chat_id, current_state, message)
            return

        # 如果没有特殊状态，则处理常规命令
        await bot_handler.handle_command(bot_client, event)
    except Exception as e:
        logger.error(f'处理机器人命令时发生错误: {str(e)}')
        logger.exception(e)

async def clear_group_cache(group_key, delay=300):  # 5分钟后清除缓存
    """清除已处理的媒体组记录"""
    await asyncio.sleep(delay)
    PROCESSED_GROUPS.discard(group_key) 

