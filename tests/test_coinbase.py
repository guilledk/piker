from piker.brokers.coinbase import Client

async def test_coinbase_get_symbols():
    cbclient = Client()

    sym_info = await cbclient.symbol_info()

    bars = await cbclient.bars()

    breakpoint()
