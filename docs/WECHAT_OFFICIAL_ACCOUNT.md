# 微信公众号发布接入

MarketCraft AI 0.11.0 支持下面这条安全发布链路：

1. 上传公众号封面素材；
2. 创建公众号草稿；
3. 由不同账号完成人工审核；
4. 提交公众号发布；
5. 查询发布状态。

默认 `WECHAT_MODE=mock`，可以完整演示，但不会访问微信服务器或发布真实内容。

## 公众号侧准备

在微信公众平台后台准备：

- 公众号 `AppID`；
- 公众号 `AppSecret`；
- 将部署服务器公网 IP 加入接口 IP 白名单；
- 在“接口权限”中确认账号具备素材、草稿和发布相关权限。

不同公众号类型、认证状态和接口权限可能不同；以公众号后台实际显示的权限为准。

不要把 `AppSecret` 写进代码、截图、聊天或 GitHub。

## 腾讯云服务器配置

进入项目目录：

```bash
cd /opt/marketcraft-ai
sudo git pull --ff-only origin main
```

在现有 `.env` 中加入：

```dotenv
WECHAT_MODE=live
WECHAT_APP_ID=你的公众号AppID
WECHAT_APP_SECRET=你的公众号AppSecret
WECHAT_API_BASE=https://api.weixin.qq.com
WECHAT_TIMEOUT_SECONDS=20
```

保护密钥文件：

```bash
sudo chmod 600 .env
```

如果仅启用公众号真实接口：

```bash
sudo docker compose \
  -f docker-compose.demo.yml \
  -f docker-compose.wechat.yml \
  up -d --build --force-recreate
```

如果同时启用 OpenAI 与公众号：

```bash
sudo docker compose \
  -f docker-compose.demo.yml \
  -f docker-compose.openai.yml \
  -f docker-compose.wechat.yml \
  up -d --build --force-recreate
```

检查配置是否加载（不会打印密钥）：

```bash
curl http://127.0.0.1/api/v1/wechat/configuration
```

查看容器与日志：

```bash
sudo docker compose \
  -f docker-compose.demo.yml \
  -f docker-compose.wechat.yml \
  ps

sudo docker compose \
  -f docker-compose.demo.yml \
  -f docker-compose.wechat.yml \
  logs -f --tail=100 api
```

手机访问：

```text
http://SERVER_IP/app#wechat
```

## 真实接口

适配器使用微信公众号官方接口：

- `GET /cgi-bin/token`：获取并缓存 `access_token`；
- `POST /cgi-bin/material/add_material`：上传永久封面素材；
- `POST /cgi-bin/draft/add`：创建草稿；
- `POST /cgi-bin/freepublish/submit`：提交发布；
- `POST /cgi-bin/freepublish/get`：查询发布状态。

所有真实发布操作必须先通过 MarketCraft 的四眼审核；创建人与审核人不能相同。
