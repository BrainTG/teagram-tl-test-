import asyncio
import functools
import random
import string
import yaml
import os
import contextlib
import aiohttp
from types import FunctionType
from typing import Any, List, Literal, Tuple, Union

from telethon.tl.functions.channels import CreateChannelRequest
from telethon import TelegramClient, types
from telethon.tl import custom

from . import database

Message = Union[custom.Message, types.Message]

def get_full_command(message: Message) -> Union[
    Tuple[Literal[""], Literal[""], Literal[""]], Tuple[str, str, str]
]:
    """
    Extract a tuple of prefix, command, and arguments from the message.

    Parameters:
        message (Message): The message.

    Returns:
        Union[
            Tuple[Literal[""], Literal[""], Literal[""]],
            Tuple[str, str, str]
        ]: A tuple containing the prefix, command, and arguments.

    Example:
        message_text = "/command arg1 arg2"
        message = Message(text=message_text)
        result = get_full_command(message)
        #  result also can be if you didn't set prefix: ("", "command", "arg1 arg2")
        # For the example message_text, result will be: ("/", "command", "arg1 arg2")
    """

    message.text = str(message.text)
    prefixes = database.db.get("teagram.loader", "prefixes", ["."])

    for prefix in prefixes:
        if (
            message.text
            and len(message.text) > len(prefix)
            and message.text.startswith(prefix)
        ):
            command, *args = message.text[len(prefix):].split(maxsplit=1)
            break
    else:
        return "", "", ""

    return prefixes[0], command.lower(), args[-1] if args else ""

def get_chat(message: Message):
    return (message.chat.id if message.chat else None or message._chat_peer)

async def create_group(
    app: TelegramClient,
    title: str,
    description: str,
    megagroup: bool = False,
    broadcast: bool = False
):
    return await app(CreateChannelRequest(title, description, megagroup=megagroup, broadcast=broadcast))

async def answer(
    message: Union[Message, List[Message]],
    response: Union[str, Any],
    photo: bool = False,
    document: bool = False,
    caption: str = '',
    parse_mode: str = 'html',
    **kwargs
) -> List[Message]:
    """
    Send a response to a message, with optional photo or document attachment.

    Parameters:
        message (Union[Message, List[Message]]): The original message or a list of messages to reply to.
        response (Union[str, Any]): The response to send. It can be a text message, a path to a photo/document, or a file-like object.
        photo (bool, optional): If True, a photo will be sent along with the response. Default is False.
        document (bool, optional): If True, a document will be sent along with the response. Default is False.
        caption (str, optional): Caption for the sent photo or document, if applicable.
        parse_mode (str, optional): Parse mode for formatting text. Default is 'html'.
        **kwargs: Additional keyword arguments for sending messages or files.

    Returns:
        List[Message]: A list of sent messages.

    Example:
        response_text = "Thank you for your message!"
        await utils.answer(message, response_text)
        
        response_image_path = "image.jpg"
        await utils.answer(message, response_image_path, photo=True, caption="Here's an image for you.")
    """
    messages: List[Message] = []
    client: TelegramClient = message._client  # type: ignore
    chat = get_chat(message)

    if isinstance(message, list):
        message: Message = message[0]

    if isinstance(response, str) and not (photo or document):
        try:
            msg = await client.edit_message(
                chat,
                message.id,
                response,
                parse_mode=parse_mode,
                **kwargs
            )
        except:
            msg = await message.reply(response, parse_mode=parse_mode, **kwargs)

        messages.append(msg)

    if photo or document:       
        messages.append(
            await client.send_file(
                chat, 
                response,
                caption=caption,
                parse_mode=parse_mode,
                reply_to=message.id,
                **kwargs
            ) # type: ignore
        ) # type: ignore

        await client.delete_messages(chat, message.id)

    return messages

async def invoke_inline(
    message: Message,
    bot_username: str,
    inline_id: str
):
    """
    Invoke an inline query to a bot.

    Args:
        message (Union[Message, List[Message]]): The original message or a list of messages to refer to.
        bot_username (str): The username of the bot to invoke the inline query.
        inline_id (str): The unique identifier of the inline query.

    Returns:
        Awaitable: The result of the invoked inline query.
    """
    client: TelegramClient = message._client # type: ignore
    query: custom.InlineResults = await client.inline_query(bot_username, inline_id)

    return await query[0].click(
        get_chat(message),
        reply_to=message.reply_to_msg_id or None
    )


