"""Telegram 消息发送模块"""

import asyncio
import logging
from pathlib import Path
from typing import List, Optional
from telegram import Bot
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class TelegramSender:
    """Telegram 消息发送器"""

    def __init__(
        self,
        bot_token: str,
        chat_id: str,
        max_message_chars: int = 3800,
    ):
        """
        Args:
            bot_token: Telegram Bot Token
            chat_id: Telegram Chat ID 或用户名
            max_message_chars: 每条消息最大字符数 (默认为3800，留空间给前缀)
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.max_message_chars = max_message_chars
        self.bot = Bot(token=bot_token)

    def split_content_by_lines(
        self,
        content: str,
        lines_per_chunk: int = 15,
    ) -> List[str]:
        """将内容按行分割成适合Telegram的消息块

        Args:
            content: 要发送的完整内容
            lines_per_chunk: 每个块的行数

        Returns:
            消息块列表
        """
        lines = content.split('\n')
        chunks = []

        for i in range(0, len(lines), lines_per_chunk):
            chunk_lines = lines[i:i + lines_per_chunk]
            chunk = '\n'.join(chunk_lines)

            # 检查是否超过字符限制
            if len(chunk) > self.max_message_chars:
                # 如果超过，按字符分割
                chunks.extend(self._split_by_chars(chunk))
            else:
                chunks.append(chunk)

        return chunks

    def _split_by_chars(self, content: str) -> List[str]:
        """按字符限制分割内容"""
        chunks = []
        lines = content.split('\n')
        current_chunk = []
        current_length = 0

        for line in lines:
            line_length = len(line) + 1  # +1 for newline

            if current_length + line_length > self.max_message_chars:
                # 保存当前块
                if current_chunk:
                    chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_length = line_length
            else:
                current_chunk.append(line)
                current_length += line_length

        if current_chunk:
            chunks.append('\n'.join(current_chunk))

        return chunks

    async def send_file_chunks(
        self,
        filepath: Path,
        lines_per_chunk: int = 15,
        delay_between_messages: float = 1.0,
    ) -> bool:
        """发送文件内容，按行分割成多个消息

        Args:
            filepath: 文件路径
            lines_per_chunk: 每个消息块的行数
            delay_between_messages: 消息之间的延迟(秒)

        Returns:
            是否成功
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            chunks = self.split_content_by_lines(content, lines_per_chunk)

            if not chunks:
                logger.warning("文件内容为空")
                return False

            total_chunks = len(chunks)
            logger.info(f"文件将被分割成 {total_chunks} 个消息块发送")

            success = True
            for i, chunk in enumerate(chunks, 1):
                try:
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=f"📰 新闻分析报告 (第{i}/{total_chunks}部分)\n\n{chunk}"
                    )
                    logger.info(f"已发送第 {i}/{total_chunks} 部分")

                    if i < total_chunks:
                        await asyncio.sleep(delay_between_messages)

                except TelegramError as e:
                    logger.error(f"发送第 {i}/{total_chunks} 部分失败: {e}")
                    success = False

            return success

        except Exception as e:
            logger.error(f"读取或发送文件失败: {e}")
            return False

    async def send_text(
        self,
        text: str,
        lines_per_chunk: int = 15,
        delay_between_messages: float = 1.0,
    ) -> bool:
        """发送文本消息，自动分割

        Args:
            text: 要发送的文本
            lines_per_chunk: 每个消息块的行数
            delay_between_messages: 消息之间的延迟(秒)

        Returns:
            是否成功
        """
        try:
            chunks = self.split_content_by_lines(text, lines_per_chunk)

            if not chunks:
                logger.warning("文本内容为空")
                return False

            total_chunks = len(chunks)
            logger.info(f"文本将被分割成 {total_chunks} 个消息块发送")

            success = True
            for i, chunk in enumerate(chunks, 1):
                try:
                    await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=chunk if total_chunks == 1 else f"(第{i}/{total_chunks}) {chunk}"
                    )
                    logger.info(f"已发送第 {i}/{total_chunks} 部分")

                    if i < total_chunks:
                        await asyncio.sleep(delay_between_messages)

                except TelegramError as e:
                    logger.error(f"发送第 {i}/{total_chunks} 部分失败: {e}")
                    success = False

            return success

        except Exception as e:
            logger.error(f"发送文本失败: {e}")
            return False

    async def send_document(
        self,
        filepath: Path,
        caption: Optional[str] = None,
    ) -> bool:
        """发送文档文件

        Args:
            filepath: 文件路径
            caption: 文件说明

        Returns:
            是否成功
        """
        try:
            with open(filepath, 'rb') as f:
                await self.bot.send_document(
                    chat_id=self.chat_id,
                    document=f,
                    caption=caption,
                    filename=filepath.name,
                )
            logger.info(f"已发送文档: {filepath.name}")
            return True

        except Exception as e:
            logger.error(f"发送文档失败: {e}")
            return False


def send_telegram_file(
    bot_token: str,
    chat_id: str,
    filepath: str,
    lines_per_chunk: int = 15,
) -> bool:
    """便捷发送函数 - 发送文件内容

    Args:
        bot_token: Telegram Bot Token
        chat_id: Telegram Chat ID
        filepath: 文件路径
        lines_per_chunk: 每个消息块的行数

    Returns:
        是否成功
    """
    sender = TelegramSender(bot_token, chat_id)
    return asyncio.run(sender.send_file_chunks(Path(filepath), lines_per_chunk))


def send_telegram_text(
    bot_token: str,
    chat_id: str,
    text: str,
    lines_per_chunk: int = 15,
) -> bool:
    """便捷发送函数 - 发送文本

    Args:
        bot_token: Telegram Bot Token
        chat_id: Telegram Chat ID
        text: 要发送的文本
        lines_per_chunk: 每个消息块的行数

    Returns:
        是否成功
    """
    sender = TelegramSender(bot_token, chat_id)
    return asyncio.run(sender.send_text(text, lines_per_chunk))


def send_telegram_document(
    bot_token: str,
    chat_id: str,
    filepath: str,
    caption: Optional[str] = None,
) -> bool:
    """便捷发送函数 - 发送文档文件

    Args:
        bot_token: Telegram Bot Token
        chat_id: Telegram Chat ID
        filepath: 文件路径
        caption: 文件说明

    Returns:
        是否成功
    """
    sender = TelegramSender(bot_token, chat_id)
    return asyncio.run(sender.send_document(Path(filepath), caption))
