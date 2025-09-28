"""Utilities to parse geometry JSON into domain models."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

from models.mesh import (
	Vertex,
	MeshGeometry,
	MeshScene,
	BeamGeometry,
	SlabGeometry,
)


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


def _parse_carbon(value: Any) -> float | None:
	if value is None:
		return None
	try:
		return float(value)
	except (TypeError, ValueError):
		return None


def _extract_system_payload(system_data: Any) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
	"""Normalize system payload containing element list plus metadata."""
	elements: List[Dict[str, Any]] = []
	meta: Dict[str, Any] = {}
	if isinstance(system_data, list):
		for item in system_data:
			if isinstance(item, list):
				elements.extend([elem for elem in item if isinstance(elem, dict)])
			elif isinstance(item, dict):
				meta.update(item)
	elif isinstance(system_data, dict):
		elements_payload = system_data.get("elements")
		if isinstance(elements_payload, list):
			elements.extend([elem for elem in elements_payload if isinstance(elem, dict)])
		meta.update({k: v for k, v in system_data.items() if k != "elements"})
	return elements, meta


def _merge_metadata(target: Dict[str, Any], source: Dict[str, Any]) -> None:
	for key, value in source.items():
		if isinstance(value, (int, float)):
			target[key] = value
		elif isinstance(value, str) and key.lower().endswith("co2"):
			target[key] = _parse_carbon(value)
		else:
			target[key] = value


def _parse_linear_elements(
	system_data: Any,
	element_prefix: str,
	structural_type: str,
	start_key: str = "PointStart",
	end_key: str = "PointEnd",
) -> Tuple[List[BeamGeometry], Dict[str, Any]]:
	elements_payload, meta = _extract_system_payload(system_data)
	linear_elements: List[BeamGeometry] = []
	for idx, elem in enumerate(elements_payload):
		try:
			start_raw = elem.get(start_key)
			end_raw = elem.get(end_key)
			if start_raw is None or end_raw is None:
				raise MeshParseError(f"Missing start/end point in element {idx}")
			start_point = parse_point_string(start_raw)
			end_point = parse_point_string(end_raw)
			carbon_val = _parse_carbon(elem.get("CarbonEmission") or elem.get("CarbonEmmision"))
			linear_elements.append(
				BeamGeometry(
					name=f"{element_prefix}_{idx:03d}",
					start_point=start_point,
					end_point=end_point,
					embodied_carbon=carbon_val,
					structural_type=structural_type,
					meta={k: str(v) for k, v in elem.items() if k not in {start_key, end_key, "CarbonEmission", "CarbonEmmision"}}
				)
			)
		except (ValueError, TypeError) as e:
			raise MeshParseError(f"Failed to parse {structural_type.lower()} {idx}: {e}")
	return linear_elements, meta


def _parse_slab_system(system_data: Any, element_prefix: str = "Slab") -> Tuple[List[SlabGeometry], Dict[str, Any]]:
	elements_payload, meta = _extract_system_payload(system_data)
	slabs: List[SlabGeometry] = []
	for idx, elem in enumerate(elements_payload):
		corner_keys = [k for k in elem.keys() if k.lower().startswith("point")]
		if not corner_keys:
			raise MeshParseError(f"Slab {idx} missing corner points")
		# Sort corners by numeric suffix to preserve order (Point1, Point2, ...)
		corner_keys.sort(key=lambda k: int(''.join(filter(str.isdigit, k)) or 0))
		corners = [parse_point_string(elem[k]) for k in corner_keys]
		carbon_val = _parse_carbon(elem.get("CarbonEmission") or elem.get("CarbonEmmision"))
		slabs.append(
			SlabGeometry(
				name=f"{element_prefix}_{idx:03d}",
				corners=corners,
				embodied_carbon=carbon_val,
				structural_type="Floor",
				meta={k: str(v) for k, v in elem.items() if k not in corner_keys + ["CarbonEmission", "CarbonEmmision"]}
			)
		)
	return slabs, meta


def parse_structural_frame(data: Dict[str, Any]) -> MeshScene:
	"""Parse StructuralFrame payloads (beams, columns, slabs)."""
	structural_frame = data.get("StructuralFrame")
	if structural_frame is None:
		return MeshScene()

	beams: List[BeamGeometry] = []
	columns: List[BeamGeometry] = []
	slabs: List[SlabGeometry] = []
	metadata: Dict[str, Any] = {}

	# Support both dict and list variants
	if isinstance(structural_frame, dict):
		if "BeamSystem" in structural_frame:
			parsed_beams, beam_meta = _parse_linear_elements(structural_frame["BeamSystem"], "Beam", "Beam")
			beams.extend(parsed_beams)
			_merge_metadata(metadata, beam_meta)
		if "ColumnSystem" in structural_frame:
			parsed_columns, column_meta = _parse_linear_elements(structural_frame["ColumnSystem"], "Column", "Column")
			columns.extend(parsed_columns)
			_merge_metadata(metadata, column_meta)
		if "SlabSystem" in structural_frame:
			parsed_slabs, slab_meta = _parse_slab_system(structural_frame["SlabSystem"], element_prefix="Floor")
			slabs.extend(parsed_slabs)
			_merge_metadata(metadata, slab_meta)
	else:
		for entry in structural_frame:
			if not isinstance(entry, dict):
				continue
			if "BeamSystem" in entry:
				parsed_beams, beam_meta = _parse_linear_elements(entry["BeamSystem"], "Beam", "Beam")
				beams.extend(parsed_beams)
				_merge_metadata(metadata, beam_meta)
			if "ColumnSystem" in entry:
				parsed_columns, column_meta = _parse_linear_elements(entry["ColumnSystem"], "Column", "Column")
				columns.extend(parsed_columns)
				_merge_metadata(metadata, column_meta)
			if "SlabSystem" in entry:
				parsed_slabs, slab_meta = _parse_slab_system(entry["SlabSystem"], element_prefix="Floor")
				slabs.extend(parsed_slabs)
				_merge_metadata(metadata, slab_meta)
			if "TotalCO2" in entry:
				metadata["totalCO2"] = _parse_carbon(entry.get("TotalCO2"))

	return MeshScene(meshes=[], beams=beams, columns=columns, slabs=slabs, metadata=metadata)


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

