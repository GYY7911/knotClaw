"""
Markdown 后处理器单元测试
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

import unittest
from src.exporter.post_processor import (
    MarkdownPostProcessor,
    process_content,
    number_to_chinese,
    NUM_CN,
    COMMAND_KEYWORDS
)
from src.exporter.platform_utils import (
    _get_platform_info,
    get_platform_from_url,
    get_platform_from_source,
    get_platform_key
)


class TestNumberToChinese(unittest.TestCase):
    """数字转中文函数测试"""

    def test_single_digit(self):
        """测试单个数字"""
        self.assertEqual(number_to_chinese(1), "一")
        self.assertEqual(number_to_chinese(5), "五")
        self.assertEqual(number_to_chinese(9), "九")

    def test_ten(self):
        """测试 10"""
        self.assertEqual(number_to_chinese(10), "十")

    def test_teens(self):
        """测试 11-19"""
        self.assertEqual(number_to_chinese(11), "十一")
        self.assertEqual(number_to_chinese(15), "十五")
        self.assertEqual(number_to_chinese(19), "十九")

    def test_tens(self):
        """测试整十数"""
        self.assertEqual(number_to_chinese(20), "二十")
        self.assertEqual(number_to_chinese(50), "五十")
        self.assertEqual(number_to_chinese(90), "九十")

    def test_composite_numbers(self):
        """测试复合数字"""
        self.assertEqual(number_to_chinese(21), "二十一")
        self.assertEqual(number_to_chinese(99), "九十九")

    def test_hundreds(self):
        """测试百位数"""
        self.assertEqual(number_to_chinese(100), "一百")
        self.assertEqual(number_to_chinese(101), "一百零一")
        self.assertEqual(number_to_chinese(110), "一百一十")
        self.assertEqual(number_to_chinese(111), "一百一十一")
        self.assertEqual(number_to_chinese(120), "一百二十")
        self.assertEqual(number_to_chinese(999), "九百九十九")

    def test_edge_cases(self):
        """测试边界情况"""
        self.assertEqual(number_to_chinese(0), "零")
        self.assertEqual(number_to_chinese(-1), "-1")  # 负数返回字符串
        self.assertEqual(number_to_chinese(10000), "10000")  # 超出范围返回字符串

    def test_num_cn_dict(self):
        """测试预计算的数字映射"""
        self.assertEqual(NUM_CN[1], "一")
        self.assertEqual(NUM_CN[5], "五")
        self.assertEqual(NUM_CN[10], "十")


class TestCommandKeywords(unittest.TestCase):
    """命令关键词测试"""

    def test_no_duplicates(self):
        """确保没有重复项"""
        self.assertEqual(len(COMMAND_KEYWORDS), len(set(COMMAND_KEYWORDS)))

    def test_common_commands_present(self):
        """确保常见命令存在"""
        essential_commands = ['npm', 'pip', 'git', 'docker', 'curl', 'python']
        for cmd in essential_commands:
            self.assertIn(cmd, COMMAND_KEYWORDS, f"Missing command: {cmd}")


class TestMarkdownPostProcessor(unittest.TestCase):
    """Markdown 后处理器测试"""

    def setUp(self):
        self.processor = MarkdownPostProcessor()

    def test_empty_content(self):
        """测试空内容"""
        self.assertEqual(self.processor.process(""), "")
        self.assertEqual(self.processor.process(None), None)

    def test_phase_title_formatting(self):
        """测试阶段标题格式化"""
        test_cases = [
            ("第一阶段：开始", "### 第一阶段：开始"),
            ("第二阶段：进行中", "### 第二阶段：进行中"),
            ("第十阶段：结束", "### 第十阶段：结束"),
            ("关键环节一：设计", "### 关键环节一：设计"),
            ("第二步：实现", "### 第二步：实现"),
        ]
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = self.processor.process(input_text)
                self.assertEqual(result, expected)

    def test_phase_title_with_colon_variants(self):
        """测试不同冒号格式"""
        # 中文冒号
        self.assertIn("### 第一阶段：", self.processor.process("第一阶段：测试"))
        # 英文冒号
        self.assertIn("### 第一阶段：", self.processor.process("第一阶段: 测试"))

    def test_step_conversion(self):
        """测试 Step 转中文"""
        test_cases = [
            ("Step 1：开始", "### 第一步：开始"),
            ("step 2：继续", "### 第二步：继续"),
            ("Step1：简洁", "### 第一步：简洁"),
            # 使用半角冒号的英文格式
            ("Step 1: English", "### 第一步：English"),
        ]
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = self.processor.process(input_text)
                self.assertEqual(result, expected)

    def test_list_item_bold(self):
        """测试列表项加粗"""
        test_cases = [
            ("1. 标题：", "1. **标题：**"),
            ("2. 目标学员画像：", "2. **目标学员画像：**"),
            ("- 课程MVP：", "- **课程MVP：**"),
            ("* 简单列表：", "* **简单列表：**"),
        ]
        for input_text, expected in test_cases:
            with self.subTest(input_text=input_text):
                result = self.processor.process(input_text)
                self.assertEqual(result, expected)

    def test_list_item_with_content_preserved(self):
        """测试列表项后内容保留"""
        # 列表项后的换行内容应该保留
        content = "1. 标题：\n   这是描述内容"
        result = self.processor.process(content)
        self.assertIn("1. **标题：**", result)
        self.assertIn("   这是描述内容", result)

    def test_list_item_already_bold(self):
        """测试已加粗的列表项不重复处理"""
        content = "1. **已加粗：**"
        result = self.processor.process(content)
        self.assertEqual(result, content)  # 保持不变

    def test_code_block_preserved(self):
        """测试代码块内容保持原样"""
        content = """```
第一阶段：这不应该被处理
1. 标题：也不应该被加粗
```"""
        result = self.processor.process(content)
        self.assertIn("第一阶段：这不应该被处理", result)
        self.assertIn("1. 标题：也不应该被加粗", result)

    def test_code_block_text_to_bash(self):
        """测试 text 代码块转 bash"""
        content = """```text
npm install
pip install requests
```"""
        result = self.processor.process(content)
        self.assertIn("```bash", result)
        self.assertNotIn("```text", result)

    def test_code_block_plain_to_bash(self):
        """测试无语言标记的命令块转 bash"""
        content = """```
git clone https://github.com/test/repo.git
cd repo
npm install
```"""
        result = self.processor.process(content)
        self.assertIn("```bash", result)

    def test_code_block_non_command_preserved(self):
        """测试非命令代码块保持原样"""
        content = """```
这是一段普通文字
不是命令
```"""
        result = self.processor.process(content)
        # 不应该被转换为 bash
        self.assertNotIn("```bash", result)

    def test_existing_heading_preserved(self):
        """测试已有标题不被重复处理"""
        content = "### 第一阶段：已存在"
        result = self.processor.process(content)
        self.assertEqual(result, content)

    def test_indentation_preserved(self):
        """测试缩进保持"""
        content = "  第一阶段：有缩进"
        result = self.processor.process(content)
        self.assertTrue(result.startswith("  ###"))

    def test_complex_content(self):
        """测试复杂内容"""
        content = """# 标题

