import json
import os
import re
from datetime import datetime
from xml.sax.saxutils import escape

import dateutil.tz
import feedparser
from dotenv import load_dotenv
from feedgen.feed import FeedGenerator
from flask import Flask, send_file
from jinja2 import Template
from openai import OpenAI

load_dotenv()

app = Flask(__name__)

XKCD_FEED_URL = "https://xkcd.com/atom.xml"
PROCESSED_FILE = "assets/processed_comics.json"
SAVED_COMICS_INFO_FILE = "assets/saved_comics_info.json"
PROMPT_FILE = "assets/system.prompt.md"
FEED_CONTENT_TEMPLATE_FILE = "assets/content_html.template"
OUTPUT_FEED_FILE = "assets/atom.xml"

OPENAI_API_URL = os.getenv("OPENAI_API_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "google/gemini-2.0-flash-001")
XKCD_SERVICE_HOST = os.getenv("XKCD_SERVICE_HOST", "0.0.0.0")
XKCD_SERVICE_PORT = os.getenv("XKCD_SERVICE_PORT", "5000")
XKCD_SERVICE_URL = os.getenv("XKCD_SERVICE_URL", "http://127.0.0.1:5000")


def load_processed():
    """加载已处理的漫画 ID"""
    if os.path.exists(PROCESSED_FILE):
        with open(PROCESSED_FILE, "r") as f:
            return set(json.load(f))
    return set()


def save_processed(comic_id):
    """保存新处理的漫画 ID"""
    processed = load_processed()
    processed.add(comic_id)
    with open(PROCESSED_FILE, "w") as f:
        json.dump(list(processed), f)


def load_prompts():
    """加载 AI 解释提示文件"""
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()


def parse_xkcd_feed():
    """解析 xkcd Atom feed，提取未处理的漫画信息"""
    processed = load_processed()
    feed = feedparser.parse(XKCD_FEED_URL)
    comics = []

    for entry in feed.entries:
        comic_id = entry.id
        if comic_id not in processed:
            img_url = re.search(r'src="(.*?)"', entry.summary).group(1)
            comics.append(
                {
                    "id": comic_id,
                    "title": entry.title,
                    "published": entry.updated,
                    "img_url": img_url,
                    "description": re.search(r'title="(.*?)"', entry.summary).group(1),
                }
            )

    return comics


def explain_comic(
    system_prompt,
    comic_title,
    comic_description,
    img_url,
    model_name=OPENAI_MODEL_NAME,
):
    """使用 AI 解释漫画"""
    user_prompt = f"漫画标题：{comic_title}\n漫画官方描述：{comic_description}"

    client = OpenAI(base_url=OPENAI_API_URL, api_key=OPENAI_API_KEY)

    completion = client.chat.completions.create(
        extra_headers={
            "HTTP-Referer": "https://github.com/KrDw9ec4/xkcd-translater",  # Optional. Site URL for rankings on openrouter.ai.
            "X-Title": "xkcd-translater",  # Optional. Site title for rankings on openrouter.ai.
        },
        extra_body={},
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": img_url},
                    },
                ],
            },
        ],
    )

    return completion.choices[0].message.content


def save_comic_info(comic_info, file_path=SAVED_COMICS_INFO_FILE):
    """保存漫画信息到 JSON 文件"""
    # 读取现有数据
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []

    data.append(comic_info)

    # 写入更新数据
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        raise Exception(f"写入文件失败: {e}")


def load_comic_info(file_path=SAVED_COMICS_INFO_FILE):
    """加载漫画信息从 JSON 文件"""
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def generate_content_html(comic_info, template_file=FEED_CONTENT_TEMPLATE_FILE):
    """生成漫画内容的 HTML"""
    with open(template_file, "r", encoding="utf-8") as f:
        template_content = f.read()
    compressed_content = "".join(template_content.splitlines()).replace("  ", " ")
    template = Template(compressed_content)
    return template.render(data=comic_info, e=escape)


def generate_atom_feed(input_file=SAVED_COMICS_INFO_FILE, output_file=OUTPUT_FEED_FILE):
    """生成 Atom Feed 文件"""
    saved_comics_info = load_comic_info(input_file)

    fg = FeedGenerator()
    fg.id("https://github.com/KrDw9ec4/xkcd-translater")
    fg.title("xkcd-translater")
    fg.subtitle("使用大模型翻译和解释 xkcd 漫画")
    fg.link(href="https://xkcd.com/atom.xml", rel="alternate")
    fg.link(href=XKCD_SERVICE_URL + "/atom", rel="self")
    fg.icon("https://xkcd.com/s/919f27.ico")
    fg.language("zh-CN")
    fg.updated(datetime.now(dateutil.tz.tzutc()))

    for comic in saved_comics_info:
        fe = fg.add_entry()
        fe.id(comic["id"])
        fe.title(comic["title"]["chinese"])
        fe.link(href=comic["id"], rel="alternate")
        fe.summary(comic["description"]["chinese"])
        fe.content(generate_content_html(comic), type="html")
        fe.published(comic["published"])
        fe.updated(datetime.now(dateutil.tz.tzutc()))

    fg.atom_file(output_file, pretty=True)


def update_comic(comics):
    """更新漫画信息"""
    system_prompt = load_prompts()

    for comic in comics:
        response_msg = explain_comic(
            system_prompt=system_prompt,
            comic_title=comic["title"],
            comic_description=comic["description"],
            img_url=comic["img_url"],
            model_name="google/gemini-2.0-flash-001",
        )
        response_json_str = re.search(
            r"^```json\n(.*?)\n```$", response_msg, re.DOTALL
        ).group(1)
        response_json = json.loads(response_json_str)

        response_json["id"] = comic["id"]
        response_json["published"] = comic["published"]
        response_json["image_url"] = comic["img_url"]

        save_comic_info(response_json)
        save_processed(comic["id"])

    generate_atom_feed()


@app.route("/")
def index():
    return "Welcome to the XKCD Comic Explanation Service!"


@app.route("/atom")
def send_atom_feed():
    return send_file(OUTPUT_FEED_FILE, mimetype="application/atom+xml")


@app.route("/update")
def update_route():
    """更新漫画信息的路由"""
    comics = parse_xkcd_feed()
    if not comics:
        return "没有新的漫画需要更新。", 200
    try:
        update_comic(comics)
        return "更新成功！", 200
    except Exception as e:
        return f"更新失败: {e}", 500


@app.route("/comics")
def get_comics():
    """获取已保存的漫画信息"""
    try:
        comics_info = load_comic_info()
        return (
            json.dumps(comics_info, ensure_ascii=False),
            200,
            {"Content-Type": "application/json"},
        )
    except Exception as e:
        return f"加载漫画信息失败: {e}", 500


if __name__ == "__main__":
    app.run(debug=True, host=XKCD_SERVICE_HOST, port=XKCD_SERVICE_PORT)
