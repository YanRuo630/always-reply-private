from maibot_sdk import MaiBotPlugin, PluginConfigBase, Field, HookHandler
from maibot_sdk.types import HookMode, HookOrder, ErrorPolicy


class PluginSection(PluginConfigBase):
    """私聊必回复基础设置"""
    __ui_label__ = "基础设置"

    config_version: str = Field(default="1.5.0", description="配置版本号")
    enabled: bool = Field(default=True, description="是否启用此插件")
    whitelist_only: bool = Field(
        default=False,
        description="是否仅对白名单中的用户生效（关闭则对所有私聊生效）",
    )
    whitelist_users: str = Field(
        default="",
        description="白名单用户 QQ 号，多个用英文逗号分隔",
        json_schema_extra={"placeholder": "例如: 123456,789012"},
    )


class AlwaysReplyConfig(PluginConfigBase):
    """私聊必回复插件完整配置"""

    plugin: PluginSection = Field(default_factory=PluginSection)


class AlwaysReplyPrivatePlugin(MaiBotPlugin):
    config_model = AlwaysReplyConfig

    async def on_load(self) -> None:
        self.ctx.logger.info("私聊必回复插件已加载")

    async def on_unload(self) -> None:
        self.ctx.logger.info("私聊必回复插件已卸载")

    async def on_config_update(self, scope: str, config_data: dict, version: str) -> None:
        self.ctx.logger.info("私聊必回复插件配置已更新")

    def _extract_user_id(self, message: dict) -> str:
        """从消息结构中提取发送者用户 ID"""
        # 优先尝试顶层字段
        for key in ("user_id", "sender_id"):
            if key in message:
                return str(message[key])

        # 尝试 message_info.user_info
        msg_info = message.get("message_info") or {}
        user_info = msg_info.get("user_info") or {}
        if user_info:
            uid = user_info.get("user_id") or user_info.get("id")
            if uid:
                return str(uid)

        # 尝试 sender 对象
        sender = message.get("sender") or {}
        if sender:
            uid = sender.get("user_id") or sender.get("id")
            if uid:
                return str(uid)

        return ""

    def _is_private_chat(self, message: dict) -> bool:
        """判断消息是否为私聊"""
        # 顶层标记
        if message.get("is_private") is True:
            return True

        # chat_type / scene / detail_type
        chat_type = (
            message.get("chat_type")
            or message.get("scene")
            or message.get("detail_type")
            or ""
        )
        if chat_type in ("private", "direct"):
            return True

        # NapCat 适配器额外字段
        add_config = {}
        if "message_info" in message:
            add_config = message.get("message_info", {}).get("additional_config") or {}
        elif "additional_config" in message:
            add_config = message.get("additional_config") or {}

        napcat_type = (
            add_config.get("napcat_message_type")
            or add_config.get("napcat_notice_type")
            or ""
        )
        if napcat_type == "private":
            return True

        # 如果带有平台 target 用户 ID 且无 group 信息，往往也是私聊
        if add_config.get("platform_io_target_user_id") is not None:
            return True

        return False

    @HookHandler(
        "chat.receive.before_process",
        name="force_private_reply",
        description="私聊消息拦截，强制设置回复状态",
        mode=HookMode.BLOCKING,
        order=HookOrder.EARLY,
        error_policy=ErrorPolicy.SKIP,
    )
    async def handle_private_reply(self, **kwargs):
        if not self.config.plugin.enabled:
            return {"action": "continue", "modified_kwargs": kwargs}

        message = kwargs.get("message", {})
        if not message:
            return {"action": "continue", "modified_kwargs": kwargs}

        # 调试时打印完整消息结构（生产环境 debug 级别不会输出）
        self.ctx.logger.debug(f"收到消息: {message}")

        user_id = self._extract_user_id(message)
        is_private = self._is_private_chat(message)

        self.ctx.logger.debug(
            f"消息分析 | 文本: '{message.get('processed_plain_text')}' | "
            f"chat_type: '{message.get('chat_type')}' | user_id: '{user_id}' | "
            f"is_private: {is_private}"
        )

        if not is_private:
            return {"action": "continue", "modified_kwargs": kwargs}

        # 白名单检查
        if self.config.plugin.whitelist_only:
            whitelist_raw = self.config.plugin.whitelist_users
            whitelist = [uid.strip() for uid in whitelist_raw.split(",") if uid.strip()]
            if user_id not in whitelist:
                self.ctx.logger.debug(f"用户 {user_id} 不在白名单，跳过")
                return {"action": "continue", "modified_kwargs": kwargs}

        self.ctx.logger.info(f"私聊触发强制回复 | 用户: {user_id}")

        # 注入决策标记（使 MaiBot 绕过时机模型）
        message["force_continue"] = True
        message["force_reply"] = True
        message["_force_reply"] = True
        message["is_at"] = True
        message["is_mentioned"] = True
        message["at_me"] = True

        kwargs["message"] = message
        return {"action": "continue", "modified_kwargs": kwargs}

def create_plugin():
    return AlwaysReplyPrivatePlugin()
