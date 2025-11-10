import logging
from filters.base_filter import BaseFilter
from models.models import DeleteRule, get_session

logger = logging.getLogger(__name__)

class DeleteFilter(BaseFilter):
    """
    删除过滤器，根据规则删除关键字及其后的所有内容
    """
    
    async def _process(self, context):
        """
        处理消息文本删除
        
        Args:
            context: 消息上下文
            
        Returns:
            bool: 是否继续处理
        """
        rule = context.rule
        message_text = context.message_text

        # 如果没有文本内容，直接返回
        if not message_text:
            return True
        
        session = get_session()
        try:
            # 获取所有删除规则
            delete_rules = session.query(DeleteRule).filter_by(rule_id=rule.id).all()
            delete_rules_count = len(delete_rules)
            
            if delete_rules_count == 0:
                return True
            
            logger.info(f'[删除规则] 规则数量: {delete_rules_count}')
            
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
            
            # 更新上下文中的消息文本
            context.message_text = message_text
            context.check_message_text = message_text
            
            return True
        except Exception as e:
            logger.error(f'应用删除规则时出错: {str(e)}')
            context.errors.append(f"删除规则错误: {str(e)}")
            return True  # 即使删除出错，仍然继续处理
        finally:
            session.close()

