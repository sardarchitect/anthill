"""Mesh domain models & related computations.

The JSON provided resembles a Three.js export: a top-level list of geometries
each with a `data` dict containing flat `vertices` (x,y,z repeating) and a
`faces` list. The faces list appears to use a simplified pattern where every
face entry is preceded by a `0` flag (bitmask) followed by three vertex indices.
We normalize this into triangle indices. Normals/UVs are ignored for now.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple, Iterable, Optional, Dict, Any
import math


@dataclass(frozen=True)
class Vertex:
	x: float
	y: float
	z: float

	def to_tuple(self) -> Tuple[float, float, float]:
		return (self.x, self.y, self.z)


@dataclass
class BeamGeometry:
	"""A structural beam defined by start and end points.

	Attributes
	----------
	name: Optional human-readable identifier.
	start_point: Starting vertex of the beam.
	end_point: Ending vertex of the beam.
	embodied_carbon: Carbon emission value (kgCO2e).
	meta: Arbitrary metadata.
	"""

	name: str
	start_point: Vertex
	end_point: Vertex
	embodied_carbon: float | None = None  # kgCO2e
	structural_type: str = "Beam"
	meta: Dict[str, str] = field(default_factory=dict)

	def length(self) -> float:
		"""Calculate the length of the beam."""
		dx = self.end_point.x - self.start_point.x
		dy = self.end_point.y - self.start_point.y
		dz = self.end_point.z - self.start_point.z
		return math.sqrt(dx*dx + dy*dy + dz*dz)


# Alias for readability when using BeamGeometry to represent columns
ColumnGeometry = BeamGeometry


@dataclass
class SlabGeometry:
	"""Planar slab/floor geometry defined by corner vertices."""

	name: str
	corners: List[Vertex]
	embodied_carbon: float | None = None
	structural_type: str = "Floor"
	meta: Dict[str, str] = field(default_factory=dict)

	def area(self) -> float:
		"""Calculate polygon area using fan triangulation."""
		if len(self.corners) < 3:
			return 0.0
		area = 0.0
		p0 = self.corners[0]
		for i in range(1, len(self.corners) - 1):
			p1 = self.corners[i]
			p2 = self.corners[i + 1]
			area += _triangle_area(p0, p1, p2)
		return area

	def bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
		if not self.corners:
			return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
		xs = [v.x for v in self.corners]
		ys = [v.y for v in self.corners]
		zs = [v.z for v in self.corners]
		return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

	def centroid(self) -> Tuple[float, float, float]:
		if not self.corners:
			return (0.0, 0.0, 0.0)
		n = len(self.corners)
		x = sum(v.x for v in self.corners) / n
		y = sum(v.y for v in self.corners) / n
		z = sum(v.z for v in self.corners) / n
		return (x, y, z)


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
	"""Collection of scene geometries with helpers for analytics and rendering."""

	meshes: List[MeshGeometry] = field(default_factory=list)
	beams: List[BeamGeometry] = field(default_factory=list)
	columns: List[BeamGeometry] = field(default_factory=list)
	slabs: List[SlabGeometry] = field(default_factory=list)
	metadata: Dict[str, Any] = field(default_factory=dict)

	def total_vertices(self) -> int:
		mesh_vertices = sum(m.vertex_count() for m in self.meshes)
		line_vertices = len(self.beams) * 2 + len(self.columns) * 2
		slab_vertices = len(self.slabs) * 4  # assuming quads
		return mesh_vertices + line_vertices + slab_vertices

	def total_faces(self) -> int:
		mesh_faces = sum(m.face_count() for m in self.meshes)
		slab_faces = len(self.slabs) * 2  # triangles per quad
		return mesh_faces + slab_faces

	def aggregate_bounds(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
		points: List[Tuple[float, float, float]] = []
		for mesh in self.meshes:
			points.extend(v.to_tuple() for v in mesh.vertices)
		for beam in self.beams:
			points.append(beam.start_point.to_tuple())
			points.append(beam.end_point.to_tuple())
		for column in self.columns:
			points.append(column.start_point.to_tuple())
			points.append(column.end_point.to_tuple())
		for slab in self.slabs:
			points.extend(v.to_tuple() for v in slab.corners)
		if not points:
			return (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)
		xs, ys, zs = zip(*points)
		return (min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs))

	def summary(self) -> List[Dict[str, float]]:
		rows = []
		
		# Add mesh geometries
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
		
		# Add beam geometries
		for b in self.beams:
			min_z = min(b.start_point.z, b.end_point.z)
			max_z = max(b.start_point.z, b.end_point.z)
			rows.append(
				{
					"name": b.name,
					"vertices": 2,  # Start and end points
					"faces": 0,     # Beams don't have faces
					"bbox_volume": 0,  # Line has no volume
					"length": b.length(),
					"min_z": min_z,
					"max_z": max_z,
					"embodied_carbon": b.embodied_carbon,
					"structural_type": b.structural_type
				}
			)

		# Add columns (as linear elements)
		for c in self.columns:
			min_z = min(c.start_point.z, c.end_point.z)
			max_z = max(c.start_point.z, c.end_point.z)
			rows.append(
				{
					"name": c.name,
					"vertices": 2,
					"faces": 0,
					"bbox_volume": 0,
					"length": c.length(),
					"min_z": min_z,
					"max_z": max_z,
					"embodied_carbon": c.embodied_carbon,
					"structural_type": c.structural_type
				}
			)

		# Add slabs/floors
		for slab in self.slabs:
			(minx, miny, minz), (maxx, maxy, maxz) = slab.bounds()
			rows.append(
				{
					"name": slab.name,
					"vertices": len(slab.corners),
					"faces": 2,  # Represented as quad (two triangles)
					"bbox_volume": (maxx - minx) * (maxy - miny) * (maxz - minz) if maxz > minz else 0,
					"area": slab.area(),
					"min_z": minz,
					"max_z": maxz,
					"embodied_carbon": slab.embodied_carbon,
					"structural_type": slab.structural_type
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


def _triangle_area(a: Vertex, b: Vertex, c: Vertex) -> float:
	ab = (b.x - a.x, b.y - a.y, b.z - a.z)
	ac = (c.x - a.x, c.y - a.y, c.z - a.z)
	cross_x = ab[1] * ac[2] - ab[2] * ac[1]
	cross_y = ab[2] * ac[0] - ab[0] * ac[2]
	cross_z = ab[0] * ac[1] - ab[1] * ac[0]
	return 0.5 * math.sqrt(cross_x**2 + cross_y**2 + cross_z**2)

