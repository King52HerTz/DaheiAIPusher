import unittest

from src.feed import FeedItem, parse_feed, unseen_items


SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>大黑AI速报</title>
    <item>
      <title>第2期</title>
      <link>https://example.com/2</link>
      <description>第二期摘要</description>
      <content:encoded><![CDATA[<p>第二期完整内容</p>]]></content:encoded>
      <pubDate>Wed, 15 Jul 2026 20:01:00 +0800</pubDate>
      <guid isPermaLink="false">issue-2</guid>
    </item>
    <item>
      <title>第1期</title>
      <link>https://example.com/1</link>
      <description>第一期摘要</description>
      <guid isPermaLink="false">issue-1</guid>
    </item>
  </channel>
</rss>
"""


class FeedTests(unittest.TestCase):
    def test_parse_feed_reads_guid_and_full_content(self):
        items = parse_feed(SAMPLE_RSS)
        self.assertEqual([item.guid for item in items], ["issue-2", "issue-1"])
        self.assertIn("第二期完整内容", items[0].content_html)
        self.assertEqual(items[1].content_html, "第一期摘要")

    def test_unseen_items_are_returned_oldest_first(self):
        items = [
            FeedItem(str(number), str(number), f"https://e/{number}", "", "", "")
            for number in (4, 3, 2, 1)
        ]
        pending, found = unseen_items(items, "2")
        self.assertTrue(found)
        self.assertEqual([item.guid for item in pending], ["3", "4"])

    def test_missing_guid_limits_catchup(self):
        items = [
            FeedItem(str(number), str(number), f"https://e/{number}", "", "", "")
            for number in (5, 4, 3, 2, 1)
        ]
        pending, found = unseen_items(items, "missing", max_catchup_items=2)
        self.assertFalse(found)
        self.assertEqual([item.guid for item in pending], ["4", "5"])


if __name__ == "__main__":
    unittest.main()

