"""
Markdown导出器
将对话导出为结构清晰的Markdown文件
"""
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
import json
import re

from ..models import Conversation, Message, MessageRole


@dataclass
class ExportOptions:
    """导出选项"""
    # 是否包含元数据头部
    include_metadata: bool = True
    # 是否包含时间戳
    include_timestamps: bool = True
    # 是否包含Token统计
    include_token_stats: bool = True
    # 是否包含来源URL
    include_source_url: bool = True
    # 是否使用代码块格式化长内容
    use_code_blocks: bool = False
    # 代码块语言（当use_code_blocks=True时）
    code_block_language: str = ""
    # 自定义标题
    custom_title: Optional[str] = None
    # 是否包含消息索引
    include_message_index: bool = True
    # 是否包含摘要
    include_summary: bool = False
    # 最大内容长度（超过则截断）
    max_content_length: Optional[int] = None
    # 截断后缀
    truncate_suffix: str = "\n\n... (内容已截断)"


class ContentFormatter:
    """
    内容格式化器
    智能识别并格式化代码块、表格等特殊内容
    """

    # 常见编程语言的关键字模式
    LANGUAGE_PATTERNS = {
        'python': [
            r'\bdef\s+\w+\s*\(',
            r'\bimport\s+\w+',
            r'\bfrom\s+\w+\s+import',
            r'\bclass\s+\w+',
            r'@\w+\s*\n\s*def',  # 装饰器
            r'if\s+__name__\s*==\s*["\']__main__["\']',
        ],
        'bash': [
            r'^\s*#\s*!/bin/(bash|sh)',
            r'^\s*(apt|yum|brew|npm|pip|git|docker|kubectl|openclaw)\s+',
            r'^\s*(curl|wget|chmod|mkdir|cd|ls|cp|mv|rm|cat|echo)\s+',
            r'^\s*export\s+\w+=',
            r'\|\s*(grep|sed|awk|sort|uniq|head|tail)',
            r'\$\{?\w+\}?',  # 环境变量
        ],
        'javascript': [
            r'\b(function|const|let|var)\s+\w+\s*[=\(]',
            r'\basync\s+function',
            r'=>\s*\{',
            r'console\.(log|error|warn)',
            r'document\.(querySelector|getElementById)',
        ],
        'json': [
            r'^\s*\{',
            r'"\w+"\s*:',
            r'\[\s*\{',
        ],
        'sql': [
            r'\b(SELECT|INSERT|UPDATE|DELETE|CREATE|ALTER|DROP)\b',
            r'\bFROM\s+\w+',
            r'\bWHERE\s+\w+',
        ],
    }

    @classmethod
    def detect_language(cls, code: str) -> str:
        """检测代码语言"""
        # 清理代码
        code_clean = code.strip()

        # 计分系统
        scores = {lang: 0 for lang in cls.LANGUAGE_PATTERNS}

        for lang, patterns in cls.LANGUAGE_PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, code_clean, re.MULTILINE | re.IGNORECASE)
                scores[lang] += len(matches)

        # 返回得分最高的语言
        if max(scores.values()) > 0:
            return max(scores, key=scores.get)
        return ""

    @classmethod
    def is_code_block(cls, text: str) -> tuple:
        """
        判断文本是否为代码块
        返回: (is_code, language)
        """
        text = text.strip()

        # 空文本
        if not text or len(text) < 10:
            return False, ""

        # 已经是代码块格式
        if text.startswith('```'):
            return True, ""

        # 行数较少但看起来像命令
        lines = text.split('\n')

        # 单行命令判断
        if len(lines) == 1:
            # 常见命令行模式
            cmd_patterns = [
                r'^(apt|brew|npm|pip|git|docker|kubectl|curl|wget|openclaw)\s+',
                r'^\$\s+',  # 带提示符的命令
            ]
            for pattern in cmd_patterns:
                if re.match(pattern, text.strip()):
                    return True, 'bash'

        # 多行代码判断
        if len(lines) >= 2:
            # 检测语言
            lang = cls.detect_language(text)
            if lang:
                return True, lang

        # 检查是否包含典型的代码特征
        code_indicators = [
            r'[{}\[\]()]',  # 括号
            r'[=<>!]=',  # 比较运算符
            r'\b(if|else|for|while|return|function)\b',  # 关键字
            r'\$\w+',  # 变量
            r'//|#.*$',  # 注释
        ]

        indicator_count = 0
        for pattern in code_indicators:
            if re.search(pattern, text, re.MULTILINE):
                indicator_count += 1

        if indicator_count >= 3:
            lang = cls.detect_language(text)
            return True, lang

        return False, ""

    @classmethod
    def format_content(cls, content: str) -> str:
        """
        格式化消息内容
        智能识别代码块、表格等并正确格式化
        """
        if not content:
            return ""

        # 按段落分割
        paragraphs = content.split('\n\n')
        formatted_parts = []

        i = 0
        while i < len(paragraphs):
            para = paragraphs[i].strip()

            if not para:
                i += 1
                continue

            # 检查是否为代码块
            is_code, lang = cls.is_code_block(para)

            # 如果当前段落不是代码，但后续段落看起来是代码块的一部分
            if not is_code and i + 1 < len(paragraphs):
                combined = para + '\n\n' + paragraphs[i + 1]
                is_code_combined, lang_combined = cls.is_code_block(combined)
                if is_code_combined:
                    # 合并段落
                    code_content = combined
                    j = i + 2
                    while j < len(paragraphs):
                        next_para = paragraphs[j].strip()
                        if cls.is_code_block(next_para)[0] or cls.is_code_block(code_content + '\n\n' + next_para)[0]:
                            code_content += '\n\n' + next_para
                            j += 1
                        else:
                            break

                    if lang_combined:
                        formatted_parts.append(f"```{lang_combined}\n{code_content}\n```")
                    else:
                        formatted_parts.append(f"```\n{code_content}\n```")
                    i = j
                    continue

            if is_code:
                # 检查是否需要合并后续代码段落
                code_content = para
                j = i + 1
                while j < len(paragraphs):
                    next_para = paragraphs[j].strip()
                    next_is_code, _ = cls.is_code_block(next_para)
                    if next_is_code:
                        code_content += '\n\n' + next_para
                        j += 1
                    else:
                        break

                if lang:
                    formatted_parts.append(f"```{lang}\n{code_content}\n```")
                else:
                    # 重新检测合并后的代码
                    final_lang = cls.detect_language(code_content)
                    if final_lang:
                        formatted_parts.append(f"```{final_lang}\n{code_content}\n```")
                    else:
                        formatted_parts.append(f"```\n{code_content}\n```")
                i = j
            else:
                formatted_parts.append(para)
                i += 1

        return '\n\n'.join(formatted_parts)


