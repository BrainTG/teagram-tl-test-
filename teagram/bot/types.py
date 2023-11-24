import logging
import inspect

from types import FunctionType
from typing import Union

from aiogram import types as aiotypes
from aiogram.types import CallbackQuery, InlineQuery, Message, InlineKeyboardMarkup
from telethon import TelegramClient

from .. import database, types
from .utils import Utils

logger = logging.getLogger()

class Item(Utils):
    """
    Base class for items.
    This class provides functionality for checking filters applied to event handlers.
    """

    def __init__(self) -> None:
        """
        Initialize the class.
        """
        self._manager: types.ModulesManager = None
        self._db: database.Database = None
        self._app: TelegramClient = None

    async def _check_filters(
        self,
        func: FunctionType,
        module: types.Module,
        update_type: Union[Message, InlineQuery, CallbackQuery],
    ) -> bool:
        """
        Check filters for an event handler.

        Args:
            func (FunctionType): The event handler function.
            module (types.Module): The module the function belongs to.
            update_type (Union[Message, InlineQuery, CallbackQuery]): The type of update.

        Returns:
            bool: True if the event should be processed, False otherwise.
        """
        if (custom_filters := getattr(func, "_filters", None)):
            coro = custom_filters(module, update_type)
            if inspect.iscoroutine(coro):
                coro = await coro

            if not coro:
                return False
        elif update_type.from_user.id != self._manager.me.id:
            if not getattr(func, 'inline_everyone', None):
                return False

        return True

class InlineCall(CallbackQuery):
    def __init__(
        self,
        call: CallbackQuery,
        manager: 'types.bot.BotManager'
    ):
        self.inline_message_id = None
        self.callback_query = call
        self._bot = manager.bot

        for orig in (
            'id',
            'from_user',
            'message',
            'inline_message_id',
            'chat_instance',
            'data'
        ):
            setattr(
                self,
                orig,
                getattr(call, orig, None)
            )

    async def edit(
        self,
        text: str = None,
        photo: str = None,
        gif: str = None,
        file = None,
        spoiler: bool = False,
        reply_markup: InlineKeyboardMarkup = None,
        inline_message_id: str = None
    ):
        if not text and not (
            photo or gif or file
        ):
            logger.warning("InlineCall needs text or media for edit")
            return
        
        from io import BytesIO
        media = None
        if isinstance(file, BytesIO):
            media = aiotypes.InputFile(file)

        try:
            if photo:
                media = aiotypes.InputMediaPhoto(photo, text, parse_mode="html")
            if gif:
                media = aiotypes.InputMediaAnimation(
                    photo, caption=text, parse_mode="html", has_spoiler=spoiler)
        except Exception as error:
            logger.exception("Can't delete inline call")
        
        if media:
            return await self._bot.edit_message_media(
                media, 
                inline_message_id=inline_message_id or self.inline_message_id,
                reply_markup=reply_markup
            )
        try:
            return await self._bot.edit_message_text(
                text,
                inline_message_id=inline_message_id or self.inline_message_id,
                reply_markup=reply_markup
            )
        except Exception:
            logger.exception("Can't edit inline call")

    async def delete(self):
        try:
            if self.message and self.message.chat:
                return await self._bot.delete_message(
                    chat_id=self.message.chat.id,
                    message_id=self.message.message_id
                )

            return False
        except Exception:
            logger.exception("Can't delete inline call")