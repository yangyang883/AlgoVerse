from app.schemas.models import AlgorithmCapability

CAPABILITIES = [
    AlgorithmCapability(name="bubble_sort", level="L4", executable=True, visualizable=True, max_input_size=2000),
    AlgorithmCapability(name="insertion_sort", level="L2", executable=False, visualizable=False, max_input_size=0),
    AlgorithmCapability(name="quick_sort", level="L2", executable=False, visualizable=False, max_input_size=0),
    AlgorithmCapability(name="merge_sort", level="L2", executable=False, visualizable=False, max_input_size=0),
]
