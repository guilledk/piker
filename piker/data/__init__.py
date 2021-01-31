# piker: trading gear for hackers
# Copyright (C) 2018-present  Tyler Goodlet (in stewardship of piker0)

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
Data feed apis and infra.

We provide tsdb integrations for retrieving
and storing data from your brokers as well as
sharing your feeds with other fellow pikers.
"""
from dataclasses import dataclass
from contextlib import asynccontextmanager
from importlib import import_module
from types import ModuleType
from typing import (
    Dict, List, Any,
    Sequence, AsyncIterator, Optional
)

import tractor

from ..brokers import get_brokermod
from ..log import get_logger, get_console_log
from .._daemon import spawn_brokerd, maybe_spawn_pikerd
from ._normalize import iterticks
from ._sharedmem import (
    maybe_open_shm_array,
    attach_shm_array,
    open_shm_array,
    ShmArray,
    get_shm_token,
)
from ._source import base_iohlc_dtype
from ._buffer import (
    increment_ohlc_buffer,
    subscribe_ohlc_for_increment
)

__all__ = [
    'iterticks',
    'maybe_open_shm_array',
    'attach_shm_array',
    'open_shm_array',
    'get_shm_token',
    'subscribe_ohlc_for_increment',
]


log = get_logger(__name__)

__ingestors__ = [
    'marketstore',
]


def get_ingestormod(name: str) -> ModuleType:
    """Return the imported ingestor module by name.
    """
    module = import_module('.' + name, 'piker.data')
    # we only allow monkeying because it's for internal keying
    module.name = module.__name__.split('.')[-1]
    return module


@asynccontextmanager
async def maybe_spawn_brokerd(
    brokername: str,
    loglevel: Optional[str] = None
) -> tractor._portal.Portal:
    """If no ``brokerd.{brokername}`` daemon-actor can be found,
    spawn one in a local subactor and return a portal to it.
    """
    if loglevel:
        get_console_log(loglevel)

    # disable debugger in brokerd?
    # tractor._state._runtime_vars['_debug_mode'] = False

    dname = f'brokerd.{brokername}'
    async with tractor.find_actor(dname) as portal:

        # WTF: why doesn't this work?
        if portal is not None:
            yield portal

        else:  # no daemon has been spawned yet
            async with maybe_spawn_pikerd(
                loglevel=loglevel
            ) as pikerd_portal:

                if pikerd_portal is None:
                    await spawn_brokerd(
                        brokername, loglevel=loglevel
                    )

                else:
                    await pikerd_portal.run(
                        spawn_brokerd,
                        brokername=brokername,
                        loglevel=loglevel
                    )

                async with tractor.wait_for_actor(dname) as portal:
                    yield portal



@dataclass
class Feed:
    """A data feed for client-side interaction with far-process
    real-time data sources.

    This is an thin abstraction on top of ``tractor``'s portals for
    interacting with IPC streams and conducting automatic
    memory buffer orchestration.
    """
    name: str
    stream: AsyncIterator[Dict[str, Any]]
    shm: ShmArray
    # ticks: ShmArray
    _brokerd_portal: tractor._portal.Portal
    _index_stream: Optional[AsyncIterator[Dict[str, Any]]] = None

    async def receive(self) -> dict:
        return await self.stream.__anext__()

    async def index_stream(self) -> AsyncIterator[int]:
        if not self._index_stream:
            # XXX: this should be singleton on a host,
            # a lone broker-daemon per provider should be
            # created for all practical purposes
            self._index_stream = await self._brokerd_portal.run(
                increment_ohlc_buffer,
                shm_token=self.shm.token,
                topics=['index'],
            )

        return self._index_stream


def sym_to_shm_key(
    broker: str,
    symbol: str,
) -> str:
    return f'{broker}.{symbol}'


@asynccontextmanager
async def open_feed(
    name: str,
    symbols: Sequence[str],
    loglevel: Optional[str] = None,
) -> AsyncIterator[Dict[str, Any]]:
    """Open a "data feed" which provides streamed real-time quotes.
    """
    try:
        mod = get_brokermod(name)
    except ImportError:
        mod = get_ingestormod(name)

    if loglevel is None:
        loglevel = tractor.current_actor().loglevel

    # Attempt to allocate (or attach to) shm array for this broker/symbol
    shm, opened = maybe_open_shm_array(
        key=sym_to_shm_key(name, symbols[0]),

        # use any broker defined ohlc dtype:
        dtype=getattr(mod, '_ohlc_dtype', base_iohlc_dtype),

        # we expect the sub-actor to write
        readonly=True,
    )

    async with maybe_spawn_brokerd(
        mod.name,
        loglevel=loglevel,
    ) as portal:
        stream = await portal.run(
            mod.stream_quotes,
            symbols=symbols,
            shm_token=shm.token,

            # compat with eventual ``tractor.msg.pub``
            topics=symbols,
        )

        # TODO: we can't do this **and** be compate with
        # ``tractor.msg.pub``, should we maybe just drop this after
        # tests are in?
        shm_token, is_writer = await stream.receive()

        if opened:
            assert is_writer
            log.info("Started shared mem bar writer")

        shm_token['dtype_descr'] = list(shm_token['dtype_descr'])
        assert shm_token == shm.token  # sanity

        yield Feed(
            name=name,
            stream=stream,
            shm=shm,
            _brokerd_portal=portal,
        )
