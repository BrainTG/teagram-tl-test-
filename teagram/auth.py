import configparser
import logging
import sys

from getpass import getpass
from typing import NoReturn, Tuple, Union

from telethon.password import compute_check
from telethon import TelegramClient, errors, types
from telethon.tl.functions.account import GetPasswordRequest
from telethon.tl.functions.auth import CheckPasswordRequest
from telethon.tl import types as tltypes

from qrcode.main import QRCode

from . import __version__, database
from .utils import rnd_device

db = database.db


class Auth:
    def __init__(
        self,
        session_name: str = "./teagram",
        random_device: bool = False,
        manual: bool = True,
    ) -> None:
        if manual:
            config = configparser.ConfigParser()
            if not config.read("./config.ini"):
                config["telethon"] = {
                    "api_id": input("Enter API id: "),
                    "api_hash": input("Enter API hash: "),
                }

                with open("./config.ini", "w") as file:
                    config.write(file)

        if db.get("teagram.loader", "web_success", ""):
            db.pop("teagram.loader", "web_success")

        config = configparser.ConfigParser()
        config.read("./config.ini")

        try:
            _id = config.get("telethon", "api_id")
            _hash = config.get("telethon", "api_hash")
        except Exception:
            _id = 123
            _hash = "_"

        device_model = "Teagram Userbot" if not random_device else rnd_device()
        self.app = TelegramClient(
            api_id=_id,
            api_hash=_hash,
            session=session_name,
            device_model=device_model,
            app_version=f"v{__version__}",
        )
        self.app.session.set_dc(2, '149.154.167.40', 80)

    async def _2fa(self) -> str:
        password = await self.app(GetPasswordRequest())

        while True:
            twofa = getpass("Enter 2FA password: ")
            try:
                await self.app._on_login(
                    (
                        await self.app(
                            CheckPasswordRequest(compute_check(password, twofa.strip()))
                        )
                    ).user
                )
            except errors.PasswordHashInvalidError:
                logging.error("Wrong password!")
            else:
                return twofa

    async def send_code(self) -> Tuple[str, str]:
        """Enter phone number"""
        while True:
            error_text: str = ""

            try:
                phone = input("Enter phone number: ")
                return (
                    phone,
                    (
                        await self.app.send_code_request(phone, _retry_count=5)
                    ).phone_code_hash,
                )
            except errors.PhoneNumberInvalidError:
                error_text = "Invalid phone number, please try again"
            except errors.PhoneNumberBannedError:
                error_text = "Phone number blocked"
            except errors.PhoneNumberFloodError as e:
                error_text = f"On the phone number floodwait, please wait {e.seconds}s"
            except errors.PhoneNumberUnoccupiedError:
                error_text = "Number not registered"
            except errors.BadRequestError as error:
                error_text = f"An unknown error has occurred: {error}"

            if error_text:
                logging.error(error_text)

    async def enter_code(self, phone: str, phone_code_hash: str) -> types.User:
        """Login in account"""

        code = input("Enter confirmation code: ")

        try:
            return await self.app.sign_in(phone, code, phone_code_hash=phone_code_hash)
        except errors.SessionPasswordNeededError:
            twofa = await self._2fa()

            return await self.app.sign_in(
                phone, code, password=twofa, phone_code_hash=phone_code_hash
            )

    async def authorize(self) -> Union[Tuple[types.User, TelegramClient], NoReturn]:
        """Account authorization process"""
        await self.app.connect()

        try:
            me = await self.app.get_me()
            if not me:
                raise errors.AuthKeyUnregisteredError("?")
        except errors.AuthKeyUnregisteredError:
            qr = input("Login by QR-CODE? y/n ").lower()

            if "y" in qr:
                qr_ = False
                while True:
                    try:
                        qrcode = await self.app.qr_login()
                    except errors.UnauthorizedError:
                        break

                    try:
                        if qr_:
                            _qr = await qrcode.wait(15)
                            if isinstance(_qr, tltypes.User):
                                break
                    except Exception:
                        pass

                    try:
                        await qrcode.recreate()
                    except Exception:
                        break

                    print("Settings > Devices > Scan QR Code (or Add device)\n")
                    print("Scan QR code below:")

                    qr = QRCode()

                    qr.clear()
                    qr.add_data(qrcode.url)
                    qr.print_ascii()

                    qr_ = True

                await self._2fa()

                me = await self.app.get_me()

            else:
                phone, phone_code_hash = await self.send_code()
                await self.enter_code(phone, phone_code_hash)

                me: types.User = await self.app.get_me()
        except errors.SessionRevokedError:
            logging.error("The session was terminated, delete the session and re-auth")
            self.app.disconnect()

            return sys.exit(64)

        return me, self.app
