"""OASIS adapter — placeholder for future OASIS integration."""


class OasisPropagationAdapter:
    """Reserved adapter for future OASIS integration.

    Current implementation intentionally delegates to lightweight propagation
    runtime because existing SimulationRunner is subprocess/log/IPC oriented and
    does not expose a stable in-process propagation API.
    """

    def is_available(self) -> bool:
        return False

    def run(self, *args, **kwargs):
        raise NotImplementedError(
            "OASIS propagation adapter is reserved for a later integration round. "
            "Use lightweight propagation simulator for now."
        )
