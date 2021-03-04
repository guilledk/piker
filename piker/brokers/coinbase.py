# piker: trading gear for hackers
# Copyright (C) Tyler Goodlet (in stewardship for piker0)

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

from typing import Dict, Any

import asks

from ._util import resproc
from ..log import get_logger


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
