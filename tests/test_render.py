import unittest

from src.feed import FeedItem
from src.render import build_message, parse_news


def make_item(**overrides) -> FeedItem:
    base = dict(
        guid="issue-1",
        title="第1期",
        link="https://example.com/1",
        summary="摘要",
        content_html="<p>完整内容</p>",
        published="",
    )
    base.update(overrides)
    return FeedItem(**base)


class RenderTests(unittest.TestCase):
    def test_build_message_is_deterministic(self):
        item = make_item(published="2026-07-15 20:01")
        self.assertEqual(build_message(item), build_message(item))
        self.assertIn("完整内容", build_message(item).content)
        self.assertIn("DAHEI AI BRIEF", build_message(item).content)
        self.assertIn("去原网页看完整速报", build_message(item).content)

    def test_summary_mode_does_not_include_full_content(self):
        item = make_item(summary="本期摘要")
        message = build_message(item, content_mode="summary")
        self.assertIn("本期摘要", message.content)
        self.assertNotIn("完整内容", message.content)

    def test_full_mode_turns_rss_items_into_styled_cards(self):
        item = make_item(
            guid="issue-2",
            title="第1496期 - 2026-07-16 00:01",
            content_html=(
                "<h3>速报总结</h3><p>本期重点内容</p>"
                "<h3>本期内容（共1条）</h3><ul><li>"
                "<strong>[模型动态] 新模型正式发布</strong><br/>模型能力显著提升。"
                "<br/><small>来源：<a href='https://source.example'>官方</a></small>"
                "</li></ul>"
            ),
        )
        message = build_message(item)
        self.assertIn("模型动态", message.content)
        self.assertIn("新模型正式发布", message.content)
        self.assertIn("◆ AI 总结", message.content)
        self.assertIn("[1] &nbsp;查看信源", message.content)
        self.assertIn("本期重点内容", message.content)
        self.assertIn('href="https://source.example"', message.content)
        self.assertIn("官方 &nbsp;↗", message.content)

    def test_full_mode_groups_categories_in_editorial_order(self):
        item = make_item(
            guid="issue-3",
            title="第1497期",
            content_html=(
                "<ul>"
                "<li><strong>[行业资讯] 行业新闻</strong><br/>内容一</li>"
                "<li><strong>[模型动态] 模型新闻</strong><br/>内容二</li>"
                "</ul>"
            ),
        )
        content = build_message(item).content
        self.assertLess(content.index("模型动态"), content.index("行业资讯"))

    def test_parse_news_extracts_structured_entries(self):
        item = make_item(
            content_html=(
                "<h3>速报总结</h3><p>解析测试摘要</p>"
                "<ul><li>"
                "<strong>[产品工具] 工具新版上线</strong><br/>支持批量处理。"
                "<br/><small>来源：<a href='https://source.example'>官方博客</a> [官网]</small>"
                "</li></ul>"
            )
        )
        summary_text, entries = parse_news(item)
        self.assertEqual(summary_text, "解析测试摘要")
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertEqual(entry.category, "产品工具")
        self.assertEqual(entry.title, "工具新版上线")
        self.assertIn("支持批量处理", entry.description)
        self.assertEqual(entry.source_name, "官方博客")
        self.assertEqual(entry.source_url, "https://source.example")
        self.assertEqual(entry.source_kind, "官网")

    def test_long_content_degrades_to_summary_card(self):
        item = make_item(summary="超长降级摘要", content_html="<p>" + "字" * 40_000 + "</p>")
        message = build_message(item)
        self.assertIn("超长降级摘要", message.content)
        self.assertLessEqual(len(message.content), 40_000)


if __name__ == "__main__":
    unittest.main()
