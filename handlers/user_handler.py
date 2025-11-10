from models.models import ForwardMode, DeleteRule
import re
import logging
import asyncio
import os
from utils.common import check_keywords, get_sender_info


logger = logging.getLogger(__name__)

async def apply_delete_rules(rule, message_text, session):
    """应用删除规则到消息文本 - 删除关键字及其后的所有内容"""
    logger.info(f'[删除规则] 开始应用删除规则')
    logger.info(f'[删除规则] message_text存在={bool(message_text)}')
    
    if not message_text:
        logger.info(f'[删除规则] 跳过删除（无文本内容）')
        return message_text
    
    try:
        # 获取所有删除规则
        delete_rules = session.query(DeleteRule).filter_by(rule_id=rule.id).all()
        delete_rules_count = len(delete_rules)
        logger.info(f'[删除规则] 规则数量: {delete_rules_count}')
        
        if delete_rules_count == 0:
            return message_text
        
        for idx, delete_rule in enumerate(delete_rules):
            keyword = delete_rule.keyword
            logger.info(f'[删除规则] 处理第 {idx+1} 条规则: 关键字="{keyword}"')
            
            # 查找关键字在文本中的位置
            keyword_pos = message_text.find(keyword)
            
            if keyword_pos != -1:
                # 找到关键字，删除关键字及其后的所有内容
                old_text = message_text
                message_text = message_text[:keyword_pos]
                logger.info(f'[删除规则] ✅ 执行删除成功:\n原文: "{old_text}"\n关键字: "{keyword}"\n删除后: "{message_text}"')
                # 找到第一个匹配的关键字后就停止，避免重复删除
                break
            else:
                logger.info(f'[删除规则] ⚠️ 未找到关键字: "{keyword}"')
        
        logger.info(f'[删除规则] 最终结果: "{message_text}"')
        return message_text
    except Exception as e:
        logger.error(f'[删除规则] 应用删除规则时出错: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return message_text

async def apply_replace_rules(rule, message_text):
    """应用替换规则到消息文本"""
    logger.info(f'[替换规则] 开始应用替换规则')
    logger.info(f'[替换规则] is_replace={rule.is_replace}, message_text存在={bool(message_text)}')
    
    if not rule.is_replace or not message_text:
        logger.info(f'[替换规则] 跳过替换（is_replace={rule.is_replace}, has_text={bool(message_text)}）')
        return message_text
    
    try:
        # 尝试访问替换规则
        try:
            replace_rules_count = len(rule.replace_rules) if rule.replace_rules else 0
            logger.info(f'[替换规则] 规则数量: {replace_rules_count}')
        except Exception as e:
            logger.error(f'[替换规则] 无法访问替换规则列表: {str(e)}')
            return message_text
        
        for idx, replace_rule in enumerate(rule.replace_rules):
            logger.info(f'[替换规则] 处理第 {idx+1} 条规则: "{replace_rule.pattern}" -> "{replace_rule.content}"')
            
            if replace_rule.pattern == '.*':
                # 全文替换
                logger.info(f'[替换规则] 执行全文替换:\n原文: "{message_text}"\n替换为: "{replace_rule.content or ""}"')
                message_text = replace_rule.content or ''
                break
            else:
                try:
                    # 正则替换
                    old_text = message_text
                    message_text = re.sub(
                        replace_rule.pattern,
                        replace_rule.content or '',
                        message_text
                    )
                    if old_text != message_text:
                        logger.info(f'[替换规则] ✅ 执行部分替换成功:\n原文: "{old_text}"\n替换规则: "{replace_rule.pattern}" -> "{replace_rule.content}"\n替换后: "{message_text}"')
                    else:
                        logger.info(f'[替换规则] ⚠️ 未匹配: "{replace_rule.pattern}" 在 "{old_text}" 中')
                except re.error as e:
                    logger.error(f'[替换规则] 替换规则格式错误: {replace_rule.pattern}, 错误: {str(e)}')
        
        logger.info(f'[替换规则] 最终结果: "{message_text}"')
        return message_text
    except Exception as e:
        logger.error(f'[替换规则] 应用替换规则时出错: {str(e)}')
        import traceback
        logger.error(traceback.format_exc())
        return message_text

async def process_forward_rule(client, event, chat_id, rule, session=None):
    """处理转发规则（用户模式）"""

    
    if not rule.enable_rule:
        logger.info(f'规则 ID: {rule.id} 已禁用，跳过处理')
        return
    
    # 获取消息文本，优先使用message字段（包含所有文本），其次是text字段
    message_text = event.message.message if hasattr(event.message, 'message') and event.message.message else (event.message.text or '')
    check_message_text = message_text
    # 添加日志
    logger.info(f'处理规则 ID: {rule.id}')
    logger.info(f'消息内容: {message_text}')
    logger.info(f'消息类型: message={hasattr(event.message, "message")}, text={event.message.text is not None}')
    logger.info(f'规则模式: {rule.forward_mode.value}')


    if rule.is_filter_user_info:
        sender_info = await get_sender_info(event, rule.id)  # 调用新的函数获取 sender_info
        if sender_info:
            check_message_text = f"{sender_info}:\n{message_text}"
            logger.info(f'附带用户信息后的消息: {message_text}')
        else:
            logger.warning(f"规则 ID: {rule.id} - 无法获取发送者信息")
    
    should_forward = await check_keywords(rule,check_message_text)
    
    logger.info(f'最终决定: {"转发" if should_forward else "不转发"}')
    
    if should_forward:
        target_chat = rule.target_chat
        target_chat_id = int(target_chat.telegram_chat_id)
        
        try:
            # 添加调试日志
            logger.info(f'规则 {rule.id} - is_replace: {rule.is_replace}')
            try:
                replace_rules_count = len(rule.replace_rules) if rule.replace_rules else 0
                logger.info(f'规则 {rule.id} - 替换规则数量: {replace_rules_count}')
                if replace_rules_count > 0:
                    for idx, rr in enumerate(rule.replace_rules):
                        logger.info(f'  替换规则 {idx+1}: pattern="{rr.pattern}", content="{rr.content}"')
            except Exception as e:
                logger.error(f'访问替换规则时出错: {str(e)}')
                replace_rules_count = 0
            
            # 先应用删除规则（如果有session的话）
            if session and message_text:
                message_text = await apply_delete_rules(rule, message_text, session)
                logger.info(f'规则 {rule.id} - 删除规则应用后的文本: {message_text}')
            
            # 检查是否需要应用替换规则
            need_replace = rule.is_replace and replace_rules_count > 0 and message_text
            logger.info(f'规则 {rule.id} - need_replace: {need_replace}')
            
            if need_replace:
                # 应用替换规则
                replaced_text = await apply_replace_rules(rule, message_text)
                
                # 如果文本发生了改变，需要重新发送而不是转发
                if replaced_text != message_text:
                    logger.info(f'检测到替换规则生效，将重新发送消息而不是转发')
                    
                    if event.message.grouped_id:
                        # 处理媒体组消息
                        await asyncio.sleep(1)
                        
                        # 收集媒体组的所有消息
                        media_messages = []
                        async for message in client.iter_messages(
                            event.chat_id,
                            limit=20,
                            min_id=event.message.id - 10,
                            max_id=event.message.id + 10
                        ):
                            if message.grouped_id == event.message.grouped_id:
                                media_messages.append(message)
                                logger.info(f'找到媒体组消息: ID={message.id}')
                        
                        # 按ID排序
                        media_messages.sort(key=lambda m: m.id)
                        
                        # 下载所有媒体文件
                        files = []
                        for msg in media_messages:
                            if msg.media:
                                file_path = await msg.download_media(os.path.join(os.getcwd(), 'temp'))
                                if file_path:
                                    files.append(file_path)
                        
                        if files:
                            # 发送媒体组，第一个文件带替换后的文本
                            await client.send_file(
                                target_chat_id,
                                files,
                                caption=replaced_text
                            )
                            logger.info(f'[用户] 已发送 {len(files)} 条媒体组消息（应用替换规则）到: {target_chat.name} ({target_chat_id})')
                            
                            # 清理临时文件
                            for file_path in files:
                                try:
                                    os.remove(file_path)
                                except Exception as e:
                                    logger.error(f'删除临时文件失败: {str(e)}')
                    
                    elif event.message.media:
                        # 处理单条媒体消息
                        file_path = await event.message.download_media(os.path.join(os.getcwd(), 'temp'))
                        if file_path:
                            await client.send_file(
                                target_chat_id,
                                file_path,
                                caption=replaced_text
                            )
                            logger.info(f'[用户] 消息已发送（应用替换规则）到: {target_chat.name} ({target_chat_id})')
                            
                            # 清理临时文件
                            try:
                                os.remove(file_path)
                            except Exception as e:
                                logger.error(f'删除临时文件失败: {str(e)}')
                    
                    else:
                        # 处理纯文本消息
                        await client.send_message(
                            target_chat_id,
                            replaced_text
                        )
                        logger.info(f'[用户] 文本消息已发送（应用替换规则）到: {target_chat.name} ({target_chat_id})')
                    
                    return
            
            # 如果不需要替换或替换后文本未变化，使用原来的转发逻辑
            if event.message.grouped_id:
                # 等待一段时间以确保收到所有媒体组消息
                await asyncio.sleep(1)
                
                # 收集媒体组的所有消息
                messages = []
                async for message in client.iter_messages(
                    event.chat_id,
                    limit=20,  # 限制搜索范围
                    min_id=event.message.id - 10,
                    max_id=event.message.id + 10
                ):
                    if message.grouped_id == event.message.grouped_id:
                        messages.append(message.id)
                        logger.info(f'找到媒体组消息: ID={message.id}')
                
                # 按照ID排序，确保转发顺序正确
                messages.sort()
                
                # 一次性转发所有消息
                await client.forward_messages(
                    target_chat_id,
                    messages,
                    event.chat_id
                )
                logger.info(f'[用户] 已转发 {len(messages)} 条媒体组消息到: {target_chat.name} ({target_chat_id})')
                
            else:
                # 处理单条消息
                await client.forward_messages(
                    target_chat_id,
                    event.message.id,
                    event.chat_id
                )
                logger.info(f'[用户] 消息已转发到: {target_chat.name} ({target_chat_id})')
                
                
        except Exception as e:
            logger.error(f'转发消息时出错: {str(e)}')
            logger.exception(e) 