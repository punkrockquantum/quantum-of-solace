"""A minimal, backend-agnostic quantum circuit intermediate representation.

The IR is deliberately small: enough to express the parameterized ansatz
circuits used by the hybrid algorithms (QAOA, VQE), and simple enough for
every backend adapter (statevector simulator, CUDA-Q, hardware drivers,
cloud SDKs) to translate into its native format.
"""

from __future__ import annotations

from dataclasses import dataclass, field


#: Gates with no parameters, keyed by name.
FIXED_GATES = {"h", "x", "y", "z", "s", "sdg", "t", "cx", "cz", "swap"}
#: Gates taking a single rotation angle (radians).
ROTATION_GATES = {"rx", "ry", "rz", "rzz"}


@dataclass(frozen=True)
class Gate:
    """A single gate application.

    ``name``    lowercase gate name (see FIXED_GATES / ROTATION_GATES)
    ``qubits``  target qubit indices (control first for two-qubit gates)
    ``params``  rotation angles in radians, if any
    """

    name: str
    qubits: tuple[int, ...]
    params: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if self.name in FIXED_GATES:
            if self.params:
                raise ValueError(f"gate '{self.name}' takes no parameters")
        elif self.name in ROTATION_GATES:
            if len(self.params) != 1:
                raise ValueError(f"gate '{self.name}' takes exactly one angle")
        else:
            raise ValueError(f"unknown gate '{self.name}'")


@dataclass
class Circuit:
    """An ordered list of gates acting on ``num_qubits`` qubits.

    Measurement is implicit: backends measure all qubits in the
    computational basis at the end of the circuit.
    """

    num_qubits: int
    gates: list[Gate] = field(default_factory=list)

    def _add(self, name: str, qubits: tuple[int, ...], params: tuple[float, ...] = ()) -> "Circuit":
        for q in qubits:
            if not 0 <= q < self.num_qubits:
                raise ValueError(f"qubit index {q} out of range for {self.num_qubits}-qubit circuit")
        if len(set(qubits)) != len(qubits):
            raise ValueError(f"duplicate qubit indices in {qubits}")
        self.gates.append(Gate(name, qubits, params))
        return self

    # --- single-qubit gates ---
    def h(self, q: int) -> "Circuit":
        return self._add("h", (q,))

    def x(self, q: int) -> "Circuit":
        return self._add("x", (q,))

    def y(self, q: int) -> "Circuit":
        return self._add("y", (q,))

    def z(self, q: int) -> "Circuit":
        return self._add("z", (q,))

    def rx(self, theta: float, q: int) -> "Circuit":
        return self._add("rx", (q,), (float(theta),))

    def ry(self, theta: float, q: int) -> "Circuit":
        return self._add("ry", (q,), (float(theta),))

    def rz(self, theta: float, q: int) -> "Circuit":
        return self._add("rz", (q,), (float(theta),))

    # --- two-qubit gates ---
    def cx(self, control: int, target: int) -> "Circuit":
        return self._add("cx", (control, target))

    def cz(self, a: int, b: int) -> "Circuit":
        return self._add("cz", (a, b))

    def rzz(self, theta: float, a: int, b: int) -> "Circuit":
        """exp(-i * theta/2 * Z_a Z_b) — the QAOA cost-layer primitive."""
        return self._add("rzz", (a, b), (float(theta),))

    @property
    def depth_ops(self) -> int:
        """Total gate count (a simple complexity proxy)."""
        return len(self.gates)

    def to_dict(self) -> dict:
        return {
            "num_qubits": self.num_qubits,
            "gates": [
                {"name": g.name, "qubits": list(g.qubits), "params": list(g.params)}
                for g in self.gates
            ],
        }
