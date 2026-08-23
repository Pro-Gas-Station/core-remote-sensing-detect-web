# 本地配置

将 `*.example.json` 复制为去掉 `.example` 的同名文件后填写。

| 文件 | 必填 | 说明 |
|------|------|------|
| `email_config.json` | 否 | SMTP，用于邮箱验证码 |
| `sms_config.json` | 否 | 短信验证码；未配置时开发模式打印至控制台 |
| `llm_config.json` | 否 | 检测页大语言模型 |
| `member_llm_config.json` | 否 | 会员账号专用模型 Key |
| `app.db` | — | SQLite，首次启动自动创建 |

含密码、AccessKey、API Key 的文件不得纳入版本库。
