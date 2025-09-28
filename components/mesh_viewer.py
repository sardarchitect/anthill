"""Mesh viewer component translating domain models to Plotly figures."""

from __future__ import annotations

import random
from typing import List, Optional
import plotly.graph_objects as go
import plotly.express as px
from models.mesh import MeshScene, MeshGeometry, flatten_vertices


def _color_gen(n: int) -> List[str]:
	random.seed(42)
	base_colors = [
		"#1f77b4",
		"#ff7f0e",
		"#2ca02c",
		"#d62728",
		"#9467bd",
		"#8c564b",
		"#e377c2",
		"#7f7f7f",
		"#bcbd22",
		"#17becf",
	]
	if n <= len(base_colors):
		return base_colors[:n]
	# Extend deterministically
	out = []
	for i in range(n):
		out.append(base_colors[i % len(base_colors)])
	return out


def _get_carbon_color(carbon_value: float, cmin: float, cmax: float) -> str:
	"""Get color for carbon value using smooth gradient interpolation."""
	if cmax == cmin:
		return '#ffff00'  # Yellow for single value
	
	# Normalize carbon value to 0-1 range
	normalized = (carbon_value - cmin) / (cmax - cmin)
	normalized = max(0, min(1, normalized))  # Clamp to [0,1]
	
	# Define gradient stops with more nuanced colors
	gradient_stops = [
		(0.0, (0, 255, 0)),      # Bright green
		(0.15, (127, 255, 0)),   # Spring green
		(0.3, (255, 255, 0)),    # Yellow
		(0.5, (255, 165, 0)),    # Orange
		(0.7, (255, 102, 0)),    # Red-orange
		(0.85, (255, 0, 0)),     # Red
		(1.0, (139, 0, 0))       # Dark red
	]
	
	# Find the two stops to interpolate between
	for i in range(len(gradient_stops) - 1):
		stop1_pos, stop1_color = gradient_stops[i]
		stop2_pos, stop2_color = gradient_stops[i + 1]
		
		if stop1_pos <= normalized <= stop2_pos:
			# Interpolate between the two colors
			if stop2_pos == stop1_pos:
				r, g, b = stop1_color
			else:
				t = (normalized - stop1_pos) / (stop2_pos - stop1_pos)
				r = int(stop1_color[0] + t * (stop2_color[0] - stop1_color[0]))
				g = int(stop1_color[1] + t * (stop2_color[1] - stop1_color[1]))
				b = int(stop1_color[2] + t * (stop2_color[2] - stop1_color[2]))
			
			return f'rgb({r}, {g}, {b})'
	
	# Fallback (should not reach here)
	return f'rgb(255, 0, 0)'


