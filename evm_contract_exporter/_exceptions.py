
from web3.exceptions import ContractLogicError


_value_err_reverts = ["No data was returned - the call likely reverted", "Call reverted: Integer overflow"]

def _is_revert(e: Exception) -> bool:
    if isinstance(e, ContractLogicError):
        return True
    return isinstance(e, ValueError) and str(e) in _value_err_reverts
    
class FixMe(Exception):
    """A base class for known bugs that must be fixed"""
    ...