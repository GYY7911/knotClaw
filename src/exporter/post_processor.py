"""
Markdown 后处理器
对导出的 Markdown 内容进行格式优化，提升可读性
"""
import re
from typing import List, Tuple, Optional


def number_to_chinese(num: int, abbreviate: bool = True) -> str:
    """
    将数字转换为中文数字

    Args:
        num: 阿拉伯数字
        abbreviate: 是否缩写（如 "一十" -> "十"）

    Returns:
        中文数字字符串
    """
    if num < 0 or num > 9999:
        return str(num)

    if num == 0:
        return "零"

    # 0-9 直接映射
    if num < 10:
        return "零一二三四五六七八九"[num]

    # 10 特殊处理
    if num == 10:
        return "一十" if not abbreviate else "十"

    # 11-99
    if num < 100:
        tens = num // 10
        ones = num % 10
        result = f"{number_to_chinese(tens)}十"
        if ones > 0:
            result += number_to_chinese(ones)
        if abbreviate and result.startswith("一十"):
            result = result[1:]
        return result

    # 100-999
    if num < 1000:
        hundreds = num // 100
        remainder = num % 100
        result = f"{number_to_chinese(hundreds)}百"
        if remainder > 0:
            if remainder < 10:
                result += f"零{number_to_chinese(remainder)}"
            else:
                result += number_to_chinese(remainder, abbreviate=False)
        return result

    # 1000-9999
    if num < 10000:
        thousands = num // 1000
        remainder = num % 1000
        result = f"{number_to_chinese(thousands)}千"
        if remainder > 0:
            if remainder < 100:
                result += f"零{number_to_chinese(remainder)}"
            else:
                result += number_to_chinese(remainder, abbreviate=False)
        return result

    return str(num)


# 中文数字映射（向后兼容，用于简单场景）
NUM_CN = {i: number_to_chinese(i) for i in range(1, 11)}

# 命令行关键词（用于代码块检测）- 移除重复项
COMMAND_KEYWORDS = [
    'apt', 'yum', 'brew', 'pip', 'git', 'docker', 'kubectl',
    'curl', 'wget', 'chmod', 'mkdir', 'cd', 'ls', 'cp', 'mv', 'rm',
    'cat', 'echo', 'export', 'source', 'openclaw', 'clawhub',
    'agent-reach', 'python', 'node', 'npm', 'yarn', 'pnpm'
]


