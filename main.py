import machine
import bluetooth
import struct
import time
import ubinascii

from micropython import const
from machine import Pin
from ble_advertising import advertising_payload

_IRQ_CENTRAL_CONNECT    = const(1)
_IRQ_CENTRAL_DISCONNECT = const(2)
_IRQ_GATTS_WRITE        = const(3)

MIDI_SERVICE_UUID = bluetooth.UUID('03B80E5A-EDE8-4B33-A751-6CE34EC4C700')
MIDI_CHAR_UUID    = bluetooth.UUID('7772E5DB-3868-4112-A1A9-F2669D106BF3')
BLE_MIDI_CHAR     = (MIDI_CHAR_UUID, bluetooth.FLAG_READ | bluetooth.FLAG_NOTIFY | bluetooth.FLAG_WRITE | bluetooth.FLAG_WRITE_NO_RESPONSE)
BLE_MIDI_SERVICE  = (MIDI_SERVICE_UUID, (BLE_MIDI_CHAR,))
SERVICES = (BLE_MIDI_SERVICE, )
PAYLOAD  = advertising_payload(
    name="PicoMIDI",
    services=[MIDI_SERVICE_UUID],
)

isConnected = False
timestamp = 0

def sendNote(channel, note, velocity):
    global bt
    global conn_handle
    global midi_handle
    global timestamp

    timestamp += 1
    if (velocity == 0):
        status = 0x80 | (channel & 0x0f)  # NoteOff
    else:
        status = 0x90 | (channel & 0x0f)  # NoteOn
    txdata = bytearray([0x80 | (timestamp >> 7), 0x80 | (timestamp & 0x7f), status, note, velocity])
    bt.gatts_notify(conn_handle, midi_handle, txdata)
    print("send", txdata)

def sendCC(channel, number, value):
    global bt
    global conn_handle
    global midi_handle
    global timestamp

    timestamp += 1
    status = 0xb0 | (channel & 0x0f)  # CC
    txdata = bytearray([0x80 | (timestamp >> 7), 0x80 | (timestamp & 0x7f), status, number, value])
    bt.gatts_notify(conn_handle, midi_handle, txdata)
    print("send", txdata)

def parseMidiData(data):
    print("parse", data)
    if ((data[0] & 0x80) == 0) | ((data[1] & 0x80) == 0):
        return

    length = len(data)
    n = 2
    while (n + 2 < length):
        if ((data[n] & 0xf0) == 0x80):
            # Note Off
            a = data[n + 1] & 0x7f
            b = data[n + 2] & 0x7f
            print("NoteOff", a, b)
            n += 2

        elif ((data[n] & 0xf0) == 0x90):
            # Note On
            a = data[n + 1] & 0x7f
            b = data[n + 2] & 0x7f
            print("NoteOn", a, b)
            n += 2

        elif ((data[n] & 0xf0) == 0xb0):
            # Control Change
            a = data[n + 1] & 0x7f
            b = data[n + 2] & 0x7f
            print("CC", a, b)
            n += 2

        n += 1

def isrBt(event, data):
    global bt
    global conn_handle
    global isConnected

    if (event == _IRQ_CENTRAL_CONNECT):
        # Connect
        conn_handle, _, _ = data
        isConnected = True
        print("Connected", conn_handle)

    elif (event == _IRQ_CENTRAL_DISCONNECT):
        # Disconnect
        conn_handle, _, _ = data
        isConnected = False
        print("Disconnected", conn_handle)
        # re-start advertising
        bt.gap_advertise(500000, adv_data=PAYLOAD)

    elif (event == _IRQ_GATTS_WRITE):
        # Receive
        conn_handle, value_handle = data
        rxdata = bt.gatts_read(value_handle)
        parseMidiData(rxdata)

#    else:
#        print("IRQ", event)


def work():
    global bt
    global conn_handle
    global midi_handle
    global isConnected

    led = Pin('LED', Pin.OUT)
    sw1 = Pin(0, Pin.IN, Pin.PULL_UP)
    sw2 = Pin(1, Pin.IN, Pin.PULL_UP)

    # Bluetooth LE
    bt = bluetooth.BLE()
    bt.irq(isrBt)
    bt.active(True)
    # resister GATT server
    ((midi_handle,),) = bt.gatts_register_services(SERVICES)
    # start advertising
    bt.gap_advertise(500000, adv_data=PAYLOAD)
    print("Advertising", midi_handle)

    while True:
        if (sw1.value() == 0):
            print("sw1")
            if (isConnected):
                sendNote(0, 60, 100)  # C4

        if (sw2.value() == 0):
            print("sw2")
            if (isConnected):
                sendCC(0, 1, 100)

        led.toggle()
        if (isConnected):
            time.sleep_ms(250)
        else:
            time.sleep_ms(500)
 

if __name__ == "__main__":
    work()

