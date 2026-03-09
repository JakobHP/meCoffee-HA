from bleak import BleakClient
from .const import CHAR_UUID


class MeCoffeeBLE:

    def __init__(self, address, callback):
        self.address = address
        self.callback = callback
        self.client = BleakClient(address)

    async def connect(self):

        await self.client.connect()

        await self.client.start_notify(
            CHAR_UUID,
            self._handle_notify
        )

    def _handle_notify(self, sender, data):

        msg = data.decode("utf-8").strip()

        for line in msg.split("\n"):
            self.callback(line)

    async def send(self, command):

        await self.client.write_gatt_char(
            CHAR_UUID,
            command.encode("utf-8"),
            False
        )
