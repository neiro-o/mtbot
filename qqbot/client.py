import botpy
from botpy import logging
from botpy.message import C2CMessage, GroupMessage

from qqbot.handlers import MessageContext, handle_text_message, truncate_reply
from qqbot.images import (
    extract_image_attachments,
    log_image_attachments,
    search_answer_from_image,
)


_log = logging.get_logger()


class QQBotClient(botpy.Client):
    async def on_ready(self):
        _log.info(f"robot {self.robot.name} on_ready!")

    async def on_group_at_message_create(self, message: GroupMessage):
        content = (message.content or "").strip()
        context = MessageContext(
            source="group",
            message_id=message.id,
            sender_id=message.group_openid,
        )
        images = extract_image_attachments(message)

        try:
            if images:
                log_image_attachments(context.source, context.message_id, context.sender_id, images)

            image_search_reply = search_answer_from_image(images[0]) if images else None
            if image_search_reply:
                reply = truncate_reply(image_search_reply)
            elif content:
                reply = truncate_reply(handle_text_message(content, context))
            elif images:
                _log.info("ignore image message without search reply: %s", message.id)
                return
            else:
                _log.info("ignore empty group message: %s", message.id)
                return

            if not reply:
                _log.info("ignore message with empty reply: %s", message.id)
                return

            await message._api.post_group_message(
                group_openid=message.group_openid,
                msg_type=0,
                msg_id=message.id,
                content=reply,
            )
        except Exception:
            _log.exception("failed to handle group message: %s", message.id)

    async def on_c2c_message_create(self, message: C2CMessage):
        content = (message.content or "").strip()
        context = MessageContext(
            source="c2c",
            message_id=message.id,
            sender_id=message.author.user_openid,
        )
        images = extract_image_attachments(message)

        try:
            if images:
                log_image_attachments(context.source, context.message_id, context.sender_id, images)

            image_search_reply = search_answer_from_image(images[0]) if images else None
            if image_search_reply:
                reply = truncate_reply(image_search_reply)
            elif content:
                reply = truncate_reply(handle_text_message(content, context))
            elif images:
                _log.info("ignore image message without search reply: %s", message.id)
                return
            else:
                _log.info("ignore empty c2c message: %s", message.id)
                return

            if not reply:
                _log.info("ignore message with empty reply: %s", message.id)
                return

            await message._api.post_c2c_message(
                openid=message.author.user_openid,
                msg_type=0,
                msg_id=message.id,
                content=reply,
            )
        except Exception:
            _log.exception("failed to handle c2c message: %s", message.id)
