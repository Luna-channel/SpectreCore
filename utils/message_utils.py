from astrbot.api.all import *
from typing import List, Dict, Any
import os
import time
from datetime import datetime
from .image_caption import ImageCaptionUtils
import asyncio

def _safe_isinstance(obj, class_name: str) -> bool:
    """
    安全地检查对象是否为指定类的实例
    如果类不存在，则使用 type 属性检查
    
    Args:
        obj: 要检查的对象
        class_name: 类名（字符串）
        
    Returns:
        是否为该类的实例
    """
    # 首先尝试使用 type 属性检查（更可靠）
    if hasattr(obj, 'type'):
        type_mapping = {
            'anonymous': 'Anonymous',
            'rps': 'RPS',
            'dice': 'Dice',
            'shake': 'Shake',
            'redbag': 'RedBag',
            'poke': 'Poke',
            'forward': 'Forward',
            'node': 'Node',
            'nodes': 'Nodes',
            'xml': 'Xml',
            'json': 'Json',
            'cardimage': 'CardImage',
            'tts': 'TTS',
            'wechatemoji': 'WechatEmoji',
        }
        obj_type = getattr(obj, 'type', '').lower()
        if obj_type in type_mapping and type_mapping[obj_type] == class_name:
            return True
    
    # 如果类存在，使用 isinstance 检查
    try:
        cls = globals().get(class_name)
        if cls is not None:
            return isinstance(obj, cls)
    except (NameError, TypeError):
        pass
    
    return False

