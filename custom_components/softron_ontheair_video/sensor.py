"""Sensors for Softron OnTheAir Video."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL
from .coordinator import OnTheAirVideoCoordinator, OnTheAirVideoData


@dataclass(frozen=True, kw_only=True)
class OnTheAirVideoSensorDescription(SensorEntityDescription):
    """Describes an OnTheAir Video sensor."""

    value_fn: Callable[[OnTheAirVideoData], Any]
    attrs_fn: Callable[[OnTheAirVideoData], dict[str, Any]] | None = None


def _seconds(value: float | None) -> float | None:
    """Return positive whole seconds."""
    if value is None:
        return None
    return round(abs(value), 1)


SENSORS: tuple[OnTheAirVideoSensorDescription, ...] = (
    OnTheAirVideoSensorDescription(
        key="status",
        translation_key="status",
        icon="mdi:television-play",
        value_fn=lambda data: data.status,
    ),
    OnTheAirVideoSensorDescription(
        key="current_clip",
        translation_key="current_clip",
        icon="mdi:filmstrip",
        value_fn=lambda data: data.title,
    ),
    OnTheAirVideoSensorDescription(
        key="playlist",
        translation_key="playlist",
        icon="mdi:playlist-play",
        value_fn=lambda data: data.playlist,
    ),
    OnTheAirVideoSensorDescription(
        key="next_clip",
        translation_key="next_clip",
        icon="mdi:skip-next",
        value_fn=lambda data: data.next_title,
    ),
    OnTheAirVideoSensorDescription(
        key="elapsed",
        translation_key="elapsed",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        value_fn=lambda data: _seconds(data.elapsed),
        attrs_fn=lambda data: {"timecode": data.elapsed_timecode},
    ),
    OnTheAirVideoSensorDescription(
        key="remaining",
        translation_key="remaining",
        icon="mdi:timer-sand",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        value_fn=lambda data: _seconds(data.remaining),
        attrs_fn=lambda data: {"timecode": data.remaining_timecode},
    ),
    OnTheAirVideoSensorDescription(
        key="duration",
        translation_key="duration",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_display_precision=0,
        entity_registry_enabled_default=False,
        value_fn=lambda data: _seconds(data.duration),
        attrs_fn=lambda data: {"timecode": data.duration_timecode},
    ),
    OnTheAirVideoSensorDescription(
        key="next_live",
        translation_key="next_live",
        icon="mdi:access-point",
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.next_live,
        attrs_fn=lambda data: {"seconds_until": _seconds(data.until_next_live)},
    ),
    OnTheAirVideoSensorDescription(
        key="fps",
        translation_key="fps",
        icon="mdi:filmstrip-box",
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
        value_fn=lambda data: data.fps,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the sensors."""
    coordinator: OnTheAirVideoCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        OnTheAirVideoSensor(coordinator, entry, description)
        for description in SENSORS
    )


class OnTheAirVideoSensor(
    CoordinatorEntity[OnTheAirVideoCoordinator], SensorEntity
):
    """A single OnTheAir Video sensor."""

    _attr_has_entity_name = True
    entity_description: OnTheAirVideoSensorDescription

    def __init__(
        self,
        coordinator: OnTheAirVideoCoordinator,
        entry: ConfigEntry,
        description: OnTheAirVideoSensorDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=MODEL,
            configuration_url=coordinator.client.base_url,
        )

    @property
    def native_value(self) -> Any:
        """Return the sensor value."""
        if self.coordinator.data is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra attributes."""
        if self.coordinator.data is None or self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
