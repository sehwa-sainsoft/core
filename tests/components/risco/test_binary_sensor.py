"""Tests for the Risco binary sensors."""
import pytest

from homeassistant.components.risco import CannotConnectError, UnauthorizedError
from homeassistant.components.risco.const import DOMAIN
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.helpers.entity_component import async_update_entity

from .util import TEST_CONFIG, TEST_SITE_UUID, setup_risco

from tests.async_mock import MagicMock, PropertyMock, patch
from tests.common import MockConfigEntry

FIRST_ENTITY_ID = "binary_sensor.zone_0"
SECOND_ENTITY_ID = "binary_sensor.zone_1"


def _zone_mock():
    return MagicMock(
        triggered=False,
        bypassed=False,
    )


@pytest.fixture
def two_zone_alarm():
    """Fixture to mock alarm with two zones."""
    zone_mocks = {0: _zone_mock(), 1: _zone_mock()}
    alarm_mock = MagicMock()
    with patch.object(
        zone_mocks[0], "id", new_callable=PropertyMock(return_value=0)
    ), patch.object(
        zone_mocks[0], "name", new_callable=PropertyMock(return_value="Zone 0")
    ), patch.object(
        zone_mocks[1], "id", new_callable=PropertyMock(return_value=1)
    ), patch.object(
        zone_mocks[1], "name", new_callable=PropertyMock(return_value="Zone 1")
    ), patch.object(
        alarm_mock,
        "zones",
        new_callable=PropertyMock(return_value=zone_mocks),
    ), patch(
        "homeassistant.components.risco.RiscoAPI.get_state",
        return_value=alarm_mock,
    ):
        yield alarm_mock


async def test_cannot_connect(hass):
    """Test connection error."""

    with patch(
        "homeassistant.components.risco.RiscoAPI.login",
        side_effect=CannotConnectError,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        registry = await hass.helpers.entity_registry.async_get_registry()
        assert not registry.async_is_registered(FIRST_ENTITY_ID)
        assert not registry.async_is_registered(SECOND_ENTITY_ID)


async def test_unauthorized(hass):
    """Test unauthorized error."""

    with patch(
        "homeassistant.components.risco.RiscoAPI.login",
        side_effect=UnauthorizedError,
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=TEST_CONFIG)
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        registry = await hass.helpers.entity_registry.async_get_registry()
        assert not registry.async_is_registered(FIRST_ENTITY_ID)
        assert not registry.async_is_registered(SECOND_ENTITY_ID)


async def test_setup(hass, two_zone_alarm):
    """Test entity setup."""
    registry = await hass.helpers.entity_registry.async_get_registry()

    assert not registry.async_is_registered(FIRST_ENTITY_ID)
    assert not registry.async_is_registered(SECOND_ENTITY_ID)

    await setup_risco(hass)

    assert registry.async_is_registered(FIRST_ENTITY_ID)
    assert registry.async_is_registered(SECOND_ENTITY_ID)

    registry = await hass.helpers.device_registry.async_get_registry()
    device = registry.async_get_device({(DOMAIN, TEST_SITE_UUID + "_zone_0")}, {})
    assert device is not None
    assert device.manufacturer == "Risco"

    device = registry.async_get_device({(DOMAIN, TEST_SITE_UUID + "_zone_1")}, {})
    assert device is not None
    assert device.manufacturer == "Risco"


async def _check_state(hass, alarm, triggered, bypassed, entity_id, zone_id):
    with patch.object(
        alarm.zones[zone_id],
        "triggered",
        new_callable=PropertyMock(return_value=triggered),
    ), patch.object(
        alarm.zones[zone_id],
        "bypassed",
        new_callable=PropertyMock(return_value=bypassed),
    ):
        await async_update_entity(hass, entity_id)
        await hass.async_block_till_done()

        expected_triggered = STATE_ON if triggered else STATE_OFF
        assert hass.states.get(entity_id).state == expected_triggered
        assert hass.states.get(entity_id).attributes["bypassed"] == bypassed


async def test_states(hass, two_zone_alarm):
    """Test the various alarm states."""
    await setup_risco(hass)

    await _check_state(hass, two_zone_alarm, True, True, FIRST_ENTITY_ID, 0)
    await _check_state(hass, two_zone_alarm, True, False, FIRST_ENTITY_ID, 0)
    await _check_state(hass, two_zone_alarm, False, True, FIRST_ENTITY_ID, 0)
    await _check_state(hass, two_zone_alarm, False, False, FIRST_ENTITY_ID, 0)
    await _check_state(hass, two_zone_alarm, True, True, SECOND_ENTITY_ID, 1)
    await _check_state(hass, two_zone_alarm, True, False, SECOND_ENTITY_ID, 1)
    await _check_state(hass, two_zone_alarm, False, True, SECOND_ENTITY_ID, 1)
    await _check_state(hass, two_zone_alarm, False, False, SECOND_ENTITY_ID, 1)


async def test_bypass(hass, two_zone_alarm):
    """Test bypassing a zone."""
    await setup_risco(hass)
    with patch("homeassistant.components.risco.RiscoAPI.bypass_zone") as mock:
        data = {"entity_id": FIRST_ENTITY_ID}

        await hass.services.async_call(
            DOMAIN, "bypass_zone", service_data=data, blocking=True
        )

        mock.assert_awaited_once_with(0, True)


async def test_unbypass(hass, two_zone_alarm):
    """Test unbypassing a zone."""
    await setup_risco(hass)
    with patch("homeassistant.components.risco.RiscoAPI.bypass_zone") as mock:
        data = {"entity_id": FIRST_ENTITY_ID}

        await hass.services.async_call(
            DOMAIN, "unbypass_zone", service_data=data, blocking=True
        )

        mock.assert_awaited_once_with(0, False)
