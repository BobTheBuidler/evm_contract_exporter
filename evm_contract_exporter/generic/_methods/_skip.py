SKIP_METHODS = {
    "decimals",
    "eip712Domain",
    "metadata",
    "MAX_UINT",
    "UINT_MAX_VALUE",
    # these numbers are either too big to stuff into the default db or wont scale properly (or both).
    # You can manually do things with these if you need
    "getReserves", 
    "reserve0",
    "reserve1",
    "price0CumulativeLast",
    "price1CumulativeLast",
    "kLast",
    "currentCumulativePrices",
    "reserve0CumulativeLast",
    "reserve1CumulativeLast",
    "lastObservation",
    "DELEGATE_PROTOCOL_SWAP_FEES_SENTINEL",
}