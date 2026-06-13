from maibot_sdk import MaiBotPlugin, PluginConfigBase, Field, HookHandler
from maibot_sdk.types import HookMode, HookOrder, ErrorPolicy
from typing import List


class PluginSection(PluginConfigBase):
    """私聊必回复插件设置"""
    __ui_label__ = "基础设置"

    config_version: str = Field(
        default="2.0.0",
        description="配置文件版本号",
    )

    enabled: bool = Field(
        default=True,
        description="是否启用私聊必回复功能",
    )

    whitelist_users: str = Field(
        default="",
        description="白名单用户 ID：只有这些用户在私聊时才能直接跳过时机模型，多个 ID 用英文逗号分隔，留空表示对所有私聊用户生效",
        json_schema_extra={"placeholder": "例如: 123456,789012"},
    )


class AlwaysReplyPrivateConfig(PluginConfigBase):
    """私聊必回复插件完整配置"""

    plugin: PluginSection = Field(default_factory=PluginSection)


class AlwaysReplyPrivatePlugin(MaiBotPlugin):
    config_model = AlwaysReplyPrivateConfig

    async def on_load(self) -> None:
        self.ctx.logger.info("私聊必回复插件已加载")

    async def on_unload(self) -> None:
        self.ctx.logger.info("私聊必回复插件已卸载")

    async def on_config_update(self, scope: str, config_data: dict, version: str) -> None:
        self.ctx.logger.info("私聊必回复插件配置已更新")

    def _is_private_chat(self, message: dict) -> bool:
        """判断消息是否为私聊"""
        if message.get("is_private") is True:
            return True

        chat_type = (
            message.get("chat_type")
            or message.get("scene")
            or message.get("detail_type")
            or ""
        )
        if chat_type in ("private", "direct"):
            return True

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

        if add_config.get("platform_io_target_user_id") is not None and not message.get("group_id"):
            return True

        return False

    def _extract_user_id(self, message: dict) -> str:
        """从消息中提取用户 ID"""
        user_id = message.get("user_id") or ""
        if user_id:
            return str(user_id)

        msg_info = message.get("message_info") or {}
        user_info = msg_info.get("user_info") or {}
        if user_info:
            uid = user_info.get("user_id") or user_info.get("id")
            if uid:
                return str(uid)

        return ""

    def _parse_id_list(self, raw_str: str) -> List[str]:
        """解析逗号分隔的 ID 列表"""
        if not raw_str:
            return []
        return [item.strip() for item in raw_str.split(",") if item.strip()]

    def _should_force_timing_continue(self, message: dict) -> bool:
        """判断是否应该强制跳过时机模型"""
        # 检查是否启用
        if not self.config.plugin.enabled:
            return False

        # 检查是否为私聊
        if not self._is_private_chat(message):
            self.ctx.logger.debug("非私聊消息，不强制跳过时机模型")
            return False

        # 检查白名单
        whitelist = self._parse_id_list(self.config.plugin.whitelist_users)
        if whitelist:
            user_id = self._extract_user_id(message)
            if not user_id:
                self.ctx.logger.debug("无法提取用户 ID，不强制跳过时机模型")
                return False

            if user_id not in whitelist:
                self.ctx.logger.debug(f"用户 {user_id} 不在白名单中，不强制跳过时机模型")
                return False

            self.ctx.logger.info(f"用户 {user_id} 在白名单中，将强制跳过时机模型")
        else:
            self.ctx.logger.info("白名单为空，所有私聊用户将强制跳过时机模型")

        return True

    @HookHandler(
        "chat.receive.after_process",
        name="force_timing_continue_in_private",
        description="私聊环境下强制跳过时机模型，直接进入 Planner",
        mode=HookMode.BLOCKING,
        order=HookOrder.LATE,
        error_policy=ErrorPolicy.SKIP,
    )
    async def force_timing_continue_in_private(self, **kwargs):
        """在私聊环境下通过设置 is_mentioned 标志来强制跳过时机模型"""
        message = kwargs.get("message", {})
        if not message:
            return {"action": "continue", "modified_kwargs": kwargs}

        # 跳过通知消息
        if message.get("is_notify", False):
            return {"action": "continue", "modified_kwargs": kwargs}

        # 如果已经设置了 is_mentioned 或 is_at，不需要重复设置
        if message.get("is_mentioned", False) or message.get("is_at", False):
            return {"action": "continue", "modified_kwargs": kwargs}

        if not self._should_force_timing_continue(message):
            return {"action": "continue", "modified_kwargs": kwargs}

        # 设置 is_mentioned 标志，让 runtime 的 _update_message_trigger_state 自动设置强制跳过
        # 这样就不需要直接操作 runtime 实例了
        message["is_mentioned"] = True
        kwargs["message"] = message

        user_id = self._extract_user_id(message)
        self.ctx.logger.info(
            f"✓ 私聊消息设置 is_mentioned 标志: user_id={user_id}, "
            f"message_id={message.get('message_id', 'unknown')}"
        )

        return {"action": "continue", "modified_kwargs": kwargs}


def create_plugin():
    return AlwaysReplyPrivatePlugin()