def run_sync(func: FunctionType, *args, **kwargs) -> asyncio.Future:
    """
    Run a non-async function asynchronously.

    Parameters:
        func (FunctionType): The function to run.
        args (list): Arguments for the function.
        kwargs (dict): Keyword arguments for the function.

    Returns:
        asyncio.Future: A Future object representing the result of the function.

    Example:
        def sync_function(x):
            return x * 2

        async def main():
            result = await run_sync(sync_function, 5)
            print(result)  # Output: 10
    """

    return asyncio.get_event_loop().run_in_executor(
        None, functools.partial(
            func, *args, **kwargs)
    )

def get_ram() -> float:
    """
    Get memory usage in megabytes.

    Returns:
        float: Memory usage in megabytes.
    """
    
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem = process.memory_info()[0] / 2.0**20
        for child in process.children(recursive=True):
            mem += child.memory_info()[0] / 2.0**20
        return round(mem, 1)
    except:
        return 0

def get_cpu() -> float:
    """
    Get CPU usage as a percentage.

    Returns:
        float: CPU usage as a percentage.
    """

    try:
        import psutil

        process = psutil.Process(os.getpid())
        cpu = process.cpu_percent()

        for child in process.children(recursive=True):
            cpu += child.cpu_percent()

        return cpu
    except:
        return 0
    
def get_display_name(entity: Union[types.User, types.Chat]) -> str:
    """
    Get display name of user or chat.

    Returns:
        entity: Union[types.User, types.Chat].
    """
    return getattr(entity, "title", None) or (
        entity.first_name or "" + (
            " " + entity.last_name
            if entity.last_name else ""
        )
    )

def get_platform() -> str:
    """
    Get the platform information.

    Returns:
        str: Platform information.
    """

    IS_TERMUX = "com.termux" in os.environ.get("PREFIX", "")
    IS_CODESPACES = "CODESPACES" in os.environ
    IS_DOCKER = "DOCKER" in os.environ
    IS_GOORM = "GOORM" in os.environ
    IS_WIN = "WINDIR" in os.environ
    IS_TRIGGER = 'TRIGGEREARTH' in os.environ
    IS_WSL = False
    
    with contextlib.suppress(Exception):
        from platform import uname
        if "microsoft-standard" in uname().release:
            IS_WSL = True

    if IS_TERMUX:
        platform = "<emoji id=5407025283456835913>📱</emoji> Termux"
    elif IS_DOCKER:
        platform = "<emoji id=5431815452437257407>🐳</emoji> Docker"
    elif IS_GOORM:
        platform = "<emoji id=5215584860063669771>💚</emoji> Goorm"
    elif IS_WSL:
        platform = "<emoji id=6327609909416298142>🧱</emoji> WSL"
    elif IS_WIN:
        platform = "<emoji id=5309880373126113150>💻</emoji> Windows"
    elif IS_CODESPACES:
        platform = "<emoji id=5467643451145199431>👨‍💻</emoji> Github Codespaces"
    elif IS_TRIGGER:
        platform = "🌍 TriggerEarth"
    else:
        platform = "🖥️ VDS"
    
    return platform

def random_id(length: int = 10) -> str:
    """
    Generate a random ID.

    Parameters:
        length (int): Length of the random ID. Default is 10.

    Returns:
        str: Random ID.
    """

    return "".join(
        random.choice(string.ascii_letters + string.digits)
        for _ in range(length)
    )


def get_langpack() -> Union[Any, List]:
    """
    Get the language pack.

    Returns:
        Union[Any, List]: The language pack.
    """

    if not (lang := database.db.get('teagram.loader', 'lang')):
        database.db.set('teagram.loader', 'lang', 'en')

        get_langpack()
    else:
        with open(f'teagram/langpacks/{lang}.yml') as file:
            pack = yaml.safe_load(file)

        return pack

async def paste_neko(code: str):
    """
    Paste code on nekobin.com and get the URL.

    Parameters:
        code (str): The code to be pasted.

    Returns:
        str: The URL of the pasted code.
    """

    try:
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            async with session.post(
                "https://nekobin.com/api/documents",
                json={"content": code},
            ) as paste:
                paste.raise_for_status()
                result = await paste.json()
    except Exception:
        return "Pasting failed"
    else:
        return f"nekobin.com/{result['result']['key']}.py"
