# xkcd-translater

一个从 xkcd 官方 Atom 源获取漫画、解析并翻译的 Python 项目，使用 OpenRouter 的 google/gemini-2.0-flash-001 模型生成翻译，并通过 Flask 提供 Web 服务生成新的 Atom 源。

## 功能

- 使用 [feedparser](https://github.com/kurtmckee/feedparser) 解析 xkcd 官方 Atom 源。
- 缓存已处理漫画 ID 和数据到两个 JSON 文件。
- 使用 OpenAI SDK 调用 OpenRouter 的 google/gemini-2.0-flash-001 模型生成翻译，输出 JSON 格式字符串。
- 使用 [feedgen](https://github.com/lkiesow/python-feedgen) 生成新的 Atom 源。
- 通过 Flask 提供 Web 服务：
  - `/atom`: 获取翻译后的 Atom 源。
  - `/update`: 触发更新操作。
- 支持通过 crontab 定期调用 `/update` 实现自动更新。

## 安装

### 1. 安装 uv

uv 是用 Rust 写的 Python 包和项目管理器。

参考 [uv 官方文档](https://docs.astral.sh/uv/getting-started/installation/) 安装 uv。

### 2. 克隆项目并安装依赖

```bash
git clone https://github.com/KrDw9ec4/xkcd-translater.git
cd xkcd-translater
uv sync
```

它会自动安装相应版本的 Python 和所需包。

### 3. 运行项目

```bash
cp .env.example .env
vim .env
```

- OPENAI_API_URL: API 地址
- OPENAI_API_KEY: API 密钥
- OPENAI_MODEL_NAME: 要使用的模型名称
- XKCD_SERVICE_HOST: 服务监听地址
- XKCD_SERVICE_PORT: 服务监听端口
- XKCD_SERVICE_URL: 服务访问地址，如 `http://127.0.0.1:5000`

```bash
uv run main.py
```

### 4. 配置系统服务（Linux 可选）

1. 编辑 `assets/xkcd-translater.service`，修改工作目录、可执行文件路径和用户组名。
2. 部署服务：
```bash
sudo cp assets/xkcd-translater.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl start xkcd-translater
```
3. 设置开机启动：
```bash
sudo systemctl enable xkcd-translater
```

## 使用

访问 `http://127.0.0.1:5000`，会看到欢迎。访问 `http://127.0.0.1:5000/update` 进行首次数据获取，要加载一会。

然后访问 `http://127.0.0.1:5000/atom` 就能发现生成的 Atom 源。

- `/atom`: 获取翻译后的 Atom 源。
- `/update`: 触发漫画数据更新，如果有新漫画，则会调用 API 进行翻译和解释。
- `/comics`: 获取已保存的漫画信息，返回的是 assets/saved_comics_info.json 的内容。
- `/force_refresh_atom`: 强制刷新 Atom Feed，利用已有的 saved_comic_info.json 的数据，重新生成 Atom Feed 文件。

配置 crontab 定期调用 `/update` 实现自动更新，例如：

```bash
0 9 * * * curl http://127.0.0.1:5000/update
```