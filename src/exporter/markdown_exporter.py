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
        
        # 消息标题
        role_emoji = "👤" if message.role == MessageRole.USER else "🤖"
        role_name = "用户" if message.role == MessageRole.USER else "助手"
        
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
        
        # 格式化内容
        if options.use_code_blocks and message.role == MessageRole.ASSISTANT:
            lang = options.code_block_language
            lines.append(f"```{lang}")
            lines.append(content)
            lines.append("```")
        else:
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