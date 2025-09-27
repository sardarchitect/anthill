"""Utilities to parse Three.js-style geometry JSON into domain models."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from models.mesh import Vertex, MeshGeometry, MeshScene


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
	return parse_scene(load_json(path))

