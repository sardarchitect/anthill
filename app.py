
import streamlit as st
from pathlib import Path
import json
from typing import Optional

from services.mcp_client import MCPClient
from components.chat import ChatComponent
from utils.json_loader import load_scene, MeshParseError
from components.mesh_viewer import MeshViewer
from components.charts import ChartsBuilder


st.set_page_config(page_title="Anthill", layout="wide")
st.title("Anthill Prototype")
st.caption("Structural embodied carbon analysis for massing models.")


def get_default_json_path() -> Optional[Path]:
	candidate = Path(__file__).parent / "Test 01.json"
	return candidate if candidate.exists() else None


def parse_uploaded_bytes(data: bytes) -> Optional[Path]:
	# Save to a temp file in session directory for consistent Path-based loader.
	tmp_dir = Path(".cache")
	tmp_dir.mkdir(exist_ok=True)
	tmp_file = tmp_dir / "uploaded_scene.json"
	tmp_file.write_bytes(data)
	return tmp_file


def load_scene_safe(path: Path):
	try:
		return load_scene(path)
	except MeshParseError as e:
		st.error(f"Failed to parse mesh JSON: {e}")
		return None


def main():
	client = MCPClient()
	chat_component = ChatComponent(client)

	col_chat, col_view = st.columns([0.45, 0.55])

	with col_chat:
		st.markdown("<div class='full-height-col'>", unsafe_allow_html=True)
		uploaded_bytes = chat_component.render()
		st.markdown("</div>", unsafe_allow_html=True)

	scene = None
	active_source = None
	if uploaded_bytes:
		path = parse_uploaded_bytes(uploaded_bytes)
		if path:
			scene = load_scene_safe(path)
			active_source = "Uploaded file"
	if scene is None:
		default_path = get_default_json_path()
		if default_path:
			scene = load_scene_safe(default_path)
			active_source = "Default sample"

	with col_view:
		st.subheader("3D Visualization & Analytics")
		if scene is None:
			st.info("No mesh scene available yet. Upload a JSON file in the chat column.")
			return
		st.caption(f"Source: {active_source}")
		viewer = MeshViewer(scene, color_by="auto")
		fig = viewer.build_figure()
		st.plotly_chart(fig, use_container_width=True)
		if viewer.carbon_coloring_active:
			st.caption("Color scale: Embodied carbon (green = low, red = high)")

		charts = ChartsBuilder(scene)
		col1, col2 = st.columns(2)
		with col1:
			st.plotly_chart(charts.faces_bar(), use_container_width=True)
			st.plotly_chart(charts.volume_scatter(), use_container_width=True)
		with col2:
			st.plotly_chart(charts.vertices_bar(), use_container_width=True)


if __name__ == "__main__":
	main()

