from maibot_sdk import MaiBotPlugin, PluginConfigBase, Field, HookHandler
from maibot_sdk.types import HookMode, HookOrder, ErrorPolicy

class PluginSection(PluginConfigBase):
    """私聊必回复基础设置"""
    __ui_label__ = "基础设置"

    config_version: str = Field(
        default="1.0.0",
        description="配置版本号"
    )
    enabled: bool = Field(
        default=True,
        description="是否启用此插件"
    )
    whitelist_only: bool = Field(
        default=False,
        description="是否仅对白名单中的用户生效（若关闭，则私聊所有用户均必回复）"
    )
    whitelist_users: list = Field(
        default_factory=list,
        description="白名单用户账号/ID 列表",
        json_schema_extra={"placeholder": "例如: ['123456', '789012']"}
    )

class AlwaysReplyConfig(PluginConfigBase):
    """私聊必回复插件完整配置"""
    plugin: PluginSection = Field(default_factory=PluginSection)

class AlwaysReplyPrivatePlugin(MaiBotPlugin):
    config_model = AlwaysReplyConfig

    async def on_load(self) -> None:
        self.ctx.logger.info("私聊必回复 (always-reply-private) 插件已成功加载！")

    async def on_unload(self) -> None:
        self.ctx.logger.info("私聊必回复 (always-reply-private) 插件已成功卸载！")

    async def on_config_update(self, scope: str, config_data: dict, version: str) -> None:
        self.ctx.logger.info("私聊必回复插件配置已更新！")

    @HookHandler(
        "chat.receive.before_process",
        name="force_private_reply",
        description="私聊消息拦截，判断并强制设置回复状态",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
        error_policy=ErrorPolicy.SKIP
    )
    async def handle_private_reply(self, **kwargs):
        # 访问嵌套配置
        if not self.config.plugin.enabled:
            return {"action": "continue", "modified_kwargs": kwargs}

        message = kwargs.get("message", {})
        if not message:
            return {"action": "continue", "modified_kwargs": kwargs}

        # 详细记录接收到的 message 载荷，便于在后台调试中观察
        self.ctx.logger.debug(f"私聊必回复插件 - 收到完整 message: {message}")

        # ==== 获取发送者用户 ID ====
        user_id = ""
        if "user_id" in message:
            user_id = str(message["user_id"])
        elif "sender_id" in message:
            user_id = str(message["sender_id"])

        if not user_id and "message_info" in message:
            msg_info = message["message_info"] or {}
            user_info = msg_info.get("user_info") or {}
            user_id = str(user_info.get("user_id") or user_info.get("id") or "")

        if not user_id and "sender" in message:
            sender = message["sender"] or {}
            user_id = str(sender.get("user_id") or sender.get("id") or "")

        # ==== 核心：深入分析私聊场景判断 ====
        # 从您贴出的真实日志可以看出，NapCat 发送来的私聊事件中：
        # message_info.additional_config 包含了: 'napcat_message_type': 'private'
        # 这就是最铁证的私聊判定标尺！
        chat_type = message.get("chat_type") or message.get("scene") or message.get("detail_type") or ""

        # 尝试从 additional_config 取
        add_config = message.get("message_info", {}).get("additional_config", {}) if "message_info" in message else {}
        if not add_config and "additional_config" in message:
            add_config = message["additional_config"] or {}

        napcat_msg_type = add_config.get("napcat_message_type") or add_config.get("napcat_notice_type") or ""

        # 是否为私聊消息判定：
        is_private = (
            chat_type == "private"
            or chat_type == "direct"
            or message.get("is_private") is True
            or napcat_msg_type == "private"
            or add_config.get("platform_io_target_user_id") is not None  # 如果带有平台 target 用户 ID 且无 group 信息，往往也是私聊
        )

        self.ctx.logger.info(f"私聊必回复插件分析结果 - 消息文本: '{message.get('processed_plain_text')}' | chat_type: '{chat_type}' | user_id: '{user_id}' | is_private: {is_private}")

        if is_private:
            should_force = True

            # 判断白名单
            if self.config.plugin.whitelist_only:
                whitelist = [str(uid).strip() for uid in self.config.plugin.whitelist_users]
                if user_id not in whitelist:
                    should_force = False
                    self.ctx.logger.info(f"用户 {user_id} 不在白名单中 {whitelist}，跳过强制回复")

            if should_force:
                self.ctx.logger.info(f"私聊必回复插件触发成功 - 强制绕过时机模型！用户: {user_id}")

                # 注入所有能改变决策流、时机门的标记
                message["force_continue"] = True
                message["force_reply"] = True
                message["_force_reply"] = True
                message["is_at"] = True
                message["is_mentioned"] = True
                message["at_me"] = True

                # 回写到参数字典
                kwargs["message"] = message

        return {"action": "continue", "modified_kwargs": kwargs}

def create_plugin():
    return AlwaysReplyPrivatePlugin()
