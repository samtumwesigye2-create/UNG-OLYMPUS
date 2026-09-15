from adapters.mercury import MercuryAdapter
from adapters.vector import VectorAdapter
_mercury = MercuryAdapter()
_vector = VectorAdapter()
ADAPTERS_BY_DOMAIN = {"defense": [], "emergency": [], "logistics": [_mercury, _vector], "itinfra": []}
ADAPTERS_BY_SUBSYSTEM = {"MERCURY": _mercury, "VECTOR": _vector}
DOMAIN_LABELS = {"defense": "Defense / ISR", "emergency": "Emergency / Dispatch", "logistics": "Logistics", "itinfra": "IT / Infrastructure"}
DOMAIN_PHASE = {"logistics": 1, "itinfra": 2, "defense": 3, "emergency": 4}
