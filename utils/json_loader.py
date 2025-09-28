"""Utilities to parse geometry JSON into domain models."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from models.mesh import Vertex, MeshGeometry, MeshScene, BeamGeometry


class MeshParseError(RuntimeError):
	pass


def load_json(path: Path) -> Dict[str, Any]:
	try:
		with path.open("r", encoding="utf-8") as f:
			return json.load(f)
	except FileNotFoundError as e:
		raise MeshParseError(f"File not found: {path}") from e
	except json.JSONDecodeError as e:
		raise MeshParseError(f"Invalid JSON: {e}") from e


def parse_point_string(point_str: str) -> Vertex:
	"""Parse point string like '{-37, -26, 8.666667}' into Vertex."""
	# Remove braces and split by comma
	clean_str = point_str.strip('{}')
	coords = [float(x.strip()) for x in clean_str.split(',')]
	if len(coords) != 3:
		raise MeshParseError(f"Invalid point format: {point_str}")
	return Vertex(coords[0], coords[1], coords[2])


def parse_structural_frame(data: Dict[str, Any]) -> MeshScene:
	"""Parse the new StructuralFrame format with BeamSystem."""
	beams: List[BeamGeometry] = []
	
	# Check if this is the new format
	structural_frame = data.get("StructuralFrame")
	if structural_frame and "BeamSystem" in structural_frame:
		beam_system = structural_frame["BeamSystem"]
		
		for idx, beam_data in enumerate(beam_system):
			try:
				# Parse start and end points
				start_point = parse_point_string(beam_data["PointStart"])
				end_point = parse_point_string(beam_data["PointEnd"])
				
				# Parse carbon emission (note: JSON uses "CarbonEmmision" - keeping as is)
				carbon_str = beam_data.get("CarbonEmmision")
				carbon_val = float(carbon_str) if carbon_str else None
				
				# Create beam geometry
				beam = BeamGeometry(
					name=f"Beam_{idx:03d}",
					start_point=start_point,
					end_point=end_point,
					embodied_carbon=carbon_val,
					structural_type="Beam"
				)
				beams.append(beam)
				
			except (KeyError, ValueError, TypeError) as e:
				raise MeshParseError(f"Failed to parse beam {idx}: {e}")
	
	return MeshScene(meshes=[], beams=beams)


def parse_scene(data: Dict[str, Any]) -> MeshScene:
	geometries = data.get("geometries", [])
	meshes: List[MeshGeometry] = []

	# Map geometry uuid -> name from object.children
	uuid_name_map: Dict[str, str] = {}
	for child in data.get("object", {}).get("children", []):
		if child.get("type") == "Mesh":
			uuid_name_map[child.get("geometry")] = child.get("name", "mesh")

	for g in geometries:
		uuid = g.get("uuid")
		name = uuid_name_map.get(uuid, uuid or f"mesh_{len(meshes)}")
		dataset = g.get("data") or {}
		raw_vertices = dataset.get("vertices", [])
		raw_faces = dataset.get("faces", [])

		# Convert flat vertex list to Vertex objects
		if len(raw_vertices) % 3 != 0:
			raise MeshParseError(f"Vertex array length not multiple of 3 for {name}")
		vertices = [
			Vertex(raw_vertices[i], raw_vertices[i + 1], raw_vertices[i + 2])
			for i in range(0, len(raw_vertices), 3)
		]

		# Faces pattern appears as: 0, a, b, c repeating. Validate length % 4 == 0.
		faces: List[Tuple[int, int, int]] = []
		if raw_faces:
			if len(raw_faces) % 4 != 0:
				raise MeshParseError(f"Faces array length not multiple of 4 for {name}")
			for i in range(0, len(raw_faces), 4):
				flag = raw_faces[i]
				a, b, c = raw_faces[i + 1 : i + 4]
				if flag != 0:
					# Future: handle bitmask flags; for now we only accept 0.
					raise MeshParseError(f"Unsupported face flag {flag} in {name}")
				faces.append((a, b, c))

		carbon = dataset.get("embodiedCarbon")
		try:
			carbon_val = float(carbon) if carbon is not None else None
		except (TypeError, ValueError):
			carbon_val = None
		
		try:
			structuralType = str(dataset.get("structural_type")) if dataset.get("structural_type") is not None else None
		except (TypeError, ValueError):
			structuralType = None

		meshes.append(
			MeshGeometry(
				name=name,
				vertices=vertices,
				faces=faces,
				meta={"uuid": uuid or "", "vertex_count": str(len(vertices))},
				embodied_carbon=carbon_val,
				structural_type=structuralType
			)
		)

	return MeshScene(meshes=meshes)


def load_scene(path: Path) -> MeshScene:
	"""Load scene from JSON, auto-detecting format."""
	data = load_json(path)
	
	# Check if it's the new StructuralFrame format
	if "StructuralFrame" in data:
		return parse_structural_frame(data)
	else:
		# Fall back to old Three.js format
		return parse_scene(data)

