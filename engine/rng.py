from __future__ import annotations
from dataclasses import dataclass
from typing import Any, List, Sequence, Tuple
import hashlib
import random


@dataclass
class RNG:
    """
    RNG determinista con log opcional de draws.
    Requisito central para simulaciones reproducibles.
    """
    seed: int
    _r: random.Random = None
    log: List[Tuple[str, Any]] = None
    last_king_d6: int = None  # Track last d6 generated for KING_ENDROUND
    last_king_d4: int = None  # Track last d4 generated for KING_ENDROUND

    def __post_init__(self) -> None:
        self._r = random.Random(self.seed)
        self.log = []

    def randint(self, a: int, b: int) -> int:
        x = self._r.randint(a, b)
        self.log.append(("randint", (a, b, x)))
        return x

    def choice(self, seq: Sequence[Any]) -> Any:
        if not seq:
            raise ValueError("choice() on empty sequence")
        x = self._r.choice(list(seq))
        self.log.append(("choice", (len(seq), x)))
        return x

    def shuffle(self, seq: List[Any]) -> None:
        self._r.shuffle(seq)
        self.log.append(("shuffle", len(seq)))

    def sample(self, population: Sequence[Any], k: int) -> List[Any]:
        """Muestrea k elementos de la población sin reemplazo."""
        if not population:
            raise ValueError("sample() on empty population")
        result = self._r.sample(list(population), k)
        self.log.append(("sample", (len(population), k, result)))
        return result

    def fork(self, tag: str) -> "RNG":
        """
        Deriva un nuevo RNG a partir de (seed, tag).
        Útil para mantener reproducibilidad en sub-procesos/rollouts.
        """
        h = hashlib.blake2b(digest_size=8)
        h.update(str(self.seed).encode("utf-8"))
        h.update(b"|")
        h.update(tag.encode("utf-8"))
        derived = int.from_bytes(h.digest(), byteorder="big", signed=False)
        return RNG(derived)
