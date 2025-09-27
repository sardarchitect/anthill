"""Charts component creating analytic Plotly figures from scene summary."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
from models.mesh import MeshScene


class ChartsBuilder:
	def __init__(self, scene: MeshScene):
		self.scene = scene
		self._summary = scene.summary()

	def faces_bar(self):
		if not self._summary:
			return go.Figure()
		fig = px.bar(
			self._summary,
			x="name",
			y="faces",
			title="Face Count per Mesh",
		)
		fig.update_layout(margin=dict(l=0, r=0, t=40, b=40))
		return fig

	def vertices_bar(self):
		if not self._summary:
			return go.Figure()
		fig = px.bar(
			self._summary,
			x="name",
			y="vertices",
			title="Vertex Count per Mesh",
			color="vertices",
			color_continuous_scale="Viridis",
		)
		fig.update_layout(margin=dict(l=0, r=0, t=40, b=40), coloraxis_showscale=False)
		return fig

	def volume_scatter(self):
		if not self._summary:
			return go.Figure()
		fig = px.scatter(
			self._summary,
			x="faces",
			y="bbox_volume",
			size="vertices",
			text="name",
			title="BBox Volume vs Faces",
			trendline="ols",
		)
		fig.update_traces(textposition="top center")
		fig.update_layout(margin=dict(l=0, r=0, t=40, b=40))
		return fig

