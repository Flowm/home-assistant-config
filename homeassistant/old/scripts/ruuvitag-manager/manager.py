#!/usr/bin/env python3

from ruuvitag_sensor.ruuvitag import RuuviTagSensor
from sys import argv
import paho.mqtt.client as mqtt
import json

client = mqtt.Client()
configured_devices = set()


def mqtt_on_connect(client, userdata, flags, rc):
    print("Connected to Mqtt Broker")


def mqtt_on_disconnect(client, userdata, rc):
    print("Disconnected from mqtt broker")


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
    address = found_data[0].replace(':', '')
    beacon_data = found_data[1]

    # Publish HA config for new devices
    if address not in configured_devices:
        publish_ha_config(address)
        configured_devices.add(address)

    state_data = {
        'temperature': beacon_data['temperature'],
        'humidity': beacon_data['humidity'],
        'pressure': beacon_data['pressure']
    }

    client.publish('ruuvi/{}/state'.format(address), json.dumps(state_data, ensure_ascii=False))


def main():
    host = argv[1] if len(argv) > 1 else '192.168.144.10'

    client.on_connect = mqtt_on_connect
    client.on_disconnect = mqtt_on_disconnect
    client.connect(host, 1883, keepalive=60)
    client.loop_start()

    print("Started Ruuvi Tag Manager")
    RuuviTagSensor.get_datas(handle_data)
    print("Stopped Ruuvi Tag Manager")


if __name__ == "__main__":
    main()
