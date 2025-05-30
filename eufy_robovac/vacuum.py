"""Support for Eufy vacuum cleaners."""
import logging

from homeassistant.components.vacuum import (
    StateVacuumEntity, VacuumEntityFeature, VacuumActivity
)

from . import robovac

_LOGGER = logging.getLogger(__name__)


FAN_SPEED_OFF = 'Off'
FAN_SPEED_STANDARD = 'Standard'
FAN_SPEED_BOOST_IQ = 'Boost IQ'
FAN_SPEED_MAX = 'Max'
FAN_SPEEDS = {
    robovac.CleanSpeed.NO_SUCTION: FAN_SPEED_OFF,
    robovac.CleanSpeed.STANDARD: FAN_SPEED_STANDARD,
    robovac.CleanSpeed.BOOST_IQ: FAN_SPEED_BOOST_IQ,
    robovac.CleanSpeed.MAX: FAN_SPEED_MAX,
}


SUPPORT_ROBOVAC_T2118 = (
    VacuumEntityFeature.BATTERY | VacuumEntityFeature.CLEAN_SPOT | 
    VacuumEntityFeature.FAN_SPEED | VacuumEntityFeature.LOCATE |
    VacuumEntityFeature.PAUSE | VacuumEntityFeature.RETURN_HOME | 
    VacuumEntityFeature.START | VacuumEntityFeature.STATUS |
    VacuumEntityFeature.TURN_OFF | VacuumEntityFeature.TURN_ON
)


MODEL_CONFIG = {
    'T2118': {
        'fan_speeds': FAN_SPEEDS,
        'support': SUPPORT_ROBOVAC_T2118
    }
}


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Eufy vacuum cleaners."""
    if discovery_info is None:
        return
    add_entities([EufyVacuum(discovery_info)], True)


class EufyVacuum(StateVacuumEntity):
    """Representation of a Eufy vacuum cleaner."""

    def __init__(self, device_config):
        """Initialize the vacuum."""

        try:
            self._config = MODEL_CONFIG[device_config['model'].upper()]
        except KeyError:
            raise RuntimeError("Unsupported model {}".format(
                device_config['model']))

        self._fan_speed_reverse_mapping = {
            v: k for k, v in self._config['fan_speeds'].items()}
        self._device_id = device_config['device_id']
        self.robovac = robovac.Robovac(
            device_config['device_id'], device_config['address'],
            device_config['local_key'])
        self._name = device_config['name']
        self._available = False

    async def async_update(self):
        """Synchronise state from the vacuum."""
        try:
            if not self.robovac._connected:
                await self.robovac.async_connect()
            await self.robovac.async_get()
            self._available = True
            _LOGGER.debug(f"Successfully updated vacuum {self._name}, state: {self.robovac.state}")
        except Exception as e:
            _LOGGER.error(f"Failed to update vacuum {self._name}: {e}")
            self._available = False

    @property
    def unique_id(self):
        """Return the ID of this vacuum."""
        return self._device_id

    @property
    def name(self):
        """Return the name of the device if any."""
        return self._name

    @property
    def is_on(self):
        """Return true if device is on."""
        return self.robovac.work_status == robovac.WorkStatus.RUNNING

    @property
    def supported_features(self):
        """Flag vacuum cleaner robot features that are supported."""
        return self._config['support']

    @property
    def fan_speed(self):
        """Return the fan speed of the vacuum cleaner."""
        return self._config['fan_speeds'].get(
            self.robovac.clean_speed, FAN_SPEED_OFF)

    @property
    def fan_speed_list(self):
        """Get the list of available fan speed steps of the vacuum cleaner."""
        return list(self._config['fan_speeds'].values())

    @property
    def battery_level(self):
        """Return the battery level of the vacuum cleaner."""
        return self.robovac.battery_level

    @property
    def activity(self) -> VacuumActivity | None:
        """Return the current activity of the vacuum cleaner."""
        if self.robovac.error_code != robovac.ErrorCode.NO_ERROR:
            return VacuumActivity.ERROR
        elif self.robovac.go_home:
            return VacuumActivity.RETURNING
        elif self.robovac.work_status == robovac.WorkStatus.RUNNING:
            return VacuumActivity.CLEANING
        elif self.robovac.work_status == robovac.WorkStatus.CHARGING:
            return VacuumActivity.DOCKED
        elif self.robovac.work_status == robovac.WorkStatus.RECHARGE_NEEDED:
            # Should be captured by `go_home` above, but just in case
            return VacuumActivity.RETURNING
        elif self.robovac.work_status == robovac.WorkStatus.SLEEPING:
            return VacuumActivity.IDLE
        elif self.robovac.work_status == robovac.WorkStatus.STAND_BY:
            return VacuumActivity.PAUSED
        elif self.robovac.work_status == robovac.WorkStatus.COMPLETED:
            return VacuumActivity.DOCKED
        
        return VacuumActivity.IDLE

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._available

    async def async_return_to_base(self, **kwargs):
        """Set the vacuum cleaner to return to the dock."""
        await self.robovac.async_go_home()

    async def async_clean_spot(self, **kwargs):
        """Perform a spot clean-up."""
        await self.robovac.async_set_work_mode(robovac.WorkMode.SPOT)

    async def async_locate(self, **kwargs):
        """Locate the vacuum cleaner."""
        await self.robovac.async_find_robot()

    async def async_set_fan_speed(self, fan_speed, **kwargs):
        """Set fan speed."""
        clean_speed = self._fan_speed_reverse_mapping[fan_speed]
        await self.robovac.async_set_clean_speed(clean_speed)

    async def async_turn_on(self, **kwargs):
        """Turn the vacuum on."""
        await self.robovac.async_set_work_mode(robovac.WorkMode.AUTO)

    async def async_turn_off(self, **kwargs):
        """Turn the vacuum off and return to home."""
        await self.async_return_to_base()

    async def async_start(self, **kwargs):
        """Resume the cleaning cycle."""
        await self.async_turn_on()

    async def async_resume(self, **kwargs):
        """Resume the cleaning cycle."""
        await self.robovac.async_play()

    async def async_pause(self, **kwargs):
        """Pause the cleaning cycle."""
        await self.robovac.async_pause()

    async def async_start_pause(self, **kwargs):
        """Pause the cleaning task or resume it."""
        if self.robovac.play_pause:
            await self.async_pause()
        else:
            await self.async_resume()
