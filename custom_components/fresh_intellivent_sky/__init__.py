"""The Fresh Intellivent Sky integration."""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import timedelta

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from pyfreshintellivent import FreshIntelliVent

from .const import (
    AIRING_MODE_UPDATE,
    AUTH_SETTLE_DELAY,
    BOOST_SETTINGS,
    BOOST_UPDATE,
    CONF_AUTH_KEY,
    CONF_CACHE_DEVICE_INFO,
    CONF_MAX_UPDATE_RETRIES,
    CONSTANT_SPEED_UPDATE,
    DEFAULT_CACHE_DEVICE_INFO,
    DEFAULT_MAX_UPDATE_RETRIES,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    HUMIDITY_MODE_UPDATE,
    LIGHT_AND_VOC_MODE_UPDATE,
    SENSOR_READ_ATTEMPTS,
    SENSOR_READ_RETRY_DELAY,
    TIMEOUT,
    TIMER_MODE_UPDATE,
    UPDATE_RETRY_DELAY,
)
from .fetch_and_update import FetchAndUpdate


class UnableToConnect(HomeAssistantError):
    """Exception to indicate that we can not connect to device."""


ALL_UPDATES = [
    BOOST_UPDATE,
    BOOST_SETTINGS,
    CONSTANT_SPEED_UPDATE,
    AIRING_MODE_UPDATE,
    HUMIDITY_MODE_UPDATE,
    LIGHT_AND_VOC_MODE_UPDATE,
    TIMER_MODE_UPDATE,
]

AUTHENTICATED_PLATFORMS = [
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

READ_ONLY_PLATFORMS = [
    Platform.SENSOR,
]

_LOGGER = logging.getLogger(__name__)

DEVICE_INFO_LOADED = "device_info_loaded"
LAST_SUCCESSFUL_CLIENT = "last_successful_client"


def _copy_device_information(source: FreshIntelliVent, target: FreshIntelliVent) -> None:
    """Reuse cached device information without extra GATT reads."""
    target.name = source.name
    target.manufacturer = source.manufacturer
    target.fw_version = source.fw_version
    target.hw_version = source.hw_version
    target.sw_version = source.sw_version


async def _fetch_sensor_data(client: FreshIntelliVent, address: str) -> None:
    """Read the device status, retrying on the same connection."""
    for read in range(1, SENSOR_READ_ATTEMPTS + 1):
        try:
            await client.fetch_sensor_data()
            return
        except Exception as err:  # pylint: disable=broad-except
            if read == SENSOR_READ_ATTEMPTS:
                raise
            _LOGGER.debug(
                "Sensor data read %s/%s for %s failed, retrying on the same "
                "connection: %r (cause: %r)",
                read,
                SENSOR_READ_ATTEMPTS,
                address,
                err,
                err.__cause__,
            )
            await asyncio.sleep(SENSOR_READ_RETRY_DELAY)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:  # pyling: disable=too-many-statements
    """Set up Fresh Intellivent Sky."""
    hass.data.setdefault(DOMAIN, {})
    entry_data = hass.data[DOMAIN].setdefault(entry.entry_id, {})
    address = entry.unique_id

    assert address is not None

    # Make sure we remove all old data
    for update in ALL_UPDATES:
        hass.data[update] = None

    ble_device = bluetooth.async_ble_device_from_address(
        hass, address, connectable=True
    )

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Fresh Intellivent Sky device with address {address}"
        )

    auth_key = entry.data.get(CONF_AUTH_KEY)
    cache_device_info = entry.options.get(
        CONF_CACHE_DEVICE_INFO, DEFAULT_CACHE_DEVICE_INFO
    )
    max_update_retries = max(
        1, int(entry.options.get(CONF_MAX_UPDATE_RETRIES, DEFAULT_MAX_UPDATE_RETRIES))
    )

    if not ble_device:
        raise ConfigEntryNotReady(
            f"Could not find Fresh Intellivent Sky device with address {address}"
        )

    async def _async_update_method():
        """Get data from Fresh Intellivent Sky."""
        last_error: UpdateFailed | None = None
        started = time.monotonic()
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)

        for attempt in range(1, max_update_retries + 1):
            ble_device = bluetooth.async_ble_device_from_address(
                hass, address, connectable=True
            )

            if not ble_device:
                last_error = UpdateFailed(f"Unable to find device: {address}")
            else:
                client = FreshIntelliVent(ble_device=ble_device)
                error = None
                step = "connect"
                updates: FetchAndUpdate | None = None

                try:
                    await client.connect(timeout=TIMEOUT)
                    if auth_key is not None:
                        step = "authenticate"
                        await client.authenticate(authentication_code=auth_key)
                        await asyncio.sleep(AUTH_SETTLE_DELAY)
                    step = "sensor data"
                    await _fetch_sensor_data(client, address)

                    cached_client = entry_data.get(LAST_SUCCESSFUL_CLIENT)
                    if (
                        cache_device_info
                        and entry_data.get(DEVICE_INFO_LOADED)
                        and cached_client is not None
                    ):
                        _copy_device_information(cached_client, client)
                    else:
                        step = "device information"
                        await client.fetch_device_information()
                        if cache_device_info:
                            entry_data[DEVICE_INFO_LOADED] = True

                    updates = FetchAndUpdate(hass=hass, client=client)
                    await updates.update_all()
                except Exception as err:  # pylint: disable=broad-except
                    if updates is not None and updates.step is not None:
                        step = updates.step
                    # pyfreshintellivent wraps the BleakError, so the cause holds
                    # the actual reason the read failed.
                    _LOGGER.debug(
                        "Attempt %s/%s for %s failed during %s: %r (cause: %r)",
                        attempt,
                        max_update_retries,
                        address,
                        step,
                        err,
                        err.__cause__,
                    )
                    error = UpdateFailed(f"Unable to fetch data ({step}): {err}")
                finally:
                    try:
                        await client.disconnect()
                    except Exception as err:  # pylint: disable=broad-except
                        _LOGGER.error("Couldn't disconnect %s: %s", address, err)

                if error is None:
                    entry_data[LAST_SUCCESSFUL_CLIENT] = client
                    return client

                last_error = error

            if attempt < max_update_retries:
                elapsed = time.monotonic() - started
                delay = UPDATE_RETRY_DELAY * attempt
                # Each attempt already retries internally (bleak-retry-connector),
                # so stop before another one would likely run into the next poll.
                if elapsed + delay + elapsed / attempt >= scan_interval:
                    _LOGGER.debug(
                        "Not retrying %s, attempt %s/%s took %.1fs so far: %s",
                        address,
                        attempt,
                        max_update_retries,
                        elapsed,
                        last_error,
                    )
                    break
                _LOGGER.debug(
                    "Attempt %s/%s for %s failed, retrying: %s",
                    attempt,
                    max_update_retries,
                    address,
                    last_error,
                )
                await asyncio.sleep(delay)

        if last_error is not None:
            raise last_error

        raise UpdateFailed(f"Unable to fetch data from {address}")

    entry_data[CONF_SCAN_INTERVAL] = entry.options.get(
        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
    )

    entry.async_on_unload(entry.add_update_listener(update_listener))

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=DOMAIN,
        update_method=_async_update_method,
        update_interval=timedelta(
            seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        ),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(
        entry,
        READ_ONLY_PLATFORMS if auth_key is None else AUTHENTICATED_PLATFORMS
    )

    return True


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Update when config_entry options update."""
    _LOGGER.debug("Config entry was updated, rerunning setup")
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, AUTHENTICATED_PLATFORMS
    ):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