第一阶段：准备

1. 目标：
   描述内容

2. 计划：
   更多内容

```bash
npm run build
```

Step 1：开始实施"""

        result = self.processor.process(content)

        # 验证各部分
        self.assertIn("### 第一阶段：准备", result)
        self.assertIn("1. **目标：**", result)
        self.assertIn("2. **计划：**", result)
        self.assertIn("### 第一步：开始实施", result)

    def test_process_content_function(self):
        """测试便捷函数"""
        content = "第一阶段：测试"
        result = process_content(content)
        self.assertIn("### 第一阶段：测试", result)


class TestPlatformUtils(unittest.TestCase):
    """平台识别工具测试"""

    def test_get_platform_info_deepseek(self):
        """测试 DeepSeek 平台识别"""
        key, name = _get_platform_info("https://chat.deepseek.com/share/test123")
        self.assertEqual(key, "deepseek")
        self.assertEqual(name, "DeepSeek")

    def test_get_platform_from_url(self):
        """测试 URL 平台识别"""
        result = get_platform_from_url("https://chat.deepseek.com/share/abc")
        self.assertEqual(result, "DeepSeek")

    def test_get_platform_from_source(self):
        """测试来源 URL 识别（别名函数）"""
        result = get_platform_from_source("https://chat.deepseek.com/share/abc")
        self.assertEqual(result, "DeepSeek")

    def test_get_platform_key(self):
        """测试平台 key 获取"""
        result = get_platform_key("https://chat.deepseek.com/share/abc")
        self.assertEqual(result, "deepseek")

    def test_unknown_platform(self):
        """测试未知平台"""
        result = get_platform_from_url("https://unknown.com/share/abc")
        self.assertEqual(result, "Unknown")

        key = get_platform_key("https://unknown.com/share/abc")
        self.assertEqual(key, "unknown")

    def test_gemini_platform(self):
        """测试 Gemini 平台"""
        # 注意：实际 Gemini URL 格式可能不同
        result = get_platform_from_url("https://gemini.google.com/share/test")
        # 如果 Gemini fetcher 注册了，应该返回 Gemini
        # 否则返回 Unknown
        self.assertIn(result, ["Gemini", "Unknown"])


class TestEdgeCases(unittest.TestCase):
    """边界情况测试"""

    def setUp(self):
        self.processor = MarkdownPostProcessor()

    def test_mixed_colons(self):
        """测试混合冒号"""
        content = "第一阶段:中英文冒号混用：测试"
        result = self.processor.process(content)
        # 应该能正确处理
        self.assertIn("###", result)

    def test_multiple_phase_titles(self):
        """测试多个阶段标题"""
        content = """第一阶段：开始

第二阶段：进行

第三阶段：结束"""
        result = self.processor.process(content)
        self.assertEqual(result.count("###"), 3)

    def test_nested_code_blocks_not_processed(self):
        """测试代码块内嵌套的格式不被处理"""
        content = """```markdown
# 这是示例
第一阶段：示例
1. 列表项：
```"""
        result = self.processor.process(content)
        # 代码块内容不应被处理
        self.assertIn("第一阶段：示例", result)

    def test_large_step_number(self):
        """测试大数字步骤"""
        content = "Step 15：大数字步骤"
        result = self.processor.process(content)
        # Step 15 应该转换为 "15"（因为超出预定义范围）
        self.assertIn("### 第", result)

    def test_chinese_number_in_phase(self):
        """测试中文数字阶段"""
        content = "第十一阶段：超过十"
        result = self.processor.process(content)
        # 应该能识别
        self.assertIn("### 第十一阶段", result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