class MessageUtils:
    """
    消息处理工具类
    """
        
    @staticmethod
    async def format_history_for_llm(history_messages: List[AstrBotMessage], max_messages: int = 20) -> str:
        """
        将历史消息列表格式化为适合输入给大模型的文本格式
        
        Args:
            history_messages: 历史消息列表
            max_messages: 最大消息数量，默认20条
            
        Returns:
            格式化后的历史消息文本
        """
        if not history_messages:
            return ""
        
        # 限制消息数量
        if len(history_messages) > max_messages:
            history_messages = history_messages[-max_messages:]
        
        formatted_text = ""
        divider = "\n" + "-" + "\n"
        
        for idx, msg in enumerate(history_messages):
            # 获取发送者信息
            sender_name = "未知用户"
            sender_id = "unknown"
            if hasattr(msg, "sender") and msg.sender:
                sender_name = msg.sender.nickname or "未知用户"
                sender_id = msg.sender.user_id or "unknown"
            
            # 获取发送时间
            send_time = "未知时间"
            if hasattr(msg, "timestamp") and msg.timestamp:
                try:
                    time_obj = datetime.fromtimestamp(msg.timestamp)
                    send_time = time_obj.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    # 如果timestamp不是合法的时间戳，尝试使用当前时间
                    pass
            
            # 获取消息内容 (异步调用)
            message_content = await MessageUtils.outline_message_list(msg.message) if hasattr(msg, "message") and msg.message else ""
            
            # 格式化该条消息
            message_text = f"发送者: {sender_name} (ID: {sender_id})\n"
            message_text += f"时间: {send_time}\n"
            message_text += f"内容: {message_content}"
            
            # 添加到结果中
            formatted_text += message_text
            
            # 除了最后一条消息，每条消息后添加分割线
            if idx < len(history_messages) - 1:
                formatted_text += divider
        
        return formatted_text
           
    @staticmethod
    async def outline_message_list(message_list: List[BaseMessageComponent]) -> str:
        """
        获取消息概要。

        除了文本消息外，其他消息类型会被转换为对应的占位符，同时保留尽可能多的信息。
        图片会尝试进行转述。

        Astrbot中get_message_outline()方法的扩展版本，支持更多消息类型和更详细的内容。
        
        Args:
            message_list: 消息段列表
            
        Returns:
            消息概要文本
        """
        outline = ""
        for i in message_list:
            if isinstance(i, Plain):
                outline += i.text
            elif isinstance(i, Image):
                try:
                    # 优先使用 file 字段（持久化存储的绝对路径），降级到 url 字段（向后兼容）
                    image = i.file if i.file else i.url
                    if image:
                        # 如果是 file:/// 格式的持久化存储图片，提取绝对路径
                        if image.startswith("file:///"):
                            image_path = image[8:]  # 移除 file:/// 前缀
                            logger.debug(f"使用持久化图片路径: {image_path}")

                            # 检查文件是否存在
                            if not os.path.exists(image_path):
                                logger.warning(f"持久化图片文件不存在: {image_path}")
                                outline += f"[图片: 文件不存在]"
                                continue
                            image = image_path

                        # 异步调用图片转述
                        caption = await ImageCaptionUtils.generate_image_caption(image)
                        if caption:
                            outline += f"[图片: {caption}]"
                        else:
                            outline += f"[图片]"
                    else:
                        outline += f"[图片]"
                except Exception as e:
                    logger.error(f"处理图片消息失败: {e}")
                    outline += "[图片]"
            elif isinstance(i, Face):
                outline += f"[表情:{i.id}]"
            elif isinstance(i, At):
                outline += f"[At:{i.qq}{f'({i.name})' if i.name else ''}]"
            elif isinstance(i, AtAll):
                outline += "[At:全体成员]"
            elif isinstance(i, Record):
                outline += "[语音]"
            elif isinstance(i, Video):
                outline += "[视频]"
            elif _safe_isinstance(i, 'RPS'):
                outline += "[猜拳]"
            elif _safe_isinstance(i, 'Dice'):
                outline += "[骰子]"
            elif _safe_isinstance(i, 'Shake'):
                outline += "[抖一抖]"
            elif _safe_isinstance(i, 'Anonymous'):
                outline += "[匿名]"
            elif isinstance(i, Share):
                outline += f"[分享:《{i.title}》{i.content if i.content else ''}]"
            elif isinstance(i, Contact):
                outline += f"[联系人:{i.id}]"
            elif isinstance(i, Location):
                outline += f"[位置:{i.title}{f'({i.content})' if i.content else ''}]"
            elif isinstance(i, Music):
                outline += f"[音乐:{i.title}{f'({i.content})' if i.content else ''}]"
            elif _safe_isinstance(i, 'RedBag'):
                outline += f"[红包:{getattr(i, 'title', '')}]"
            elif _safe_isinstance(i, 'Poke'):
                outline += f"[戳一戳 对:{getattr(i, 'qq', '')}]"
            elif _safe_isinstance(i, 'Forward'):
                outline += f"[合并转发消息]"
            elif _safe_isinstance(i, 'Node'):
                outline += f"[合并转发消息]"
            elif _safe_isinstance(i, 'Nodes'):
                outline += f"[合并转发消息]"
            elif _safe_isinstance(i, 'Xml'):
                outline += f"[XML消息]"
            elif _safe_isinstance(i, 'Json'):
                # 尝试从JSON中提取有用信息
                json_data_attr = getattr(i, 'data', None)
                if isinstance(json_data_attr, str):
                    try:
                        import json
                        json_data = json.loads(json_data_attr)
                        if "prompt" in json_data:
                            outline += f"[JSON卡片:{json_data.get('prompt', '')}]"
                        elif "app" in json_data:
                            outline += f"[小程序:{json_data.get('app', '')}]"
                        else:
                            outline += "[JSON消息]"
                    except:
                        outline += "[JSON消息]"
                else:
                    outline += "[JSON消息]"
            elif _safe_isinstance(i, 'CardImage'):
                outline += f"[卡片图片:{getattr(i, 'source', '')}]"
            elif _safe_isinstance(i, 'TTS'):
                outline += f"[TTS:{getattr(i, 'text', '')}]"
            elif isinstance(i, File):
                outline += f"[文件:{i.name}]"
            elif _safe_isinstance(i, 'WechatEmoji'):
                outline += "[微信表情]"
            elif isinstance(i, Reply):
                if i.chain:
                    sender_info = f"{i.sender_nickname}({i.sender_id})" if i.sender_nickname else f"{i.sender_id}"
                    # 异步调用
                    reply_content = await MessageUtils.outline_message_list(i.chain)
                    outline += f"[回复({sender_info}: {reply_content})]"
                elif i.message_str:
                    sender_info = f"{i.sender_nickname}({i.sender_id})" if i.sender_nickname else f"{i.sender_id}"
                    outline += f"[回复({sender_info}: {i.message_str})]"
                elif i.sender_nickname or i.sender_id:
                    sender_info = f"{i.sender_nickname}({i.sender_id})" if i.sender_nickname else f"{i.sender_id}"
                    outline += f"[回复({sender_info})]"
                else:
                    outline += "[回复消息]"
            else:
                outline += f"[{i.type}]"
        return outline