"""
Handles a session to EDP re:dy.
"""
import asyncio
import json
import logging

import aiohttp
import async_timeout
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

URL_BASE = "https://redy.edp.pt/EdpPortal/"
URL_LOGIN_PAGE = URL_BASE
URL_GET_ACTIVE_POWER = "{0}/Consumption/GetActivePower".format(URL_BASE)
URL_GET_SWITCH_MODULES = "{0}/HomeAutomation/GetSwitchModules".format(URL_BASE)
URL_SET_STATE_VAR = "{0}/HomeAutomation/SetStateVar".format(URL_BASE)
URL_LOGOUT = "{0}/Login/Logout".format(URL_BASE)

ACTIVE_POWER_ID = "home_active_power"

UPDATE_INTERVAL = 30
DEFAULT_TIMEOUT = 30
SESSION_TIME = 59


class EdpRedySession:
    """Representation of an http session to the service."""

    def __init__(self, username, password, aiohttp_clientsession, eventloop):
        """Init the session."""
        self._username = username
        self._password = password
        self._aiohttp_client = aiohttp_clientsession
        self._eventloop = eventloop
        self._session = None
        self._session_time = datetime.utcnow()
        self.modules_dict = {}
        self.values_dict = {}

    async def async_init_session(self):
        """Create a new http session."""
        payload_auth = {'username': self._username,
                        'password': self._password,
                        'screenWidth': '1920', 'screenHeight': '1080'}

        try:
            # fetch login page
            session = self._aiohttp_client
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._eventloop):
                resp = await session.get(URL_LOGIN_PAGE)

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while accessing login page")
            return None

        if resp.status != 200:
            _LOGGER.error("Login page returned status code %s", resp.status)
            return None

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._eventloop):
                resp = await session.post(URL_LOGIN_PAGE, data=payload_auth)

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while doing login post")
            return None

        if resp.status != 200:
            _LOGGER.error("Login post returned status code %s", resp.status)
            return None

        return session

    async def async_logout(self):
        """Logout from the current session."""
        _LOGGER.debug("Logout")

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._eventloop):
                resp = await self._session.get(URL_LOGOUT)

        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while doing logout")
            return False

        if resp.status != 200:
            _LOGGER.error("Logout returned status code %s", resp.status)
            return False

        return True

    async def async_validate_session(self):
        """Check the current session and create a new one if needed."""
        if self._session is not None:
            session_life = datetime.utcnow() - self._session_time
            if session_life.total_seconds() < SESSION_TIME:
                # Session valid, nothing to do
                return True

            # Session is older than SESSION_TIME: logout
            await self.async_logout()
            self._session = None

        # not valid, create new session
        self._session = await self.async_init_session()
        self._session_time = datetime.utcnow()
        return True if self._session is not None else False

    async def async_fetch_active_power(self):
        """Fetch new data from the server."""
        if not await self.async_validate_session():
            return False

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._eventloop):
                resp = await self._session.post(URL_GET_ACTIVE_POWER)
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while getting active power")
            return False
        if resp.status != 200:
            _LOGGER.error("Getting active power returned status code %s",
                          resp.status)
            return False

        active_power_str = await resp.text()
        _LOGGER.debug("Fetched Active Power:\n %s", active_power_str)

        if active_power_str is None:
            return False

        try:
            updated_dict = json.loads(active_power_str)
        except (json.decoder.JSONDecodeError, TypeError):
            _LOGGER.error("Error parsing active power json.")
            _LOGGER.debug("Received: \n %s", active_power_str)
            return False

        if "Body" not in updated_dict:
            return False
        if "ActivePower" not in updated_dict["Body"]:
            return False

        try:
            self.values_dict[ACTIVE_POWER_ID] = \
                updated_dict["Body"]["ActivePower"] * 1000
        except ValueError:
            _LOGGER.error("Could not parse value: ActivePower")
            self.values_dict[ACTIVE_POWER_ID] = None

        return True

    async def async_fetch_modules(self):
        """Fetch new data from the server."""
        if not await self.async_validate_session():
            return False

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._eventloop):
                resp = await self._session.post(URL_GET_SWITCH_MODULES,
                                                data={"filter": 1})
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while getting switch modules")
            return False
        if resp.status != 200:
            _LOGGER.error("Getting switch modules returned status code %s",
                          resp.status)
            return False

        modules_str = await resp.text()
        _LOGGER.debug("Fetched Modules:\n %s", modules_str)

        if modules_str is None:
            return False

        try:
            updated_dict = json.loads(modules_str)
        except (json.decoder.JSONDecodeError, TypeError):
            _LOGGER.error("Error parsing modules json.")
            _LOGGER.debug("Received: \n %s", modules_str)
            return False

        if "Body" not in updated_dict:
            return False
        if "Modules" not in updated_dict["Body"]:
            return False

        for module in updated_dict["Body"]["Modules"]:
            self.modules_dict[module['PKID']] = module

        return True

    async def async_update(self):
        """Get data from the server and update local structures."""
        modules_success = await self.async_fetch_modules()
        active_power_success = await self.async_fetch_active_power()

        return modules_success and active_power_success

    async def async_set_state_var(self, json_payload):
        """Call SetStateVar API on the server."""
        if not await self.async_validate_session():
            return False

        _LOGGER.debug("Calling %s with: %s", URL_SET_STATE_VAR,
                      str(json_payload))

        try:
            with async_timeout.timeout(DEFAULT_TIMEOUT, loop=self._eventloop):
                resp = await self._session.post(URL_SET_STATE_VAR,
                                                json=json_payload)
        except (asyncio.TimeoutError, aiohttp.ClientError):
            _LOGGER.error("Error while setting state var")
            return False
        if resp.status != 200:
            _LOGGER.error("Setting state var returned status code %s",
                          resp.status)
            return False

        return True
