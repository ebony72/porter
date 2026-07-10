"""Hardware model: cores, inter-core ports, cached distance structures."""

from __future__ import annotations

from dataclasses import dataclass
from collections import deque
from typing import Dict, List, Tuple, Optional, Set, Iterable
import math

LogicalQubit = int
PhysicalQubit = int
CoreId = int
GateId = int
Edge = Tuple[int, int]


def canonical_edge(a: int, b: int) -> Tuple[int, int]:
    return (a, b) if a <= b else (b, a)


def bfs_distances(adj: Dict[int, Iterable[int]], src: int) -> Dict[int, int]:
    dist = {src: 0}
    q = deque([src])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in dist:
                dist[v] = dist[u] + 1
                q.append(v)
    return dist




@dataclass
class Core:
    cid: CoreId
    physical_qubits: Tuple[PhysicalQubit, ...]
    coupling_edges: Tuple[Edge, ...]
    ports: Dict[CoreId, PhysicalQubit]
    capacity: Optional[int] = None

    def __post_init__(self):
        self.physical_qubits = tuple(self.physical_qubits)
        self.coupling_edges = tuple(canonical_edge(*e) for e in self.coupling_edges)
        if self.capacity is None:
            self.capacity = len(self.physical_qubits)

    def local_adjacency(self) -> Dict[PhysicalQubit, Set[PhysicalQubit]]:
        """Return only intra-core coupling adjacency.

        Inter-core communication edges should not be treated as ordinary local
        SWAP/CX edges.  The hardware model stores inter-core connectivity
        separately through Hardware.core_edges and Core.ports.
        """
        local_set = set(self.physical_qubits)
        adj: Dict[PhysicalQubit, Set[PhysicalQubit]] = {p: set() for p in self.physical_qubits}
        for a, b in self.coupling_edges:
            if a in local_set and b in local_set:
                adj[a].add(b)
                adj[b].add(a)
        return adj


@dataclass
class Hardware:
    cores: Dict[CoreId, Core]
    core_edges: Tuple[Tuple[CoreId, CoreId], ...]

    def __post_init__(self):
        self.core_edges = tuple(canonical_edge(*e) for e in self.core_edges)
        self._core_adj: Dict[CoreId, Set[CoreId]] = {cid: set() for cid in self.cores}
        for a, b in self.core_edges:
            self._core_adj[a].add(b)
            self._core_adj[b].add(a)

        self.phys_to_core: Dict[PhysicalQubit, CoreId] = {}
        self.communication_qubits: Set[PhysicalQubit] = set()
        for cid, core in self.cores.items():
            for p in core.physical_qubits:
                if p in self.phys_to_core:
                    raise ValueError(f"Physical qubit {p} appears in more than one core")
                self.phys_to_core[p] = cid
            self.communication_qubits.update(core.ports.values())

        self._local_adj_by_core = {cid: core.local_adjacency() for cid, core in self.cores.items()}
        self._local_dist: Dict[Tuple[CoreId, PhysicalQubit, PhysicalQubit], int] = {}
        for cid, core in self.cores.items():
            for src in core.physical_qubits:
                dist = bfs_distances(self._local_adj_by_core[cid], src)
                for dst in core.physical_qubits:
                    self._local_dist[(cid, src, dst)] = dist.get(dst, math.inf)

        self._core_dist: Dict[CoreId, Dict[CoreId, int]] = {
            cid: bfs_distances(self._core_adj, cid) for cid in self.cores
        }
        self._core_neighbors_sorted: Dict[CoreId, List[CoreId]] = {
            cid: sorted(neighbors) for cid, neighbors in self._core_adj.items()
        }
        self._local_neighbors_sorted: Dict[PhysicalQubit, List[PhysicalQubit]] = {}
        for cid, adj in self._local_adj_by_core.items():
            for p, neighbors in adj.items():
                self._local_neighbors_sorted[p] = sorted(
                    n for n in neighbors if self.phys_to_core[n] == cid
                )

    def are_adjacent_cores(self, a: CoreId, b: CoreId) -> bool:
        return canonical_edge(a, b) in self.core_edges

    def core_neighbors(self, c: CoreId) -> List[CoreId]:
        # Cached; treat the returned list as read-only.
        return self._core_neighbors_sorted[c]

    def core_distance(self, a: CoreId, b: CoreId) -> int:
        if a == b:
            return 0
        return int(self._core_dist[a].get(b, math.inf))


    def inter_core_ports(self, a: CoreId, b: CoreId) -> Tuple[PhysicalQubit, PhysicalQubit]:
        if not self.are_adjacent_cores(a, b):
            raise ValueError(f"Cores {a} and {b} are not adjacent")
        pa = self.cores[a].ports.get(b)
        pb = self.cores[b].ports.get(a)
        if pa is None or pb is None:
            raise ValueError(f"Missing port annotation for core edge {a}-{b}")
        return pa, pb

    def local_distance(self, cid: CoreId, a: PhysicalQubit, b: PhysicalQubit) -> int:
        # Finite distances are ints; unreachable/foreign pairs yield math.inf.
        # (int(math.inf) would raise OverflowError, so no int() wrapper here.)
        return self._local_dist.get((cid, a, b), math.inf)

    def local_neighbors(self, p: PhysicalQubit) -> List[PhysicalQubit]:
        # Cached; treat the returned list as read-only.
        return self._local_neighbors_sorted[p]


