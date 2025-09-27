"""Charts component creating analytic Plotly figures from scene summary."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
from models.mesh import MeshScene


class ChartsBuilder:
	def __init__(self, scene: MeshScene):
		self.scene = scene
		self._summary = scene.summary()

	def carbon_pie(self, classifier=None):
		"""Return a pie chart of embodied carbon grouped by a classifier.

		classifier: callable taking row dict -> group name. If None, tries to
		infer 'Floor' vs 'Beam' by name keywords else 'Other'.
		"""
		rows = [r for r in self._summary if r.get("embodied_carbon") is not None]
		if not rows:
			return go.Figure()
		def default_classifier(r):
			# Use explicit structural_type if provided
			stype = r.get("structural_type")
			if stype:
				return stype
			name = r["name"].lower()
			if any(k in name for k in ("slab", "floor", "plate")):
				return "Floor"
			if any(k in name for k in ("beam", "girder")):
				return "Beam"
			return "Other"
		classifier = classifier or default_classifier
		grouped = {}
		for r in rows:
			g = classifier(r)
			grouped.setdefault(g, 0.0)
			grouped[g] += r["embodied_carbon"] or 0.0
		data = [{"type": k, "carbon": v} for k, v in grouped.items()]
		fig = px.pie(data, values="carbon", names="type", title="Embodied Carbon by Structural Type")
		fig.update_traces(textposition="inside", textinfo="percent+label")
		fig.update_layout(margin=dict(l=0, r=0, t=40, b=0))
		return fig

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