class MeshViewer:
	def __init__(self, scene: MeshScene, color_by: str = "auto"):
		self.scene = scene
		self.color_by = color_by
		# Collect carbon values from all element types for consistent coloring
		mesh_carbon_values = [m.embodied_carbon for m in scene.meshes if m.embodied_carbon is not None]
		beam_carbon_values = [b.embodied_carbon for b in scene.beams if b.embodied_carbon is not None]
		column_carbon_values = [c.embodied_carbon for c in scene.columns if c.embodied_carbon is not None]
		slab_carbon_values = [s.embodied_carbon for s in scene.slabs if s.embodied_carbon is not None]
		self._carbon_values = mesh_carbon_values + beam_carbon_values + column_carbon_values + slab_carbon_values

	def _carbon_active(self) -> bool:
		if self.color_by == "embodied_carbon":
			return bool(self._carbon_values)
		if self.color_by == "auto":
			return bool(self._carbon_values)
		return False

	def build_figure(self) -> go.Figure:
		fig = go.Figure()
		carbon_mode = self._carbon_active()
		total_elements = (
			len(self.scene.meshes)
			+ len(self.scene.beams)
			+ len(self.scene.columns)
			+ len(self.scene.slabs)
		)
		colors = _color_gen(total_elements) if not carbon_mode else None
		cmin = cmax = None
		colorscale = None
		if carbon_mode:
			cmin = min(self._carbon_values) if self._carbon_values else 0
			cmax = max(self._carbon_values) if self._carbon_values else 1
			if cmin == cmax:
				# avoid zero range
				cmin *= 0.99
				cmax *= 1.01
			# Create a sophisticated gradient from low to high carbon emissions
			# Using a multi-stop gradient: Green -> Yellow-Green -> Yellow -> Orange -> Red -> Dark Red
			colorscale = [
				[0.0, '#00ff00'],    # Bright green (lowest carbon)
				[0.15, '#7fff00'],   # Spring green
				[0.3, '#ffff00'],    # Yellow
				[0.5, '#ffa500'],    # Orange
				[0.7, '#ff6600'],    # Red-orange
				[0.85, '#ff0000'],   # Red
				[1.0, '#8b0000']     # Dark red (highest carbon)
			]
		
		color_idx = 0

		# Render mesh geometries
		for idx, mesh in enumerate(self.scene.meshes):
			if not mesh.faces:
				continue
			xs, ys, zs = flatten_vertices(mesh.vertices)
			i_idx = [f[0] for f in mesh.faces]
			j_idx = [f[1] for f in mesh.faces]
			k_idx = [f[2] for f in mesh.faces]
			common_kwargs = dict(
				x=xs,
				y=ys,
				z=zs,
				i=i_idx,
				j=j_idx,
				k=k_idx,
				name=mesh.name,
				opacity=0.68,
				flatshading=True,
			)
			if carbon_mode and mesh.embodied_carbon is not None:
				intensity_val = mesh.embodied_carbon
				fig.add_trace(
					go.Mesh3d(
						**common_kwargs,
						intensity=[intensity_val] * len(xs),
						colorscale=colorscale,
						cmin=cmin,
						cmax=cmax,
						showscale=(color_idx == 0),
						colorbar=dict(title="Embodied Carbon"),
						hovertext=f"{mesh.name}<br>EC: {intensity_val:.2f}",
						hoverinfo="text",
					)
				)
			else:
				fig.add_trace(
					go.Mesh3d(
						**common_kwargs,
						color=colors[color_idx] if colors else "#888888",
						hovertext=f"{mesh.name}",
						hoverinfo="text",
					)
				)
			color_idx += 1

		# Render beam geometries as lines
		for idx, beam in enumerate(self.scene.beams):
			x_coords = [beam.start_point.x, beam.end_point.x]
			y_coords = [beam.start_point.y, beam.end_point.y]
			z_coords = [beam.start_point.z, beam.end_point.z]
			
			if carbon_mode and beam.embodied_carbon is not None:
				# Use gradient color function for smooth transitions
				line_color = _get_carbon_color(beam.embodied_carbon, cmin, cmax)
				hover_text = f"{beam.name}<br>EC: {beam.embodied_carbon:.2f}<br>Length: {beam.length():.2f}"
			else:
				line_color = colors[color_idx] if colors else "#888888"
				hover_text = f"{beam.name}<br>Length: {beam.length():.2f}"
			
			fig.add_trace(
				go.Scatter3d(
					x=x_coords,
					y=y_coords,
					z=z_coords,
					mode='lines',
					name=beam.name,
					line=dict(
						color=line_color,
						width=8
					),
					hovertext=hover_text,
					hoverinfo="text",
					showlegend=False  # Too many beams would clutter legend
				)
			)
			color_idx += 1

		# Render column geometries (as vertical lines)
		for column in self.scene.columns:
			x_coords = [column.start_point.x, column.end_point.x]
			y_coords = [column.start_point.y, column.end_point.y]
			z_coords = [column.start_point.z, column.end_point.z]

			if carbon_mode and column.embodied_carbon is not None:
				line_color = _get_carbon_color(column.embodied_carbon, cmin, cmax)
				hover_text = (
					f"{column.name}<br>EC: {column.embodied_carbon:.2f}<br>Length: {column.length():.2f}"
				)
			else:
				line_color = colors[color_idx] if colors else "#444444"
				hover_text = f"{column.name}<br>Length: {column.length():.2f}"

			fig.add_trace(
				go.Scatter3d(
					x=x_coords,
					y=y_coords,
					z=z_coords,
					mode='lines',
					name=column.name,
					line=dict(
						color=line_color,
						width=10
					),
					hovertext=hover_text,
					hoverinfo="text",
					showlegend=False
				)
			)
			color_idx += 1

		# Render slab geometries as filled planes
		for slab in self.scene.slabs:
			if not slab.corners:
				continue
			xs = [v.x for v in slab.corners]
			ys = [v.y for v in slab.corners]
			zs = [v.z for v in slab.corners]
			triangles = []
			for tri_idx in range(1, len(slab.corners) - 1):
				triangles.append((0, tri_idx, tri_idx + 1))
			i_idx = [tri[0] for tri in triangles]
			j_idx = [tri[1] for tri in triangles]
			k_idx = [tri[2] for tri in triangles]

			common_kwargs = dict(
				x=xs,
				y=ys,
				z=zs,
				i=i_idx,
				j=j_idx,
				k=k_idx,
				name=slab.name,
				opacity=0.45,
				flatshading=True,
			)

			if carbon_mode and slab.embodied_carbon is not None:
				intensity_val = slab.embodied_carbon
				hover_text = (
					f"{slab.name}<br>EC: {slab.embodied_carbon:.2f}<br>Area: {slab.area():.2f}"
				)
				fig.add_trace(
					go.Mesh3d(
						**common_kwargs,
						intensity=[intensity_val] * len(xs),
						colorscale=colorscale,
						cmin=cmin,
						cmax=cmax,
						showscale=False,
						hovertext=hover_text,
						hoverinfo="text",
					)
				)
			else:
				hover_text = f"{slab.name}<br>Area: {slab.area():.2f}"
				fig.add_trace(
					go.Mesh3d(
						**common_kwargs,
						color=colors[color_idx] if colors else "rgba(100,149,237,0.65)",
						hovertext=hover_text,
						hoverinfo="text",
					)
				)
			color_idx += 1

		fig.update_layout(
			scene=dict(
				xaxis_title="X",
				yaxis_title="Y",
				zaxis_title="Z",
				aspectmode="data",
			),
			margin=dict(l=0, r=0, t=30, b=0),
			legend=dict(orientation="h"),
		)
		if carbon_mode:
			fig.update_layout(title="3D Structure (Carbon Gradient: Green=Low → Red=High)")
		return fig

	@property
	def carbon_coloring_active(self) -> bool:
		return self._carbon_active()

