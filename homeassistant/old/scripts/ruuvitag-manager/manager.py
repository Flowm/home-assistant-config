#!/usr/bin/env python3

import asyncio
import json
import sys
import time
from ruuvitag_sensor.ruuvi import RuuviTagSensor
import paho.mqtt.client as mqtt

# MQTT client setup
client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
configured_devices = set()
last_update_times = {}
UPDATE_INTERVAL = 10  # seconds


def mqtt_on_connect(client, userdata, flags, reason_code, properties):
    print("Connected to MQTT Broker")


def mqtt_on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
    print("Disconnected from MQTT broker")


def publish_ha_config(address):
    """Publish Home Assistant auto-discovery configuration for a RuuviTag device"""
    device_info = {
        "identifiers": address,
        "name": "RuuviTag {}".format(address),
        "manufacturer": "Ruuvi",
        "model": "RuuviTag"
    }

    sensors = [
        {
            "name": "temperature",
            "display_name": "Temperature",
            "device_class": "temperature",
            "unit": "°C",
            "value_template": "{{ value_json.temperature }}",
            "state_class": "measurement"
        },
        {
            "name": "humidity",
            "display_name": "Humidity",
            "device_class": "humidity",
            "unit": "%",
            "value_template": "{{ value_json.humidity }}",
            "state_class": "measurement"
        },
        {
            "name": "pressure",
            "display_name": "Pressure",
            "device_class": "pressure",
            "unit": "hPa",
            "value_template": "{{ value_json.pressure }}",
            "state_class": "measurement"
        },
        {
            "name": "battery",
            "display_name": "Battery Voltage",
            "device_class": "voltage",
            "unit": "mV",
            "value_template": "{{ value_json.battery }}",
            "state_class": "measurement"
        },
        {
            "name": "rssi",
            "display_name": "Signal Strength",
            "device_class": "signal_strength",
            "unit": "dBm",
            "value_template": "{{ value_json.rssi }}",
            "state_class": "measurement"
        }
    ]

    for sensor in sensors:
        config_topic = "homeassistant/sensor/ruuvi_{}/{}/config".format(address, sensor['name'])
        config_payload = {
            "unique_id": "{}_{}".format(address, sensor['name']),
            "name": sensor['display_name'],
            "state_topic": "ruuvi/{}/state".format(address),
            "device_class": sensor['device_class'],
            "unit_of_measurement": sensor['unit'],
            "value_template": sensor['value_template'],
            "state_class": sensor['state_class'],
            "device": device_info
        }
        client.publish(config_topic, json.dumps(config_payload, ensure_ascii=False))


def handle_data(found_data):
    """Handle incoming RuuviTag data"""
    mac_address = found_data[0]
    beacon_data = found_data[1]

    # Create short uppercase address from last 3 bytes of MAC
    mac_parts = mac_address.split(':')
    address = ''.join(mac_parts[-3:]).upper()

    # Rate limiting: only update every 10 seconds per device
    current_time = time.time()
    if address in last_update_times:
        time_since_last_update = current_time - last_update_times[address]
        if time_since_last_update < UPDATE_INTERVAL:
            return  # Skip this update

    last_update_times[address] = current_time

    # Publish HA config for new devices
    if address not in configured_devices:
        print(f"Discovered new RuuviTag: {mac_address}")
        publish_ha_config(address)
        configured_devices.add(address)

    # Prepare state data - include all available sensor data
    state_data = {}

    # Core sensor data
    if 'temperature' in beacon_data:
        state_data['temperature'] = beacon_data['temperature']
    if 'humidity' in beacon_data:
        state_data['humidity'] = beacon_data['humidity']
    if 'pressure' in beacon_data:
        state_data['pressure'] = beacon_data['pressure']

    # Additional sensor data available in newer data formats
    if 'battery' in beacon_data:
        state_data['battery'] = beacon_data['battery']
    if 'rssi' in beacon_data:
        state_data['rssi'] = beacon_data['rssi']
    if 'tx_power' in beacon_data:
        state_data['tx_power'] = beacon_data['tx_power']
    if 'movement_counter' in beacon_data:
        state_data['movement_counter'] = beacon_data['movement_counter']
    if 'measurement_sequence_number' in beacon_data:
        state_data['measurement_sequence_number'] = beacon_data['measurement_sequence_number']

    # Acceleration data
    if 'acceleration_x' in beacon_data:
        state_data['acceleration_x'] = beacon_data['acceleration_x']
    if 'acceleration_y' in beacon_data:
        state_data['acceleration_y'] = beacon_data['acceleration_y']
    if 'acceleration_z' in beacon_data:
        state_data['acceleration_z'] = beacon_data['acceleration_z']
    if 'acceleration' in beacon_data:
        state_data['acceleration'] = beacon_data['acceleration']

    # Publish to MQTT
    state_topic = 'ruuvi/{}/state'.format(address)
    client.publish(state_topic, json.dumps(state_data, ensure_ascii=False))

    print(f"Published data for {mac_address}: {state_data}")


async def main():
    """Main async function to handle RuuviTag data collection"""
    # Get MQTT broker host from command line args or use default
    host = sys.argv[1] if len(sys.argv) > 1 else 'localhost'

    # Setup MQTT client
    client.on_connect = mqtt_on_connect
    client.on_disconnect = mqtt_on_disconnect

    try:
        client.connect(host, 1883, keepalive=60)
        client.loop_start()

        print("Started RuuviTag Manager")
        print(f"Connected to MQTT broker at {host}")

        # Start collecting data from RuuviTags
        async for found_data in RuuviTagSensor.get_data_async():
            handle_data(found_data)

    except KeyboardInterrupt:
        print("\nShutting down RuuviTag Manager...")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.loop_stop()
        client.disconnect()
        print("Stopped RuuviTag Manager")


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