class MarkdownPostProcessor:
    """
    Markdown 后处理器

    核心功能：
    1. 阶段/步骤标题格式化
    2. 列表项加粗
    3. 代码块检测与格式化
    """

    # 阶段/步骤标题模式
    PHASE_PATTERNS = [
        # 第X阶段
        (r'^(第[一二三四五六七八九十百千]+阶段)[：:]\s*(.+)$', None),
        # 第X步
        (r'^(第[一二三四五六七八九十百千]+步)[：:]\s*(.+)$', None),
        # 关键环节X
        (r'^(关键环节[一二三四五六七八九十百千]+)[：:]\s*(.+)$', None),
    ]

    # Step X -> 第X步 转换模式
    STEP_PATTERN = re.compile(r'^[Ss]tep\s*(\d+)[：:]\s*(.+)$')

    # 列表项加粗模式：匹配 "1. 标题：" 或 "- 标题：" 格式
    LIST_ITEM_PATTERN = re.compile(
        r'^(\s*)([-*]|\d+\.)\s+([^：:\n]+[：:])(\s*)$'
    )

    def process(self, content: str) -> str:
        """
        处理内容，应用所有格式化规则

        Args:
            content: 原始 Markdown 内容

        Returns:
            格式化后的 Markdown 内容
        """
        if not content:
            return content

        # 按行处理
        lines = content.split('\n')
        processed_lines = []

        i = 0
        while i < len(lines):
            line = lines[i]

            # 检查是否在代码块内
            if line.strip().startswith('```'):
                # 保持代码块原样，找到结束位置
                processed_lines.append(line)
                i += 1
                while i < len(lines):
                    processed_lines.append(lines[i])
                    if lines[i].strip() == '```':
                        i += 1
                        break
                    i += 1
                continue

            # 应用阶段标题格式化
            line = self._format_phase_title(line)

            # 应用列表项加粗
            line = self._format_list_item(line)

            processed_lines.append(line)
            i += 1

        result = '\n'.join(processed_lines)

        # 处理代码块语言标记
        result = self._fix_code_blocks(result)

        return result

    def _format_phase_title(self, line: str) -> str:
        """
        格式化阶段/步骤标题

        Examples:
            第一阶段：xxx -> ### 第一阶段：xxx
            Step 1：xxx -> ### 第一步：xxx
        """
        # 检查是否已经是标题格式
        if line.strip().startswith('#'):
            return line

        stripped = line.strip()
        indent = len(line) - len(line.lstrip())

        # 尝试匹配阶段模式
        for pattern, _ in self.PHASE_PATTERNS:
            match = re.match(pattern, stripped)
            if match:
                groups = match.groups()
                if len(groups) >= 2:
                    return ' ' * indent + f'### {groups[0]}：{groups[1]}'

        # 尝试匹配 Step X 模式
        match = self.STEP_PATTERN.match(stripped)
        if match:
            step_num = int(match.group(1))
            step_cn = NUM_CN.get(step_num, str(step_num))
            title = match.group(2)
            return ' ' * indent + f'### 第{step_cn}步：{title}'

        return line

    def _format_list_item(self, line: str) -> str:
        """
        格式化列表项，对标题部分加粗

        Examples:
            1. 目标学员画像： -> 1. **目标学员画像：**
            - 课程MVP： -> - **课程MVP：**
        """
        match = self.LIST_ITEM_PATTERN.match(line)
        if match:
            indent = match.group(1)
            bullet = match.group(2)
            title = match.group(3)

            # 检查标题是否已经被加粗
            if title.startswith('**') and title.endswith('**'):
                return line

            return f'{indent}{bullet} **{title}**'

        return line

    def _fix_code_blocks(self, content: str) -> str:
        """
        修复代码块格式

        1. 将 ```text 改为 ```bash（如果包含命令行内容）
        2. 检测无语言标记但有命令关键词的代码块
        """
        # 替换 ```text 为 ```bash
        def replace_text_block(match):
            block_content = match.group(1)
            if self._is_command_block(block_content):
                return '```bash\n' + block_content + '```'
            return match.group(0)

        # 匹配 ```text ... ```
        pattern = r'```text\n(.*?)```'
        content = re.sub(pattern, replace_text_block, content, flags=re.DOTALL)

        # 检测无语言标记的代码块
        def check_plain_block(match):
            lang = match.group(1) or ''
            block_content = match.group(2)

            # 如果没有语言标记且内容看起来像命令
            if not lang and self._is_command_block(block_content):
                return '```bash\n' + block_content + '```'

            return match.group(0)

        # 匹配 ```[lang] ... ```
        pattern = r'```(\w*)\n(.*?)```'
        content = re.sub(pattern, check_plain_block, content, flags=re.DOTALL)

        return content

    def _is_command_block(self, content: str) -> bool:
        """
        检测内容是否为命令行代码

        更严格的检测：
        1. 必须有多行内容（或单行命令）
        2. 命令行不能包含制表符分隔的表格特征
        3. 超过 70% 的非空行必须是命令

        Args:
            content: 代码块内容

        Returns:
            是否为命令行代码
        """
        lines = content.strip().split('\n')
        command_count = 0

        # 单行内容：必须是明确的命令
        if len(lines) == 1:
            line = lines[0].strip()
            first_word = line.split()[0] if line.split() else ''
            return first_word in COMMAND_KEYWORDS

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # 检测表格特征：制表符分隔的多列内容
            # 如果一行包含多个制表符且看起来像表格，跳过
            if '\t' in line and line.count('\t') >= 2:
                continue

            # 检查是否以命令关键词开头
            first_word = line.split()[0] if line.split() else ''
            if first_word in COMMAND_KEYWORDS:
                command_count += 1

        # 如果超过 70% 的非空行是命令，则认为是命令块
        non_empty_lines = [l for l in lines if l.strip() and not l.strip().startswith('#')]
        if non_empty_lines and len(non_empty_lines) > 0:
            ratio = command_count / len(non_empty_lines)
            return ratio > 0.7

        return False


def process_content(content: str) -> str:
    """
    便捷函数：处理 Markdown 内容

    Args:
        content: 原始内容

    Returns:
        格式化后的内容
    """
    processor = MarkdownPostProcessor()
    return processor.process(content)
