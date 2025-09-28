"""Charts component creating analytic Plotly figures from scene summary."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
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

	def carbon_aggregation_summary(self, classifier=None):
		"""Create comprehensive carbon aggregation analytics."""
		rows = [r for r in self._summary if r.get("embodied_carbon") is not None]
		if not rows:
			return go.Figure()
		
		def default_classifier(r):
			stype = r.get("structural_type")
			if stype:
				return stype
			name = r["name"].lower()
			if any(k in name for k in ("slab", "floor", "plate")):
				return "Floor"
			if any(k in name for k in ("beam", "girder")):
				return "Beam"
			if any(k in name for k in ("column", "pillar", "post")):
				return "Column"
			return "Other"
		
		classifier = classifier or default_classifier
		
		# Group data by structural type
		grouped = {}
		for r in rows:
			group = classifier(r)
			if group not in grouped:
				grouped[group] = {
					'total_carbon': 0.0,
					'count': 0,
					'lengths': [],
					'elements': []
				}
			grouped[group]['total_carbon'] += r["embodied_carbon"] or 0.0
			grouped[group]['count'] += 1
			if 'length' in r:
				grouped[group]['lengths'].append(r['length'])
			grouped[group]['elements'].append(r)
		
		# Create multi-metric bar chart
		categories = list(grouped.keys())
		total_carbons = [grouped[cat]['total_carbon'] for cat in categories]
		counts = [grouped[cat]['count'] for cat in categories]
		avg_carbons = [grouped[cat]['total_carbon'] / grouped[cat]['count'] for cat in categories]
		
		fig = go.Figure()
		
		# Total carbon per category
		fig.add_trace(go.Bar(
			name='Total Carbon (kgCO2e)',
			x=categories,
			y=total_carbons,
			marker_color='rgba(255, 99, 71, 0.8)',
			text=[f"{val:.1f}" for val in total_carbons],
			textposition='auto',
			yaxis='y1'
		))
		
		# Element count (secondary y-axis)
		fig.add_trace(go.Scatter(
			name='Element Count',
			x=categories,
			y=counts,
			mode='markers+lines+text',
			marker=dict(size=12, color='rgba(50, 171, 96, 0.8)'),
			line=dict(color='rgba(50, 171, 96, 0.8)', width=3),
			text=[f"{val}" for val in counts],
			textposition='top center',
			yaxis='y2'
		))
		
		fig.update_layout(
			title='Carbon Aggregation by Structural Type',
			xaxis_title='Structural Type',
			yaxis=dict(title='Total Carbon (kgCO2e)', side='left', color='rgba(255, 99, 71, 1)'),
			yaxis2=dict(title='Element Count', side='right', overlaying='y', color='rgba(50, 171, 96, 1)'),
			legend=dict(x=0.01, y=0.99),
			margin=dict(l=0, r=0, t=40, b=40),
			hovermode='x unified'
		)
		
		return fig

	def carbon_intensity_analysis(self, classifier=None):
		"""Analyze carbon intensity (carbon per unit length/area)."""
		rows = [r for r in self._summary if r.get("embodied_carbon") is not None and r.get("length") is not None]
		if not rows:
			return go.Figure()
		
		def default_classifier(r):
			stype = r.get("structural_type")
			if stype:
				return stype
			name = r["name"].lower()
			if any(k in name for k in ("beam", "girder")):
				return "Beam"
			if any(k in name for k in ("column", "pillar")):
				return "Column"
			return "Other"
		
		classifier = classifier or default_classifier
		
		# Calculate carbon intensity for each element
		intensity_data = []
		for r in rows:
			group = classifier(r)
			length = r.get('length', 1)  # Avoid division by zero
			if length > 0:
				intensity = r["embodied_carbon"] / length
				intensity_data.append({
					'type': group,
					'name': r['name'],
					'carbon': r["embodied_carbon"],
					'length': length,
					'intensity': intensity
				})
		
		if not intensity_data:
			return go.Figure()
		
		df = pd.DataFrame(intensity_data)
		
		fig = px.box(
			df,
			x='type',
			y='intensity',
			title='Carbon Intensity Distribution (kgCO2e per unit length)',
			color='type',
			points='all'
		)
		
		fig.update_layout(
			xaxis_title='Structural Type',
			yaxis_title='Carbon Intensity (kgCO2e/unit)',
			margin=dict(l=0, r=0, t=40, b=40),
			showlegend=False
		)
		
		return fig

	def carbon_by_floor_level(self):
		"""Analyze carbon distribution by floor/elevation level."""
		rows = [r for r in self._summary if r.get("embodied_carbon") is not None]
		if not rows:
			return go.Figure()
		
		# Group by Z-level (assuming floor levels)
		floor_data = {}
		for r in rows:
			z_level = r.get('max_z', 0)
			# Round to nearest floor (assuming ~8.67m spacing based on your data)
			floor_num = round(z_level / 8.67)
			
			if floor_num not in floor_data:
				floor_data[floor_num] = {
					'total_carbon': 0.0,
					'count': 0,
					'elements': []
				}
			
			floor_data[floor_num]['total_carbon'] += r["embodied_carbon"] or 0.0
			floor_data[floor_num]['count'] += 1
			floor_data[floor_num]['elements'].append(r)
		
		floors = sorted(floor_data.keys())
		carbons = [floor_data[f]['total_carbon'] for f in floors]
		counts = [floor_data[f]['count'] for f in floors]
		
		fig = go.Figure()
		
		fig.add_trace(go.Bar(
			x=[f"Floor {f}" for f in floors],
			y=carbons,
			name='Total Carbon',
			marker_color='rgba(158, 202, 225, 0.8)',
			text=[f"{val:.1f}" for val in carbons],
			textposition='auto'
		))
		
		fig.update_layout(
			title='Carbon Distribution by Floor Level',
			xaxis_title='Floor Level',
			yaxis_title='Total Carbon (kgCO2e)',
			margin=dict(l=0, r=0, t=40, b=40)
		)
		
		return fig

	def carbon_kpi_dashboard(self, classifier=None):
		"""Create KPI dashboard with key carbon metrics."""
		rows = [r for r in self._summary if r.get("embodied_carbon") is not None]
		if not rows:
			return go.Figure()
		
		def default_classifier(r):
			stype = r.get("structural_type")
			if stype:
				return stype
			name = r["name"].lower()
			if any(k in name for k in ("beam", "girder")):
				return "Beam"
			if any(k in name for k in ("slab", "floor", "plate")):
				return "Floor"
			if any(k in name for k in ("column", "pillar")):
				return "Column"
			return "Other"
		
		classifier = classifier or default_classifier
		
		# Calculate KPIs
		total_carbon = sum(r["embodied_carbon"] for r in rows)
		avg_carbon = total_carbon / len(rows)
		max_carbon = max(r["embodied_carbon"] for r in rows)
		min_carbon = min(r["embodied_carbon"] for r in rows)
		
		# Group statistics
		grouped_stats = {}
		for r in rows:
			group = classifier(r)
			if group not in grouped_stats:
				grouped_stats[group] = []
			grouped_stats[group].append(r["embodied_carbon"])
		
		# Create summary statistics visualization
		fig = go.Figure()
		
		# Create a summary table as text
		stats_by_type = []
		for group, values in grouped_stats.items():
			stats_by_type.append({
				'Type': group,
				'Count': len(values),
				'Total (kgCO2e)': f"{sum(values):.1f}",
				'Average (kgCO2e)': f"{np.mean(values):.1f}",
				'% of Total': f"{(sum(values)/total_carbon)*100:.1f}%"
			})
		
		df_stats = pd.DataFrame(stats_by_type)
		
		fig.add_trace(go.Table(
			header=dict(
				values=list(df_stats.columns),
				fill_color='paleturquoise',
				align='left',
				font=dict(size=12)
			),
			cells=dict(
				values=[df_stats[col] for col in df_stats.columns],
				fill_color='lavender',
				align='left',
				font=dict(size=11)
			)
		))
		
		fig.update_layout(
			title=f'Carbon Analytics Dashboard - Total: {total_carbon:.1f} kgCO2e',
			margin=dict(l=0, r=0, t=60, b=20),
			height=400
		)
		
		return fig

