#!/usr/bin/env python3

from ruuvitag_sensor.ruuvitag import RuuviTagSensor
from sys import argv
import paho.mqtt.client as mqtt

client = mqtt.Client()


def mqtt_on_connect():
    print("Connected to mqtt broker")


def mqtt_on_disconnect():
    print("Disconnected from mqtt broker")


def mqtt_on_message(self, _client, _userdata, msg: mqtt.MQTTMessage):
    try:
        decoded = msg.payload.decode('utf-8', 'ignore')
        print(decoded)
    except Exception as e:
        return


def handle_data(found_data):
    global client
    address = found_data[0].replace(':', '')
    beacon_data = found_data[1]
    client.publish('home/ruuvi/{}/temp'.format(address), beacon_data['temperature'])
    client.publish('home/ruuvi/{}/humi'.format(address), beacon_data['humidity'])
    client.publish('home/ruuvi/{}/pres'.format(address), beacon_data['pressure'])


def main():
    host = argv[1] if len(argv) > 1 else 'localhost'

    client.on_connect = mqtt_on_connect
    client.on_disconnect = mqtt_on_disconnect
    client.on_message = mqtt_on_message
    client.connect(host, 1883, keepalive=60)
    client.loop_start()

    print("Started Ruuvi Tag Manager")
    while True:
        try:
            RuuviTagSensor.get_datas(handle_data)
        except Exception as e:
            print(e)
            break
    print("Stopped Ruuvi Tag Manager")


if __name__ == "__main__":
    main()
