"""Build a browser preview of the latest styled WxPusher message."""

from pathlib import Path

from src.feed import fetch_feed
from src.wxpusher import build_message


def main() -> None:
    latest = fetch_feed()[0]
    message = build_message(latest)
    document = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>WxPusher Preview</title></head>"
        "<body style='margin:0;background:#dfe5ef;padding:24px 0'>"
        f"{message.content}</body></html>"
    )
    output = Path("preview.html")
    output.write_text(document, encoding="utf-8")
    print(output.resolve())


if __name__ == "__main__":
    main()
