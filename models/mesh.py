"""Mesh domain models & related computations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple, Iterable, Optional, Dict, Any
import math
import json


@dataclass(frozen=True)
class Vertex:
    x: float
    y: float
    z: float

    def to_tuple(self) -> Tuple[float, float, float]:
        return (self.x, self.y, self.z)


@dataclass
class BeamGeometry:
    """A structural beam defined by start and end points."""
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
    """A single mesh geometry (triangular)."""
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

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MeshScene':
        """Create a MeshScene instance from a dictionary."""
        print("Creating MeshScene from data:")
        print(json.dumps(data, indent=2))
        
        scene = cls()

        def parse_point(point_str):
            """Helper to parse point string into coordinates"""
            cleaned = str(point_str).strip("{}").replace(" ", "")
            return [float(x) for x in cleaned.split(",")]

        def process_structural_elements(system_data, element_type):
            """Generic processor for structural elements (beams/columns/slabs)"""
            print(f"\nProcessing {element_type} elements...")
            print(f"Input system_data type: {type(system_data)}")
            if isinstance(system_data, (list, dict)):
                print(f"System data content: {json.dumps(system_data, indent=2)}")
            
            elements = []
            # For slabs and columns, handle nested array structures
            if element_type in ["Slab", "Column"] and isinstance(system_data, list):
                print(f"Processing {element_type} with system_data: {json.dumps(system_data, indent=2)}")
                for item in system_data:
                    if isinstance(item, list):
                        if element_type == "Column":
                            # Look for column elements with PointStart/PointEnd
                            for col in item:
                                if isinstance(col, dict) and "PointStart" in col and "PointEnd" in col:
                                    elements.append(col)
                        else:  # Slabs need point validation
                            for slab in item:
                                if isinstance(slab, dict) and all(f"Point{i}" in slab for i in range(1, 5)):
                                    elements.append(slab)
            # For beams, handle single level nesting
            elif isinstance(system_data, list):
                for item in system_data:
                    if isinstance(item, list):
                        elements.extend(item)  # Main element array
                    elif isinstance(item, dict):
                        # Skip metrics objects (those without geometric points)
                        if any(key.startswith("Point") for key in item.keys()):
                            elements.append(item)
            print(f"Found {len(elements)} {element_type} elements")
            return elements

        # Process StructuralFrame data if present
        print("\nProcessing structural frame data...")
        frame_data = {}
        
        if isinstance(data, dict) and "StructuralFrame" in data:
            print("Found StructuralFrame key in data")
            
            # Handle either a list of strings or direct dictionary data
            struct_frame = data["StructuralFrame"]
            
            if isinstance(struct_frame, list):
                print("StructuralFrame is a list, processing items...")
                for item in struct_frame:
                    if isinstance(item, str):
                        try:
                            # Parse JSON string from Grasshopper
                            parsed_item = json.loads(item)
                            if "StructuralFrame" in parsed_item:
                                # Process each system in the parsed data
                                for struct_item in parsed_item["StructuralFrame"]:
                                    if isinstance(struct_item, dict):
                                        if "BeamSystem" in struct_item:
                                            print("Found BeamSystem")
                                            frame_data["BeamSystem"] = struct_item["BeamSystem"]
                                        if "ColumnSystem" in struct_item:
                                            print("Found ColumnSystem")
                                            frame_data["ColumnSystem"] = struct_item["ColumnSystem"]
                                        if "SlabSystem" in struct_item:
                                            print("Found SlabSystem")
                                            frame_data["SlabSystem"] = struct_item["SlabSystem"]
                        except json.JSONDecodeError as e:
                            print(f"Error parsing JSON string: {e}")
                            continue
                    elif isinstance(item, dict):
                        # Handle direct dictionary items
                        if "BeamSystem" in item:
                            print("Found BeamSystem")
                            frame_data["BeamSystem"] = item["BeamSystem"]
                        if "ColumnSystem" in item:
                            print("Found ColumnSystem")
                            frame_data["ColumnSystem"] = item["ColumnSystem"]
                        if "SlabSystem" in item:
                            print("Found SlabSystem")
                            frame_data["SlabSystem"] = item["SlabSystem"]
            else:
                # Handle non-list StructuralFrame data
                frame_data = struct_frame
                print(f"Using direct StructuralFrame data: {type(frame_data)}")
        else:
            print("No StructuralFrame key found in data")
            
        print("\nProcessed frame data:")
        print(json.dumps(frame_data, indent=2))        # Process beams
        if isinstance(frame_data, dict) and "BeamSystem" in frame_data:
            beam_system = process_structural_elements(frame_data["BeamSystem"], "Beam")
            for beam_data in beam_system:
                if not isinstance(beam_data, dict):
                    continue
                try:
                    # Parse points
                    start = Vertex(*parse_point(beam_data.get("PointStart", "0,0,0")))
                    end = Vertex(*parse_point(beam_data.get("PointEnd", "0,0,0")))
                    
                    # Parse carbon
                    carbon = 0.0
                    try:
                        carbon = float(beam_data.get("CarbonEmission", 0))
                    except (ValueError, TypeError):
                        pass

                    # Create beam
                    beam = BeamGeometry(
                        name=str(beam_data.get("Name", "Beam")),
                        start_point=start,
                        end_point=end,
                        embodied_carbon=carbon,
                        structural_type="Beam"
                    )
                    scene.beams.append(beam)
                    print(f"Added beam: {beam}")
                except Exception as e:
                    print(f"Error processing beam: {e}")

        # Process columns - these should be vertical segments
        print("\nProcessing column system...")
        column_system = []  # Initialize empty list
        if isinstance(frame_data, dict) and "ColumnSystem" in frame_data:
            print(f"Found ColumnSystem in frame_data")
            print(f"Raw ColumnSystem data: {json.dumps(frame_data['ColumnSystem'], indent=2)}")
            # Handle the same nested list structure as slabs
            if isinstance(frame_data["ColumnSystem"], list):
                for item in frame_data["ColumnSystem"]:
                    if isinstance(item, list):
                        column_system = process_structural_elements([item], "Column")  # Pass as single-item list
                        print(f"Found {len(column_system)} columns in nested list")
                        break  # Found the column data, no need to continue
                    elif isinstance(item, dict) and any(key.startswith("Point") for key in item.keys()):
                        column_system = process_structural_elements([item], "Column")  # Try direct processing
                        print(f"Found {len(column_system)} columns in direct dict")
            for column_data in column_system:
                if not isinstance(column_data, dict):
                    print(f"Skipping non-dict column data: {type(column_data)}")
                    continue
                try:
                    # Parse points - columns use PointStart/PointEnd like beams
                    if "PointStart" not in column_data or "PointEnd" not in column_data:
                        print(f"Missing start/end points in column. Keys: {list(column_data.keys())}")
                        continue
                        
                    start = Vertex(*parse_point(column_data["PointStart"]))
                    end = Vertex(*parse_point(column_data["PointEnd"]))
                    
                    # Parse carbon
                    carbon = float(column_data.get("CarbonEmission", "0"))

                    # Create column using the beam geometry (since columns are vertical lines)
                    column = ColumnGeometry(
                        name=str(column_data.get("Name", "Column")),
                        start_point=start,
                        end_point=end,
                        embodied_carbon=carbon,
                        structural_type="Column"
                    )
                    scene.columns.append(column)
                    print(f"Added column: {column.name} from {start.z} to {end.z}")
                except Exception as e:
                    print(f"Error processing column: {e}")

        # Process slabs
        print("\nProcessing slab system...")
        if isinstance(frame_data, dict) and "SlabSystem" in frame_data:
            print(f"Found SlabSystem in frame_data")
            slab_system = process_structural_elements(frame_data["SlabSystem"], "Slab")
            for slab_data in slab_system:
                if not isinstance(slab_data, dict):
                    print(f"Skipping non-dict slab data: {type(slab_data)}")
                    continue
                try:
                    # For slabs, we expect four corner points numbered 1-4
                    corner_points = []
                    missing_points = False
                    
                    # Check for all four points first
                    for i in range(1, 5):
                        point_key = f"Point{i}"
                        if point_key not in slab_data:
                            print(f"Missing {point_key} in slab. Keys: {list(slab_data.keys())}")
                            missing_points = True
                            break
                    
                    if missing_points:
                        continue
                        
                    # Now parse all points since we know they exist
                    for i in range(1, 5):
                        point_key = f"Point{i}"
                        corner = Vertex(*parse_point(slab_data[point_key]))
                        corner_points.append(corner)

                    if corner_points:
                        carbon = 0.0
                        try:
                            carbon = float(slab_data.get("CarbonEmission", 0))
                        except (ValueError, TypeError):
                            pass

                        slab = SlabGeometry(
                            name=str(slab_data.get("Name", "Slab")),
                            corners=corner_points,
                            embodied_carbon=carbon,
                            structural_type="Slab"
                        )
                        scene.slabs.append(slab)
                        print(f"Added slab: {slab}")
                except Exception as e:
                    print(f"Error processing slab: {e}")

        # Store metadata
        scene.metadata = data.copy()
        print(f"Created scene with {len(scene.beams)} beams, {len(scene.columns)} columns, and {len(scene.slabs)} slabs")
        return scene

    def total_vertices(self) -> int:
        mesh_vertices = sum(m.vertex_count() for m in self.meshes)
        line_vertices = len(self.beams) * 2 + len(self.columns) * 2
        slab_vertices = sum(len(s.corners) for s in self.slabs)
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
            rows.append({
                "name": m.name,
                "vertices": m.vertex_count(),
                "faces": m.face_count(),
                "bbox_volume": m.bounding_box_volume(),
                "min_z": minz,
                "max_z": maxz,
                "embodied_carbon": m.embodied_carbon,
                "structural_type": m.structural_type
            })
        
        # Add beam geometries
        for b in self.beams:
            min_z = min(b.start_point.z, b.end_point.z)
            max_z = max(b.start_point.z, b.end_point.z)
            rows.append({
                "name": b.name,
                "vertices": 2,  # Start and end points
                "faces": 0,     # Beams don't have faces
                "bbox_volume": 0,  # Line has no volume
                "length": b.length(),
                "min_z": min_z,
                "max_z": max_z,
                "embodied_carbon": b.embodied_carbon,
                "structural_type": b.structural_type
            })

        # Add columns (as linear elements)
        for c in self.columns:
            min_z = min(c.start_point.z, c.end_point.z)
            max_z = max(c.start_point.z, c.end_point.z)
            rows.append({
                "name": c.name,
                "vertices": 2,
                "faces": 0,
                "bbox_volume": 0,
                "length": c.length(),
                "min_z": min_z,
                "max_z": max_z,
                "embodied_carbon": c.embodied_carbon,
                "structural_type": c.structural_type
            })

        # Add slabs/floors
        for slab in self.slabs:
            (minx, miny, minz), (maxx, maxy, maxz) = slab.bounds()
            rows.append({
                "name": slab.name,
                "vertices": len(slab.corners),
                "faces": 2,  # Represented as quad (two triangles)
                "bbox_volume": (maxx - minx) * (maxy - miny) * (maxz - minz) if maxz > minz else 0,
                "area": slab.area(),
                "min_z": minz,
                "max_z": maxz,
                "embodied_carbon": slab.embodied_carbon,
                "structural_type": slab.structural_type
            })
        
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