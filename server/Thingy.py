#!/usr/bin/env python

import signal
import os
import asyncio
import json
import time
from websocket import create_connection
import gmqtt as mqtt
from dotenv import load_dotenv

# Load the .env into the environement
load_dotenv()

DEBUG = True
SERVER_ADRESS = "127.0.0.1:8080"


def debug(*a, **b):
    if DEBUG:
        print(*a, **b)


class Thingy:
    # MQTT Config from the environement variable
    MQTT_HOST = os.getenv("MQTT_HOST")
    MQTT_PORT = int(os.getenv("MQTT_PORT"))
    MQTT_USER = os.getenv("MQTT_USER")
    MQTT_PWD = os.getenv("MQTT_PWD")

    # Broker endpoints
    SUB_TOPIC = "things/{}/shadow/update"
    PUB_TOPIC = "things/{}/shadow/update/accepted"

    STOP = asyncio.Event()

    client = None

    def __init__(self, device):
        self.device = device
        # Callbacks
        self.on_press = lambda *args: None
        self.on_release = lambda *args: None

    async def create_connection(self):
        self.client = mqtt.Client("")

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        self.client.on_subscribe = self.on_subscribe

        self.client.set_auth_credentials(Thingy.MQTT_USER, Thingy.MQTT_PWD)

        await self.client.connect(Thingy.MQTT_HOST, Thingy.MQTT_PORT)

        await Thingy.STOP.wait()
        await self.client.disconnect()

    def on_connect(self, client, flags, rc, properties):
        debug(f"{self.device} Connected!")
        topic = Thingy.SUB_TOPIC.format(self.device)
        client.subscribe(topic, qos=0)

    def on_message(self, client, topic, payload, qos, properties):
        # debug('RECV MSG:', payload)
        data = json.loads(payload)
        if data["appId"] == "BUTTON":
            if data["data"] == "1":
                self.on_press()
            if data["data"] == "0":
                self.on_release()

    def set_color(self, color):
        msg = '{"appId":"LED","data":{"color":"' + \
            color + '"},"messageType":"CFG_SET"}'
        topic = Thingy.PUB_TOPIC.format(self.device)
        self.client.publish(topic, msg, qos=1)

    def _play(self, frequency):
        msg = '{"appId":"BUZZER","data":{"frequency":' + \
            str(frequency) + '},"messageType":"CFG_SET"}'
        topic = Thingy.PUB_TOPIC.format(self.device)
        self.client.publish(topic, msg, qos=1)

    def play(self, frequency, t):
        self._play(frequency)
        time.sleep(t)
        self._play(0)

    def on_disconnect(self, client, packet, exc=None):
        debug(f"{self.device} Disconnected!")

    def on_subscribe(self, client, mid, qos, properties):
        debug(f"{self.device} Subscribed!")

    def ask_exit(*args):
        Thingy.STOP.set()


def create_thingy(thingy_id):
    # TODO: each user should have different thingy
    thingy = Thingy(thingy_id)

    def on_press():
        print("Pressed!")
        thingy.set_color("ffffff")
        thingy.play(440, 1)
        ws = create_connection(f'ws://{SERVER_ADRESS}/ws')
        ws.send("BUTTON-"+thingy_id)
        ws.close()

    def on_release():
        print("Release!")
        thingy.set_color("000000")


    thingy.on_press = on_press
    thingy.on_release = on_release
    return thingy


if __name__ == '__main__':
    loop = asyncio.get_event_loop()

    # Set the signal to release the connection when closing the program
    loop.add_signal_handler(signal.SIGINT, Thingy.ask_exit)
    loop.add_signal_handler(signal.SIGTERM, Thingy.ask_exit)

    # Get configured thingy
    thingy =create_thingy("orange-2")

    # Create the connection cooroutine
    connection = thingy.create_connection()

    loop.run_until_complete(connection)
