"""
pyromod - A monkeypatcher add-on for Pyrogram
Copyright (C) 2020 Cezar H. <https://github.com/usernein>

This file is part of pyromod.

pyromod is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

pyromod is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with pyromod.  If not, see <https://www.gnu.org/licenses/>.
"""

import asyncio
import functools
from typing import Optional
import logging
import pyrogram
from enum import Enum
from ..utils import patch, patchable

loop = asyncio.get_event_loop()

logger = logging.getLogger(__package__)
    
class UpdateType(Enum):
    MESSAGE = 1
    CALLBACK = 2
    INLINE = 3
    CHOSEN_INLINE = 4
    USER_STATUS = 5
    RAW = 6

class ListenerCanceled(Exception):
    pass
pyrogram.errors.ListenerCanceled = ListenerCanceled

@patch(pyrogram.client.Client)
class Client():
    @patchable
    def __init__(self, *args, **kwargs):
        self.listening = {}
        self.using_mod = True
        
        self.old__init__(*args, **kwargs)
    
    @patchable
    async def listen(self, chat_id: int, filters: pyrogram.filters =None, update_type: UpdateType = UpdateType.MESSAGE, timeout: int = None):
        _update_type, update_type = update_type, update_type.name
        if type(chat_id) != int:
            chat = await self.get_chat(chat_id)
            chat_id = chat.id
        if not self.listening.get(chat_id):
            self.listening[chat_id] = {}
        if not self.listening[chat_id].get(update_type):
            self.listening[chat_id][update_type] = {}
        future = loop.create_future()
        future.add_done_callback(
            functools.partial(self.clear_listener, chat_id, _update_type)
        )
        self.listening[chat_id][update_type].update({
            "future": future, "filters": filters, "type": update_type}
        )
        return await asyncio.wait_for(future, timeout)
   
    @patchable
    def clear_listener(self, chat_id: int, update_type: UpdateType, future: asyncio.Future):
        update_type = update_type.name
        if  self.listening[chat_id][update_type] and future == self.listening[chat_id][update_type]["future"]:
            self.listening[chat_id].pop(update_type, None)
     
    @patchable
    def cancel_listener(self, chat_id, update_type):
        update_type = update_type.name
        listener = self.listening.get(chat_id)
        if not listener:
            logger.debug("No listener found for user [cancel_listener] {}".format(chat_id))
            return
        if not listener.get(update_type) and listener[update_type]['future'].done():
            logger.debug("No listener found for user [cancel_listener] {} with {}".format(chat_id, update_type))
            return
        
        listener[update_type]['future'].set_exception(ListenerCanceled())
        self.clear_listener(chat_id, update_type, listener['future'])
        
@patch(pyrogram.handlers.message_handler.MessageHandler)
class MessageHandler():
    @patchable
    def __init__(self, callback: callable, filters=None):
        self.user_callback = callback
        self.old__init__(self.resolve_listener, filters)
        self.__update_type = UpdateType.MESSAGE.name
    
    @patchable
    async def resolve_listener(self, client, update, *args):
        listener = client.listening.get(update.from_user.id)
        if not listener:
            logger.debug("No listener found for user [resolve] {}".format(update.from_user.id))
        else:
            if not listener.get(self.__update_type):
                logger.debug("No listener found for user [resolve] {} with {}".format(update.from_user.id, self.__update_type))
                return
            listener = listener.get(self.__update_type)
            if listener and not listener['future'].done():
                listener['future'].set_result(update)
            else:
                if listener and listener['future'].done():
                    client.clear_listener(update.from_user.id, self.__update_type, listener['future'])
        await self.user_callback(client, update, *args)
    
    @patchable
    async def check(self, client, update):
        listener = client.listening.get(update.from_user.id)
        if not listener:
            logger.debug("No listener found for user [check] {}".format(update.from_user.id))
            pass
        else:
            if not listener.get(self.__update_type):
                logger.debug("No listener found for user [check] {} with {}".format(update.from_user.id, self.__update_type))
                return
            listener = listener.get(self.__update_type)
            if listener and not listener['future'].done():
                response = await listener['filters'](client, update) if callable(listener['filters']) else True
                return response
            
        response = (
            await self.filters(client, update)
            if callable(self.filters)
            else True
        )
        return response

