#!/usr/bin/env python3

import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, Set, Any, Optional
from ruuvitag_sensor.ruuvi import RuuviTagSensor
import paho.mqtt.client as mqtt

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SensorConfig:
    """Configuration for a sensor type"""
    display_name: str
    device_class: str
    unit: str
    state_class: str = "measurement"

@dataclass
class RuuviTagManager:
    """Main RuuviTag manager class"""
    mqtt_host: str = "localhost"
    mqtt_port: int = 1883
    update_interval: int = 10
    configured_devices: Set[str] = field(default_factory=set)
    last_update_times: Dict[str, float] = field(default_factory=dict)

    # Define sensor configurations
    SENSOR_CONFIGS = {
        "temperature": SensorConfig("Temperature", "temperature", "°C"),
        "humidity": SensorConfig("Humidity", "humidity", "%"),
        "pressure": SensorConfig("Pressure", "pressure", "hPa"),
        "battery": SensorConfig("Battery Voltage", "voltage", "mV"),
        "rssi": SensorConfig("Signal Strength", "signal_strength", "dBm"),
        "tx_power": SensorConfig("TX Power", "signal_strength", "dBm"),
        "movement_counter": SensorConfig("Movement Counter", None, ""),
        "measurement_sequence_number": SensorConfig("Sequence Number", None, ""),
        "acceleration_x": SensorConfig("Acceleration X", None, "g"),
        "acceleration_y": SensorConfig("Acceleration Y", None, "g"),
        "acceleration_z": SensorConfig("Acceleration Z", None, "g"),
        "acceleration": SensorConfig("Total Acceleration", None, "g"),
    }

    def __post_init__(self):
        """Initialize MQTT client after dataclass initialization"""
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_log = self._on_log

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        """MQTT connection callback"""
        if reason_code == 0:
            logger.info("Connected to MQTT broker")
        else:
            logger.error(f"Failed to connect to MQTT broker: {reason_code}")

    def _on_disconnect(self, client, userdata, disconnect_flags, reason_code, properties):
        """MQTT disconnection callback"""
        logger.info("Disconnected from MQTT broker")

    def _on_log(self, client, userdata, level, buf):
        """MQTT logging callback"""
        logger.debug(f"MQTT: {buf}")

    def _get_short_address(self, mac_address: str) -> str:
        """Convert MAC address to short uppercase address from last 3 bytes"""
        mac_parts = mac_address.split(':')
        return ''.join(mac_parts[-3:]).upper()

    def _should_update(self, address: str) -> bool:
        """Check if device should be updated based on rate limiting"""
        current_time = time.time()
        if address not in self.last_update_times:
            return True

        time_since_last = current_time - self.last_update_times[address]
        return time_since_last >= self.update_interval

    def _extract_sensor_data(self, beacon_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract only the sensor data we're interested in from beacon data"""
        return {
            key: beacon_data[key]
            for key in self.SENSOR_CONFIGS.keys()
            if key in beacon_data
        }

    def _publish_ha_config(self, address: str) -> None:
        """Publish Home Assistant auto-discovery configuration for a RuuviTag device"""
        device_info = {
            "identifiers": [address],
            "name": f"RuuviTag {address}",
            "manufacturer": "Ruuvi",
            "model": "RuuviTag"
        }

        for sensor_key, config in self.SENSOR_CONFIGS.items():
            config_topic = f"homeassistant/sensor/ruuvi_{address}/{sensor_key}/config"

            config_payload = {
                "unique_id": f"{address}_{sensor_key}",
                "name": config.display_name,
                "state_topic": f"ruuvi/{address}/state",
                "value_template": f"{{{{ value_json.{sensor_key} }}}}",
                "state_class": config.state_class,
                "device": device_info
            }

            # Only add device_class and unit if they exist
            if config.device_class:
                config_payload["device_class"] = config.device_class
            if config.unit:
                config_payload["unit_of_measurement"] = config.unit

            try:
                result = self.client.publish(config_topic, json.dumps(config_payload, ensure_ascii=False))
                if result.rc != mqtt.MQTT_ERR_SUCCESS:
                    logger.warning(f"Failed to publish config for {sensor_key}: {result.rc}")
            except Exception as e:
                logger.error(f"Error publishing config for {sensor_key}: {e}")

    def _handle_data(self, found_data: tuple) -> None:
        """Handle incoming RuuviTag data"""
        try:
            mac_address, beacon_data = found_data
            address = self._get_short_address(mac_address)

            # Rate limiting check
            if not self._should_update(address):
                return

            self.last_update_times[address] = time.time()

            # Publish HA config for new devices
            if address not in self.configured_devices:
                logger.info(f"Discovered new RuuviTag: {mac_address}")
                self._publish_ha_config(address)
                self.configured_devices.add(address)

            # Extract sensor data (this replaces all the manual if statements!)
            state_data = self._extract_sensor_data(beacon_data)

            if not state_data:
                logger.warning(f"No valid sensor data found for {mac_address}")
                return

            # Publish to MQTT
            state_topic = f'ruuvi/{address}/state'
            result = self.client.publish(state_topic, json.dumps(state_data, ensure_ascii=False))

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Published data for {mac_address}: {state_data}")
            else:
                logger.warning(f"Failed to publish data for {mac_address}: {result.rc}")

        except Exception as e:
            logger.error(f"Error handling data: {e}")

    async def start(self) -> None:
        """Start the RuuviTag manager"""
        try:
            # Connect to MQTT broker
            logger.info(f"Connecting to MQTT broker at {self.mqtt_host}:{self.mqtt_port}")
            self.client.connect(self.mqtt_host, self.mqtt_port, keepalive=60)
            self.client.loop_start()

            logger.info("Started RuuviTag Manager")

            # Start collecting data from RuuviTags
            async for found_data in RuuviTagSensor.get_data_async():
                self._handle_data(found_data)

        except KeyboardInterrupt:
            logger.info("Shutting down RuuviTag Manager...")
        except Exception as e:
            logger.error(f"Error in main loop: {e}")
            raise
        finally:
            await self.stop()

    async def stop(self) -> None:
        """Stop the RuuviTag manager"""
        try:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Stopped RuuviTag Manager")
        except Exception as e:
            logger.error(f"Error stopping manager: {e}")


async def main():
    """Main async function"""
    # Get MQTT broker host from command line args or use default
    mqtt_host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'

    # Create and start the manager
    manager = RuuviTagManager(mqtt_host=mqtt_host)
    await manager.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except RuntimeError as e:
        if "asyncio.run() cannot be called from a running event loop" in str(e):
            # Fallback for Python 3.9 or when running in Jupyter
            loop = asyncio.get_event_loop()
            loop.run_until_complete(main())
        else:
            raise
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
