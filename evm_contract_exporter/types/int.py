
class _int(int):
    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({super().__repr__()})"
    
class int8(_int):
    ...

class int16(_int):
    ...

class int24(_int):
    ...

class int32(_int):
    ...

class int48(_int):
    ...

class int64(_int):
    ...

class int96(_int):
    ...

class int104(_int):
    ...

class int112(_int):
    ...

class int128(_int):
    ...

class int192(_int):
    ...

class int256(_int):
    ...
