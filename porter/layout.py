"""Logical-to-physical layout with O(1) per-core occupancy tracking."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from .hardware import CoreId, Hardware, LogicalQubit, PhysicalQubit


@dataclass
class Layout:
    logical_to_physical: Dict[LogicalQubit, PhysicalQubit]
    logical_to_core: Dict[LogicalQubit, CoreId]
    physical_to_logical: Dict[PhysicalQubit, LogicalQubit]
    num_logical: int

    def clone(self) -> "Layout":
        cloned = Layout(
            logical_to_physical=dict(self.logical_to_physical),
            logical_to_core=dict(self.logical_to_core),
            physical_to_logical=dict(self.physical_to_logical),
            num_logical=self.num_logical,
        )
        occupancy = getattr(self, "_occupancy_cache", None)
        if occupancy is not None:
            cloned._occupancy_cache = dict(occupancy)
        return cloned

    def _core_occupancy(self) -> Dict[CoreId, int]:
        """Count of real logical qubits per core, kept in sync by the two
        mutation entry points (``move_logical_to_physical`` keeps it updated;
        ``swap_physical`` never changes core membership)."""
        occupancy = getattr(self, "_occupancy_cache", None)
        if occupancy is None:
            occupancy = {}
            for q, cid in self.logical_to_core.items():
                if q < self.num_logical:
                    occupancy[cid] = occupancy.get(cid, 0) + 1
            self._occupancy_cache = occupancy
        return occupancy

    def is_real_logical(self, q: LogicalQubit) -> bool:
        return q < self.num_logical

    def core_of(self, q: LogicalQubit) -> CoreId:
        if not self.is_real_logical(q):
            raise ValueError(f"Dummy virtual q{q} has no logical core")
        return self.logical_to_core[q]

    def phys_of(self, q: LogicalQubit) -> PhysicalQubit:
        if not self.is_real_logical(q):
            raise ValueError(f"Dummy virtual q{q} has no logical physical position")
        return self.logical_to_physical[q]


    def is_phys_free(self, p: PhysicalQubit) -> bool:
        q = self.physical_to_logical.get(p)
        return q is None or q >= self.num_logical

    def logicals_in_core(self, cid: CoreId) -> List[LogicalQubit]:
        return sorted(q for q, c in self.logical_to_core.items() if c == cid)

    def free_physical_qubits(self, hw: Hardware, cid: CoreId) -> List[PhysicalQubit]:
        return [p for p in hw.cores[cid].physical_qubits if self.is_phys_free(p)]

    def free_count(self, hw: Hardware, cid: CoreId) -> int:
        return len(hw.cores[cid].physical_qubits) - self._core_occupancy().get(cid, 0)

    def move_logical_to_physical(self, q: LogicalQubit, dst_phys: PhysicalQubit, dst_core: CoreId) -> None:
        if not self.is_real_logical(q):
            raise ValueError(f"Cannot move dummy virtual q{q}")

        if not self.is_phys_free(dst_phys):
            raise ValueError(f"Destination physical qubit {dst_phys} is occupied")

        src_phys = self.logical_to_physical[q]

        # In dummy representation, dst_phys contains a dummy virtual id.
        # After moving q into dst_phys, the source position should contain that dummy id.
        dst_dummy = self.physical_to_logical.get(dst_phys)
        if dst_dummy is None:
            dst_dummy = self._fresh_dummy_id()

        self.physical_to_logical[src_phys] = dst_dummy
        self.physical_to_logical[dst_phys] = q

        occupancy = getattr(self, "_occupancy_cache", None)
        if occupancy is not None:
            src_core = self.logical_to_core[q]
            occupancy[src_core] = occupancy.get(src_core, 0) - 1
            occupancy[dst_core] = occupancy.get(dst_core, 0) + 1

        self.logical_to_physical[q] = dst_phys
        self.logical_to_core[q] = dst_core

    def swap_physical(self, hw: Hardware, p0: PhysicalQubit, p1: PhysicalQubit) -> None:
        c0 = hw.phys_to_core[p0]
        c1 = hw.phys_to_core[p1]
        if c0 != c1:
            raise ValueError("This router only uses local physical SWAPs inside one core")

        q0 = self.physical_to_logical.get(p0)
        q1 = self.physical_to_logical.get(p1)

        if q0 is None:
            q0 = self._fresh_dummy_id()
        if q1 is None:
            q1 = self._fresh_dummy_id(exclude={q0})

        self.physical_to_logical[p0], self.physical_to_logical[p1] = q1, q0

        if q0 < self.num_logical:
            self.logical_to_physical[q0] = p1
            self.logical_to_core[q0] = c1

        if q1 < self.num_logical:
            self.logical_to_physical[q1] = p0
            self.logical_to_core[q1] = c0

    def _fresh_dummy_id(self, exclude: Optional[Set[LogicalQubit]] = None) -> LogicalQubit:
        exclude = exclude or set()
        used = set(self.physical_to_logical.values()) | exclude
        candidate = self.num_logical
        while candidate in used:
            candidate += 1
        return candidate

    @classmethod
    def from_telesabre_phys_to_virt(
        cls,
        hw: Hardware,
        phys_to_virt: List[int],
        num_logical: int,
    ) -> "Layout":
        """Build Layout from TeleSABRE's full phys_to_virt permutation.

        TeleSABRE represents every physical position with a virtual id.
        Real logical qubits satisfy v < num_logical; dummy virtual qubits
        satisfy v >= num_logical and represent free physical positions.
        """
        if len(phys_to_virt) != len(hw.phys_to_core):
            raise ValueError(
                f"phys_to_virt has length {len(phys_to_virt)}, but hardware has {len(hw.phys_to_core)} physical qubits"
            )
        expected_phys = set(hw.phys_to_core.keys())
        if expected_phys != set(range(len(phys_to_virt))):
            raise ValueError(
                "from_telesabre_phys_to_virt expects contiguous physical ids 0..num_qubits-1, "
                "matching TeleSABRE's array representation"
            )
        if len(set(map(int, phys_to_virt))) != len(phys_to_virt):
            raise ValueError("TeleSABRE phys_to_virt should be a one-to-one permutation, but duplicates were found")

        physical_to_logical: Dict[PhysicalQubit, LogicalQubit] = {
            p: int(v) for p, v in enumerate(phys_to_virt)
        }

        logical_to_physical: Dict[LogicalQubit, PhysicalQubit] = {}
        logical_to_core: Dict[LogicalQubit, CoreId] = {}

        for p, v in physical_to_logical.items():
            if v < num_logical:
                logical_to_physical[v] = p
                logical_to_core[v] = hw.phys_to_core[p]

        missing = sorted(set(range(num_logical)) - set(logical_to_physical))
        if missing:
            raise ValueError(f"Missing real logical qubits in phys_to_virt: {missing}")

        return cls(
            logical_to_physical=logical_to_physical,
            logical_to_core=logical_to_core,
            physical_to_logical=physical_to_logical,
            num_logical=num_logical,
        )


