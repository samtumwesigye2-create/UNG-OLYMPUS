"""Central registry of subsystem adapters by domain."""
from adapters.mercury import MercuryAdapter
from adapters.vector import VectorAdapter

_mercury = MercuryAdapter()
_vector = VectorAdapter()

ADAPTERS_BY_DOMAIN = {
    "defense": [],            # Phase 3
    "emergency": [],          # Phase 4
    "logistics": [_mercury, _vector],  # Phase 1 — live now
    "itinfra": [],            # Phase 2
}

ADAPTERS_BY_SUBSYSTEM = {
    adapter.name: adapter
    for adapters in ADAPTERS_BY_DOMAIN.values()
    for adapter in adapters
}

DOMAIN_LABELS = {
    "defense": "Defense / ISR",
    "emergency": "Emergency / Dispatch",
    "logistics": "Logistics",
    "itinfra": "IT / Infrastructure",
}

DOMAIN_PHASE = {
    "logistics": 1,
    "itinfra": 2,
    "defense": 3,
    "emergency": 4,
}
