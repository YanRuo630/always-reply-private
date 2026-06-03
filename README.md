# 🤫 私聊必回复插件 (always-reply-private)

一个专门用于提升 MaiBot 私聊体验的辅助插件。它能让你的 Bot 无论遇到多么简短、模糊的私聊输入，都 **100% 触发回复**，绝不漏回、绝不冷场，并且支持配置白名单用户。

---

## ✨ 核心特性

- 🚀 **跳过时机模型**：在私聊场景下，直接跳过时机模型（Timing Gate）判定，不再消耗 Token 去询问模型“我该不该回复”，缩短响应时间，实现秒回！
- 🎯 **多适配器支持**：深度适配 QQ (NapCat/GoCQ)、Telegram、Discord 等多适配器传递的异构消息格式，精准识别私聊事件。
- 🛡️ **用户白名单模式**：
  - 默认对**所有私聊用户**生效（私聊必回复）。
  - 可开启**仅白名单生效**，只有列表内的特定账号才会触发“私聊必回复”，普通私聊用户依然走原版的时机模型，兼顾群管和隐私。
- ⚙️ **完美支持 SDK 2.0 与 WebUI**：支持配置热更新（Hot Reload）以及 WebUI 的动态配置 Schema 管理。

---

## 🛠️ 实现原理

本插件基于 **MaiBot SDK 2.0** 架构开发，利用了全新设计的 **Hook 处理器**。

1. 订阅 `chat.receive.before_process` 并在 `HookOrder.EARLY` 极早阶段进行同步拦截。
2. 结合 `chat_type` 和适配器特有字段（例如 `napcat_message_type`）进行精准的私聊场景识别。
3. 判定通过后，在消息载荷中同步注入 `force_continue`、`force_reply` 以及 `is_at` 等决策覆盖标记。
4. 消息带上标记流入 Host 后，推理引擎检测到这些覆盖指令，自动绕过时机模型网关，强制转入决策和回复生成，实现 100% 回复。

---

## ⚙️ 配置文件说明 (`config.toml`)

本插件支持在 WebUI 面板中直接可视化修改配置。其生成的配置文件位于插件目录下的 `config.toml`，内容格式如下：

```toml
[plugin]
config_version = "1.0.0"
enabled = true              # 是否启用该插件
whitelist_only = false      # 是否仅对白名单中的用户生效
whitelist_users = []        # 白名单用户账号/ID 列表（例: ["1234567"]）
