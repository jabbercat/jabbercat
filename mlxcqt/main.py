import asyncio

import aioxmpp.structs

import mlxc.client


class MLXCQt:
    def __init__(self, event_loop):
        self._loop = event_loop
        self._client = mlxc.client.Client()

    @asyncio.coroutine
    def run(self):
        self._client.load_state()
        self._client.set_global_presence(aioxmpp.structs.PresenceState(True))
        yield from asyncio.sleep(1)
        yield from self._client.stop_and_wait_for_all()
        self._client.save_state()