@patch(pyrogram.handlers.callback_query_handler.CallbackQueryHandler)
class CallbackQueryHandler():
    @patchable
    def __init__(self, callback: callable, filters=None):
        self.user_callback = callback
        self.old__init__(self.resolve_listener, filters)
        self.__update_type = UpdateType.CALLBACK.name
    
    @patchable
    async def resolve_listener(self, client, update, *args):
        listener = client.listening.get(update.from_user.id)
        if not listener:
            logger.debug("No listener found for user [resolve] {}".format(update.from_user.id))
        else:
            if not listener.get(self.__update_type):
                logger.debug("No listener found for user [resolve] {} with {}".format(update.from_user.id, self.__update_type))
                return
            listener = listener.get(self.__update_type)
            if listener and not listener['future'].done():
                listener['future'].set_result(update)
            else:
                if listener and listener['future'].done():
                    client.clear_listener(update.from_user.id, self.__update_type, listener['future'])
        await self.user_callback(client, update, *args)
    
    @patchable
    async def check(self, client, update):
        listener = client.listening.get(update.from_user.id)
        if not listener:
            logger.debug("No listener found for user [check] {}".format(update.from_user.id))
            pass
        else:
            if not listener.get(self.__update_type):
                logger.debug("No listener found for user [check] {} with {}".format(update.from_user.id, self.__update_type))
                return
            listener = listener.get(self.__update_type)
            if listener and not listener['future'].done():
                response = await listener['filters'](client, update) if callable(listener['filters']) else True
                return response
            
        response = (
            await self.filters(client, update)
            if callable(self.filters)
            else True
        )
        return response

@patch(pyrogram.handlers.inline_query_handler.InlineQueryHandler)
class InlineQueryHandler():
    @patchable
    def __init__(self, callback: callable, filters=None):
        self.user_callback = callback
        self.old__init__(self.resolve_listener, filters)
        self.__update_type = UpdateType.INLINE.name
    
    @patchable
    async def resolve_listener(self, client, update, *args):
        listener = client.listening.get(update.from_user.id)
        if not listener:
            logger.debug("No listener found for user [resolve] {}".format(update.from_user.id))
        else:
            if not listener.get(self.__update_type):
                logger.debug("No listener found for user [resolve] {} with {}".format(update.from_user.id, self.__update_type))
                return
            listener = listener.get(self.__update_type)
            if listener and not listener['future'].done():
                listener['future'].set_result(update)
            else:
                if listener and listener['future'].done():
                    client.clear_listener(update.from_user.id, self.__update_type, listener['future'])
        await self.user_callback(client, update, *args)
    
    @patchable
    async def check(self, client, update):
        listener = client.listening.get(update.from_user.id)
        if not listener:
            logger.debug("No listener found for user [check] {}".format(update.from_user.id))
            pass
        else:
            if not listener.get(self.__update_type):
                logger.debug("No listener found for user [check] {} with {}".format(update.from_user.id, self.__update_type))
                return
            listener = listener.get(self.__update_type)
            if listener and not listener['future'].done():
                response = await listener['filters'](client, update) if callable(listener['filters']) else True
                return response
            
        response = (
            await self.filters(client, update)
            if callable(self.filters)
            else True
        )
        return response

