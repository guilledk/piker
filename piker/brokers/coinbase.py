# piker: trading gear for hackers
# Copyright (C) Guillermo Rodriguez (in stewardship for piker0)

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

"""
Coinbase backend.
"""

import time
import json

from typing import Optional, Tuple, List, Dict, Any
from contextlib import asynccontextmanager

import trio
import asks
import tractor
import trio_websocket

from trio_websocket._impl import ConnectionClosed, DisconnectionTimeout

from ._util import resproc
from ..log import get_logger, get_console_log
from ..data import (
    _buffer,
    # iterticks,
    attach_shm_array,
    get_shm_token,
    subscribe_ohlc_for_increment,
)


log = get_logger(__name__)


_url = 'https://api.pro.coinbase.com'


class Client:

    def __init__(self) -> None:
        self._sesh = asks.Session(connections=4)
        self._sesh.base_location = _url

    async def symbol_info(
        self,
        pair: str = 'all'
    ):
        resp = await self._sesh.get(
            path='/products',
            json={},
            timeout=float('inf')
        )
        return resproc(resp, log)

    async def bars(
        self,
        symbol: str = 'BTC-USD',
        start: int = None,
        end: int = None,
        granularity: int = 60
    ) -> dict:
        params = {
            'granularity': granularity
        }
        if start is not None:
            params['start'] = start
            params['end'] = end

        return await self._sesh.get(
            path=f'/{symbol}/candles',
            json=params,
            timeout=float('inf')
        )


@asynccontextmanager
async def get_client() -> Client:
    yield Client()


async def recv_msg(recv):
    too_slow_count = last_hb = 0

    while True:
        with trio.move_on_after(1.5) as cs:
            msg = await recv()

        # trigger reconnection logic if too slow
        if cs.cancelled_caught:
            too_slow_count += 1
            if too_slow_count > 2:
                log.warning(
                    "Heartbeat is to slow, "
                    "resetting ws connection")
                raise trio_websocket._impl.ConnectionClosed(
                    "Reset Connection")

        if isinstance(msg, dict):
            if msg.get('type') == 'heartbeat':

                now = time.time()
                delay = now - last_hb
                last_hb = now
                log.trace(f"Heartbeat after {delay}")

                continue

            elif msg.get('type') == 'ticker':
                
                ex_time = datetime.strptime(
                    msg['time'],
                    "%Y-%m-%dT%H:%M:%S%z"
                )
                yield {
                    'time': ex_time.timestamp() 
                }
            
            else:
                yield msg

        else:
            # unhandled msg
            breakpoint()


# @tractor.msg.pub
async def stream_quotes(
    shm_token: Tuple[str, str, List[tuple]],
    symbols: List[str] = ['BTC-USD', 'ETH-USD'],
    loglevel: str = None,
    # compat with eventual ``tractor.msg.pub``
    topics: Optional[List[str]] = None,
) -> None:
    """Subscribe for ohlc stream of quotes for ``pairs``.

    ``symbols`` must be formatted <crypto_symbol>-<fiat_symbol>.
    """
    # XXX: required to propagate ``tractor`` loglevel to piker logging
    get_console_log(loglevel or tractor.current_actor().loglevel)

    async with get_client() as client:
        # maybe load historical ohlcv in to shared mem
        # check if shm has already been created by previous
        # feed initialization
        writer_exists = get_shm_token(shm_token['shm_name'])

        symbol = symbols[0]

        if not writer_exists:
            shm = attach_shm_array(
                token=shm_token,
                # we are writer
                readonly=False,
            )
            # bars = await client.bars(symbol=symbol)

            # shm.push(bars)
            shm_token = shm.token

            # times = shm.array['time']
            # delay_s = times[-1] - times[times != times[-1]][-1]
            # subscribe_ohlc_for_increment(shm, delay_s)

        yield shm_token, not writer_exists

        while True:
            try:
                async with trio_websocket.open_websocket_url(
                    'wss://ws-feed.pro.coinbase.com',
                ) as ws:

                    # XXX: setup subs
                    # https://docs.pro.coinbase.com/#subscribe
                    sub_msg = {
                        "type": "subscribe",
                        "product_ids": [symbol],
                        "channels": [
                            "heartbeat", "ticker"
                        ]
                    }
                    await ws.send_message(json.dumps(sub_msg))

                    async def recv():
                        return json.loads(await ws.get_message())

                    async for msg in recv_msg(recv):
                        print(json.dumps(msg, indent=4)) 


            except (ConnectionClosed, DisconnectionTimeout):
                log.exception("Good job coinbase...reconnecting")

