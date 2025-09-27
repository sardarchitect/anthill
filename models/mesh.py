"""Mesh domain models & related computations.

The JSON provided resembles a Three.js export: a top-level list of geometries
each with a `data` dict containing flat `vertices` (x,y,z repeating) and a
`faces` list. The faces list appears to use a simplified pattern where every
face entry is preceded by a `0` flag (bitmask) followed by three vertex indices.
We normalize this into triangle indices. Normals/UVs are ignored for now.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple, Iterable, Optional, Dict
import math


@dataclass(frozen=True)
class Vertex:
	x: float
	y: float
	z: float

	def to_tuple(self) -> Tuple[float, float, float]:
		return (self.x, self.y, self.z)


@dataclass
class MeshGeometry:
	"""A single mesh geometry (triangular).

	Attributes
	----------
	name: Optional human-readable identifier.
	vertices: List of Vertex objects.
	faces: List of tuples of 3 indices referencing `vertices`.
	meta: Arbitrary metadata (e.g., uuid, layer).
	"""

	name: str
	vertices: List[Vertex]
	faces: List[Tuple[int, int, int]]
	meta: Dict[str, str] = field(default_factory=dict)
	embodied_carbon: float | None = None  # kgCO2e (per mesh aggregate)
	structural_type: str = None  # e.g., "Beam", "Floor", etc.

	def vertex_count(self) -> int:
		return len(self.vertices)

	def face_count(self) -> int:
		return len(self.faces)

	def bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
		if not self.vertices:
			return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
		xs = [v.x for v in self.vertices]
		ys = [v.y for v in self.vertices]
		zs = [v.z for v in self.vertices]
		return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

	def bounding_box_volume(self) -> float:
		(minx, miny, minz), (maxx, maxy, maxz) = self.bounds()
		return max(0.0, (maxx - minx) * (maxy - miny) * (maxz - minz))


@dataclass
class MeshScene:
	"""Collection of MeshGeometry objects with scene-level helpers."""

	meshes: List[MeshGeometry]

	def total_vertices(self) -> int:
		return sum(m.vertex_count() for m in self.meshes)

	def total_faces(self) -> int:
		return sum(m.face_count() for m in self.meshes)

	def aggregate_bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
		if not self.meshes:
			return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
		mins = [list(m.bounds()[0]) for m in self.meshes]
		maxs = [list(m.bounds()[1]) for m in self.meshes]
		return (
			(min(m[0] for m in mins), min(m[1] for m in mins), min(m[2] for m in mins)),
			(max(m[0] for m in maxs), max(m[1] for m in maxs), max(m[2] for m in maxs)),
		)

	def summary(self) -> List[Dict[str, float]]:
		rows = []
		for m in self.meshes:
			(minx, miny, minz), (maxx, maxy, maxz) = m.bounds()
			rows.append(
				{
					"name": m.name,
					"vertices": m.vertex_count(),
					"faces": m.face_count(),
					"bbox_volume": m.bounding_box_volume(),
					"min_z": minz,
					"max_z": maxz,
					"embodied_carbon": m.embodied_carbon,
					"structural_type": m.structural_type
				}
			)
		return rows


def flatten_vertices(vertices: Iterable[Vertex]) -> Tuple[List[float], List[float], List[float]]:
	xs, ys, zs = [], [], []
	for v in vertices:
		xs.append(v.x)
		ys.append(v.y)
		zs.append(v.z)
	return xs, ys, zs