@patch(pyrogram.handlers.chosen_inline_result_handler.ChosenInlineResultHandler)
class ChosenInlineResultHandler():
    @patchable
    def __init__(self, callback: callable, filters=None):
        self.user_callback = callback
        self.old__init__(self.resolve_listener, filters)
        self.__update_type = UpdateType.CHOSEN_INLINE.name
    
    @patchable
    async def resolve_listener(self, client, update, *args):
        listener = client.listening.get(update.from_user.id)
        if not listener:
            logger.debug("No listener found for user [resolve] {}".format(update.from_user.id))
        else:
            if not listener.get(self.__update_type):
                logger.debug("No listener found for user [resolve] {} with {}".format(update.from_user.id, self.__update_type))
                return
            listener = listener.get(self.__update_type)
            if listener and not listener['future'].done():
                listener['future'].set_result(update)
            else:
                if listener and listener['future'].done():
                    client.clear_listener(update.from_user.id, self.__update_type, listener['future'])
        await self.user_callback(client, update, *args)
    
    @patchable
    async def check(self, client, update):
        listener = client.listening.get(update.from_user.id)
        if not listener:
            logger.debug("No listener found for user [check] {}".format(update.from_user.id))
            pass
        else:
            if not listener.get(self.__update_type):
                logger.debug("No listener found for user [check] {} with {}".format(update.from_user.id, self.__update_type))
                return
            listener = listener.get(self.__update_type)
            if listener and not listener['future'].done():
                response = await listener['filters'](client, update) if callable(listener['filters']) else True
                return response
            
        response = (
            await self.filters(client, update)
            if callable(self.filters)
            else True
        )
        return response

@patch(pyrogram.handlers.raw_update_handler.RawUpdateHandler)
class RawUpdateHandler():
    @patchable
    def __init__(self, callback: callable, filters=None):
        self.user_callback = callback
        self.old__init__(self.resolve_listener, filters)
        self.__update_type = UpdateType.RAW.name
    
    @patchable
    async def resolve_listener(self, client, update, *args):
        listener = client.listening.get(update.from_user.id)
        if not listener:
            logger.debug("No listener found for user [resolve] {}".format(update.from_user.id))
        else:
            if not listener.get(self.__update_type):
                logger.debug("No listener found for user [resolve] {} with {}".format(update.from_user.id, self.__update_type))
                return
            listener = listener.get(self.__update_type)
            if listener and not listener['future'].done():
                listener['future'].set_result(update)
            else:
                if listener and listener['future'].done():
                    client.clear_listener(update.from_user.id, self.__update_type, listener['future'])
        await self.user_callback(client, update, *args)
    
    @patchable
    async def check(self, client, update):
        listener = client.listening.get(update.from_user.id)
        if not listener:
            logger.debug("No listener found for user [check] {}".format(update.from_user.id))
            pass
        else:
            if not listener.get(self.__update_type):
                logger.debug("No listener found for user [check] {} with {}".format(update.from_user.id, self.__update_type))
                return
            listener = listener.get(self.__update_type)
            if listener and not listener['future'].done():
                response = await listener['filters'](client, update) if callable(listener['filters']) else True
                return response
            
        response = (
            await self.filters(client, update)
            if callable(self.filters)
            else True
        )
        return response

@patch(pyrogram.types.user_and_chats.chat.Chat)
class Chat(pyrogram.types.Chat):
    @patchable
    def listen(self, *args, **kwargs):
        return self._client.listen(self.id, *args, **kwargs)
    @patchable
    def ask(self, *args, **kwargs):
        return self._client.ask(self.id, *args, **kwargs)
    @patchable
    def cancel_listener(self):
        return self._client.cancel_listener(self.id)

@patch(pyrogram.types.user_and_chats.user.User)
class User(pyrogram.types.User):
    @patchable
    def listen(self, *args, **kwargs):
        return self._client.listen(self.id, *args, **kwargs)
    @patchable
    def ask(self, *args, **kwargs):
        return self._client.ask(self.id, *args, **kwargs)
    @patchable
    def cancel_listener(self):
        return self._client.cancel_listener(self.id)
