from fixtures import *
from test_framework.utils import wait_for, get_txid, spend_coins


def get_coin(minisafed, outpoint_or_txid):
    return next(
        c
        for c in minisafed.rpc.listcoins()["coins"]
        if outpoint_or_txid in c["outpoint"]
    )


def test_reorg_detection(minisafed, bitcoind):
    """Test we detect block chain reorganization under various conditions."""
    initial_height = bitcoind.rpc.getblockcount()
    wait_for(lambda: minisafed.rpc.getinfo()["blockheight"] == initial_height)

    # Re-mine the last block. We should detect it as a reorg.
    bitcoind.invalidate_remine(initial_height)
    minisafed.wait_for_logs(
        ["Block chain reorganization detected.", "Tip was rolled back."]
    )
    wait_for(lambda: minisafed.rpc.getinfo()["blockheight"] == initial_height)

    # Same if we re-mine the next-to-last block.
    bitcoind.invalidate_remine(initial_height - 1)
    minisafed.wait_for_logs(
        ["Block chain reorganization detected.", "Tip was rolled back."]
    )
    wait_for(lambda: minisafed.rpc.getinfo()["blockheight"] == initial_height)

    # Same if we re-mine a deep block.
    bitcoind.invalidate_remine(initial_height - 50)
    minisafed.wait_for_logs(
        ["Block chain reorganization detected.", "Tip was rolled back."]
    )
    wait_for(lambda: minisafed.rpc.getinfo()["blockheight"] == initial_height)

    # Same if the new chain is longer.
    bitcoind.simple_reorg(initial_height - 10, shift=20)
    minisafed.wait_for_logs(
        ["Block chain reorganization detected.", "Tip was rolled back."]
    )
    wait_for(lambda: minisafed.rpc.getinfo()["blockheight"] == initial_height + 10)


def test_reorg_exclusion(minisafed, bitcoind):
    """Test the unconfirmation by a reorg of a coin in various states."""
    initial_height = bitcoind.rpc.getblockcount()
    wait_for(lambda: minisafed.rpc.getinfo()["blockheight"] == initial_height)

    # A confirmed received coin
    addr = minisafed.rpc.getnewaddress()["address"]
    txid = bitcoind.rpc.sendtoaddress(addr, 1)
    bitcoind.generate_block(1, wait_for_mempool=txid)
    wait_for(lambda: len(minisafed.rpc.listcoins()["coins"]) == 1)
    coin_a = minisafed.rpc.listcoins()["coins"][0]

    # A confirmed and 'spending' (unconfirmed spend) coin
    addr = minisafed.rpc.getnewaddress()["address"]
    txid = bitcoind.rpc.sendtoaddress(addr, 2)
    bitcoind.generate_block(1, wait_for_mempool=txid)
    wait_for(lambda: len(minisafed.rpc.listcoins()["coins"]) == 2)
    coin_b = get_coin(minisafed, txid)
    b_spend_tx = spend_coins(minisafed, bitcoind, [coin_b])

    # A confirmed and spent coin
    addr = minisafed.rpc.getnewaddress()["address"]
    txid = bitcoind.rpc.sendtoaddress(addr, 3)
    bitcoind.generate_block(1, wait_for_mempool=txid)
    wait_for(lambda: len(minisafed.rpc.listcoins()["coins"]) == 3)
    coin_c = get_coin(minisafed, txid)
    c_spend_tx = spend_coins(minisafed, bitcoind, [coin_c])
    bitcoind.generate_block(1, wait_for_mempool=1)

    # Reorg the chain down to the initial height, excluding all transactions.
    current_height = bitcoind.rpc.getblockcount()
    bitcoind.simple_reorg(initial_height, shift=-1)
    wait_for(lambda: minisafed.rpc.getinfo()["blockheight"] == current_height + 1)

    # They must all be marked as unconfirmed.
    new_coin_a = get_coin(minisafed, coin_a["outpoint"])
    assert new_coin_a["block_height"] is None
    new_coin_b = get_coin(minisafed, coin_b["outpoint"])
    assert new_coin_b["block_height"] is None
    new_coin_c = get_coin(minisafed, coin_c["outpoint"])
    assert new_coin_c["block_height"] is None

    # And if we now confirm everything, they'll be marked as such. The one that was 'spending'
    # will now be spent (its spending transaction will be confirmed) and the one that was spent
    # will be marked as such.
    deposit_txids = [c["outpoint"][:-2] for c in (coin_a, coin_b, coin_c)]
    for txid in deposit_txids:
        tx = bitcoind.rpc.gettransaction(txid)["hex"]
        bitcoind.rpc.sendrawtransaction(tx)
    bitcoind.rpc.sendrawtransaction(b_spend_tx)
    bitcoind.rpc.sendrawtransaction(c_spend_tx)
    bitcoind.generate_block(1, wait_for_mempool=5)
    new_height = bitcoind.rpc.getblockcount()
    wait_for(lambda: minisafed.rpc.getinfo()["blockheight"] == new_height)
    assert all(
        c["block_height"] == new_height for c in minisafed.rpc.listcoins()["coins"]
    ), (minisafed.rpc.listcoins()["coins"], new_height)
    new_coin_b = next(
        c
        for c in minisafed.rpc.listcoins()["coins"]
        if coin_b["outpoint"] == c["outpoint"]
    )
    b_spend_txid = get_txid(b_spend_tx)
    assert new_coin_b["spend_info"]["txid"] == b_spend_txid
    assert new_coin_b["spend_info"]["height"] == new_height
    new_coin_c = next(
        c
        for c in minisafed.rpc.listcoins()["coins"]
        if coin_c["outpoint"] == c["outpoint"]
    )
    c_spend_txid = get_txid(c_spend_tx)
    assert new_coin_c["spend_info"]["txid"] == c_spend_txid
    assert new_coin_c["spend_info"]["height"] == new_height

    # TODO: maybe test with some malleation for the deposit and spending txs?


