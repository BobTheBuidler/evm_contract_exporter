
import logging
from typing import List

from brownie import chain
from y import Network

logger = logging.getLogger(__name__)

try:
    import tokenlists
    class TokenList(tokenlists.TokenList):
        def __getitem__(self, token_symbol: str) -> tokenlists.TokenInfo:
            for token in self.tokens:
                if token.symbol == token_symbol:
                    return token
            raise KeyError(token_symbol)
    class TokenListManager(tokenlists.TokenListManager):
        def __getitem__(self, token_symbol: str) -> tokenlists.TokenInfo:
            for tokenlist in self.available_tokenlists():
                try:
                    return tokenlist[token_symbol]
                except KeyError:
                    pass
            raise KeyError(token_symbol)
        def available_tokenlists(self) -> List[str]:
            self.__preinstall_tokenlists()
            return super().available_tokenlists()
        def get_tokens_for_chain(self, name: str, chainid: Network = chain.id) -> List[tokenlists.TokenInfo]:
            tokenlist = self.get_tokenlist(name)
            tokens = [token for token in tokenlist.tokens if token.chainId == chainid]
            logger.info("contains %s tokens, %s for %s", len(tokenlist.tokens), len(tokens), Network(chain.id))
            return tokens
        def get_all_tokens_for_chain(self, chainid: Network = chain.id) -> List[tokenlists.TokenInfo]:
            all_tokens = []
            for name in self.available_tokenlists():
                for tokens in self.get_tokens_for_chain(name, chainid=chainid):
                    for token_info in tokens:
                        if not any(token_info.address == info.address for info in all_tokens):
                            all_tokens.append(token_info)
            return all_tokens
        def __preinstall_tokenlists(self) -> None:
            for uri in TOKENLISTS.values():
                self.install_tokenlist(uri)

except ImportError:
    class TokenListManager:
        def __init__(self) -> None:
            raise ImportError("Cannot find library `tokenlists`. You must `pip install tokenlists` before you can use this functionality.")

TOKENLISTS = {
    "1inch": "tokens.1inch.eth",
    "Aave Token List": "tokenlist.aave.eth",
    "CMC200 ERC20": "erc20.cmc.eth",
    "CMC DeFi": "defi.cmc.eth",
    "CMC Stablecoin": "stablecoin.cmc.eth",
    "Coingecko": "https://tokens.coingecko.com/uniswap/all.json",
    "Compound": "https://raw.githubusercontent.com/compound-finance/token-list/master/compound.tokenlist.json",
    "Gemini Token List": "https://www.gemini.com/uniswap/manifest.json",
}