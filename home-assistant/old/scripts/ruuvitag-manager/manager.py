#!/usr/bin/env python3

from ruuvitag_sensor.ruuvitag import RuuviTagSensor
from sys import argv
import paho.mqtt.client as mqtt

client = mqtt.Client()


def mqtt_on_connect(client, userdata, flags, rc):
    print("Connected to Mqtt Broker")


def mqtt_on_disconnect(client, userdata, rc):
    print("Disconnected from mqtt broker")


def handle_data(found_data):
    address = found_data[0].replace(':', '')
    beacon_data = found_data[1]
    client.publish('home/ruuvi/{}/temp'.format(address), beacon_data['temperature'])
    client.publish('home/ruuvi/{}/humi'.format(address), beacon_data['humidity'])
    client.publish('home/ruuvi/{}/pres'.format(address), int(beacon_data['pressure']*100))


def main():
    host = argv[1] if len(argv) > 1 else 'localhost'

    client.on_connect = mqtt_on_connect
    client.on_disconnect = mqtt_on_disconnect
    client.connect(host, 1883, keepalive=60)
    client.loop_start()

    print("Started Ruuvi Tag Manager")
    RuuviTagSensor.get_datas(handle_data)
    print("Stopped Ruuvi Tag Manager")


if __name__ == "__main__":
    main()