def spend_confirmed_noticed(minisafed, outpoint):
    c = get_coin(minisafed, outpoint)
    if c["spend_info"] is None:
        return False
    if c["spend_info"]["height"] is None:
        return False
    return True


def test_reorg_status_recovery(minisafed, bitcoind):
    """
    Test the coins that were not unconfirmed recover their initial state after a reorg.
    """
    list_coins = lambda: minisafed.rpc.listcoins()["coins"]

    # Create two confirmed coins. Note how we take the initial_height after having
    # mined them, as we'll reorg back to this height and due to anti fee-sniping
    # these deposit transactions might not be valid anymore!
    addresses = (minisafed.rpc.getnewaddress()["address"] for _ in range(2))
    txids = [bitcoind.rpc.sendtoaddress(addr, 0.5670) for addr in addresses]
    bitcoind.generate_block(1, wait_for_mempool=txids)
    initial_height = bitcoind.rpc.getblockcount()
    wait_for(lambda: minisafed.rpc.getinfo()["blockheight"] == initial_height)

    # Both coins are confirmed. Spend the second one then get their infos.
    wait_for(lambda: len(list_coins()) == 2)
    wait_for(lambda: all(c["block_height"] is not None for c in list_coins()))
    coin_b = get_coin(minisafed, txids[1])
    spend_coins(minisafed, bitcoind, [coin_b])
    bitcoind.generate_block(1, wait_for_mempool=1)
    wait_for(lambda: spend_confirmed_noticed(minisafed, coin_b["outpoint"]))
    coin_a = get_coin(minisafed, txids[0])
    coin_b = get_coin(minisafed, txids[1])

    # Reorg the chain down to the initial height without shifting nor malleating
    # any transaction. The coin info should be identical (except the transaction
    # spending the second coin will be mined at the height the reorg happened).
    bitcoind.simple_reorg(initial_height, shift=0)
    new_height = bitcoind.rpc.getblockcount()
    wait_for(lambda: minisafed.rpc.getinfo()["blockheight"] == new_height)
    new_coin_a = get_coin(minisafed, coin_a["outpoint"])
    assert coin_a == new_coin_a
    new_coin_b = get_coin(minisafed, coin_b["outpoint"])
    coin_b["spend_info"]["height"] = initial_height
    assert new_coin_b == coin_b
