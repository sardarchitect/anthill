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


class MeshViewer:
	def __init__(self, scene: MeshScene, color_by: str = "auto"):
		self.scene = scene
		self.color_by = color_by
		self._carbon_values = [m.embodied_carbon for m in scene.meshes if m.embodied_carbon is not None]

	def _carbon_active(self) -> bool:
		if self.color_by == "embodied_carbon":
			return bool(self._carbon_values)
		if self.color_by == "auto":
			return bool(self._carbon_values)
		return False

	def build_figure(self) -> go.Figure:
		fig = go.Figure()
		carbon_mode = self._carbon_active()
		colors = _color_gen(len(self.scene.meshes)) if not carbon_mode else None
		cmin = cmax = None
		colorscale = None
		if carbon_mode:
			cmin = min(self._carbon_values)
			cmax = max(self._carbon_values)
			if cmin == cmax:
				# avoid zero range
				cmin *= 0.99
				cmax *= 1.01
			# Reverse so low = green, high = red (intuitive danger scale)
			colorscale = px.colors.diverging.RdYlGn[::-1]

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
						showscale=(idx == 0),
						colorbar=dict(title="Embodied Carbon"),
						hovertext=f"{mesh.name}<br>EC: {intensity_val:.2f}",
						hoverinfo="text",
					)
				)
			else:
				fig.add_trace(
					go.Mesh3d(
						**common_kwargs,
						color=colors[idx] if colors else "#888888",
						hovertext=f"{mesh.name}",
						hoverinfo="text",
					)
				)

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
			fig.update_layout(title="3D Meshes (Colored by Embodied Carbon)")
		return fig

	@property
	def carbon_coloring_active(self) -> bool:
		return self._carbon_active()