class MarkdownExporter:
    """
    Markdown导出器

    将对话数据导出为结构清晰的Markdown文件
    支持增量导出和断点续传
    """

    def __init__(self, output_dir: str = "./output"):
        """
        初始化导出器

        Args:
            output_dir: 输出目录
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        conversation: Conversation,
        options: ExportOptions = None,
        filename: Optional[str] = None
    ) -> Path:
        """
        导出对话到Markdown文件

        Args:
            conversation: 对话对象
            options: 导出选项
            filename: 自定义文件名（不含扩展名）

        Returns:
            导出文件路径
        """
        options = options or ExportOptions()

        # 生成文件名
        if not filename:
            filename = self._generate_filename(conversation)

        file_path = self.output_dir / f"{filename}.md"

        # 生成Markdown内容
        content = self._generate_markdown(conversation, options)

        # 写入文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)

        return file_path

    def export_messages(
        self,
        messages: List[Message],
        title: str,
        source_url: str = "",
        options: ExportOptions = None,
        filename: Optional[str] = None
    ) -> Path:
        """
        导出选中的消息

        Args:
            messages: 消息列表
            title: 对话标题
            source_url: 来源URL
            options: 导出选项
            filename: 自定义文件名

        Returns:
            导出文件路径
        """
        # 创建临时对话对象
        conversation = Conversation(
            id="",
            title=title,
            source_url=source_url,
            messages=messages,
            total_messages=len(messages)
        )

        return self.export(conversation, options, filename)

    def export_incremental(
        self,
        conversation: Conversation,
        start_index: int,
        end_index: int,
        options: ExportOptions = None,
        temp_file: Optional[Path] = None
    ) -> Path:
        """
        增量导出对话片段

        Args:
            conversation: 对话对象
            start_index: 起始消息索引
            end_index: 结束消息索引
            options: 导出选项
            temp_file: 临时文件路径（用于追加）

        Returns:
            临时文件路径
        """
        options = options or ExportOptions()

        messages = conversation.messages[start_index:end_index]

        if temp_file and temp_file.exists():
            # 追加模式
            with open(temp_file, 'a', encoding='utf-8') as f:
                for i, msg in enumerate(messages):
                    f.write(self._format_message(msg, start_index + i, options))
                    f.write("\n\n")
            return temp_file
        else:
            # 创建新的临时文件
            filename = f"{self._generate_filename(conversation)}_temp"
            temp_file = self.output_dir / f"{filename}.md"

            # 写入头部
            header = self._generate_header(conversation, options)
            with open(temp_file, 'w', encoding='utf-8') as f:
                f.write(header)
                f.write("\n\n---\n\n")

            # 写入消息
            with open(temp_file, 'a', encoding='utf-8') as f:
                for i, msg in enumerate(messages):
                    f.write(self._format_message(msg, start_index + i, options))
                    f.write("\n\n")

            return temp_file

    def finalize_export(
        self,
        temp_file: Path,
        conversation: Conversation,
        options: ExportOptions = None
    ) -> Path:
        """
        完成导出（将临时文件转为最终文件）

        Args:
            temp_file: 临时文件路径
            conversation: 对话对象
            options: 导出选项

        Returns:
            最终文件路径
        """
        options = options or ExportOptions()

        # 生成最终文件名
        final_filename = self._generate_filename(conversation)
        final_path = self.output_dir / f"{final_filename}.md"

        # 添加尾部信息
        footer = self._generate_footer(conversation, options)

        with open(temp_file, 'a', encoding='utf-8') as f:
            f.write("\n---\n\n")
            f.write(footer)

        # 重命名文件
        temp_file.rename(final_path)

        return final_path

    def _generate_filename(self, conversation: Conversation) -> str:
        """生成文件名"""
        # 清理标题中的非法字符
        title = conversation.title or "未命名对话"
        safe_title = re.sub(r'[<>:"/\\|?*]', '', title)
        safe_title = safe_title[:50]  # 限制长度

        # 添加时间戳
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        return f"{safe_title}_{timestamp}"

    def _generate_markdown(self, conversation: Conversation, options: ExportOptions) -> str:
        """生成完整的Markdown内容"""
        parts = []

        # 头部
        parts.append(self._generate_header(conversation, options))
        parts.append("\n\n---\n\n")

        # 消息列表
        for i, msg in enumerate(conversation.messages):
            parts.append(self._format_message(msg, i, options))
            parts.append("\n\n")

        # 尾部
        parts.append("---\n\n")
        parts.append(self._generate_footer(conversation, options))

        return "".join(parts)

    def _generate_header(self, conversation: Conversation, options: ExportOptions) -> str:
        """生成Markdown头部"""
        lines = []

        # 标题
        title = options.custom_title or conversation.title
        lines.append(f"# {title}")
        lines.append("")

        if options.include_metadata:
            lines.append("## 📋 对话信息")
            lines.append("")

            if options.include_source_url and conversation.source_url:
                lines.append(f"- **来源**: {conversation.source_url}")

            if options.include_timestamps:
                if conversation.created_at:
                    lines.append(f"- **创建时间**: {conversation.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
                if conversation.updated_at:
                    lines.append(f"- **更新时间**: {conversation.updated_at.strftime('%Y-%m-%d %H:%M:%S')}")

            lines.append(f"- **消息数量**: {len(conversation.messages)}")

            if options.include_token_stats:
                lines.append(f"- **预估Token数**: {conversation.total_tokens}")

            lines.append("")

        return "\n".join(lines)

    def _format_message(self, message: Message, index: int, options: ExportOptions) -> str:
        """格式化单条消息"""
        lines = []

        # 检查是否为思考过程
        is_thinking = message.metadata.get("isThinking", False) if message.metadata else False

        # 消息标题
        if is_thinking:
            role_emoji = "🤔"
            role_name = "思考过程"
        elif message.role == MessageRole.USER:
            role_emoji = "👤"
            role_name = "用户"
        else:
            role_emoji = "🤖"
            role_name = "助手"

        if options.include_message_index:
            lines.append(f"### {role_emoji} {role_name} (#{index + 1})")
        else:
            lines.append(f"### {role_emoji} {role_name}")

        lines.append("")

        # 时间戳
        if options.include_timestamps and message.timestamp:
            lines.append(f"*{message.timestamp.strftime('%Y-%m-%d %H:%M:%S')}*")
            lines.append("")

        # 摘要（如果内容未加载）
        if options.include_summary and message.summary and not message.is_loaded:
            lines.append(f"> **摘要**: {message.summary}")
            lines.append("")

        # 内容
        content = message.content or "*（内容未加载）*"

        # 截断处理
        if options.max_content_length and len(content) > options.max_content_length:
            content = content[:options.max_content_length] + options.truncate_suffix

        # 格式化内容 - 使用智能格式化器
        if message.role == MessageRole.ASSISTANT:
            content = ContentFormatter.format_content(content)

        lines.append(content)

        # Token统计
        if options.include_token_stats and message.token_count > 0:
            lines.append("")
            lines.append(f"<small>Token数: {message.token_count}</small>")

        return "\n".join(lines)

    def _generate_footer(self, conversation: Conversation, options: ExportOptions) -> str:
        """生成Markdown尾部"""
        lines = []

        lines.append("## 📊 导出统计")
        lines.append("")
        lines.append(f"- 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"- 总消息数: {len(conversation.messages)}")

        if options.include_token_stats:
            lines.append(f"- 总Token数: {conversation.total_tokens}")

        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("*由 Knotclaw 大模型对话归档客户端导出*")

        return "\n".join(lines)

    def export_to_json(
        self,
        conversation: Conversation,
        filename: Optional[str] = None
    ) -> Path:
        """
        导出为JSON格式（用于备份或迁移）

        Args:
            conversation: 对话对象
            filename: 自定义文件名

        Returns:
            导出文件路径
        """
        if not filename:
            filename = self._generate_filename(conversation)

        file_path = self.output_dir / f"{filename}.json"

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(conversation.to_dict(include_content=True), f, ensure_ascii=False, indent=2)

        return file_path