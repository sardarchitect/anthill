
import streamlit as st
from pathlib import Path
import json
import pandas as pd
from typing import Optional
import os
from dotenv import load_dotenv
from services.mcp_client import MCPClient
from components.chat import ChatComponent
from utils.json_loader import load_scene, MeshParseError
from components.mesh_viewer import MeshViewer
from components.charts import ChartsBuilder


st.set_page_config(page_title="Anthill", layout="wide")
st.title("Anthill Prototype")
st.caption("Structural embodied carbon analysis for massing models.")

if "buildingJSON" not in st.session_state:
	st.session_state.buidlingJSON = None


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


def load_scene_safe(data):
	"""Load a scene from a file path, JSON string, or dictionary.

	Args:
		data: Can be:
			- Path object pointing to a JSON file
			- Dictionary containing the scene data
			- String containing JSON data

	Returns:
		The loaded scene, or None if loading failed
	"""
	try:
		if isinstance(data, Path):
			# If data is a file path, use the original load_scene function
			return load_scene(data)
		elif isinstance(data, dict):
			# If data is a dictionary, parse it directly
			from models.mesh import MeshScene
			return MeshScene.from_dict(data)
		elif isinstance(data, str):
			# If data is a string, try to parse it as JSON
			try:
				json_data = json.loads(data)
				from models.mesh import MeshScene
				return MeshScene.from_dict(json_data)
			except json.JSONDecodeError as e:
				st.error(f"Invalid JSON string: {str(e)}")
				return None
		else:
			st.error(f"Invalid input type for load_scene_safe: {type(data)}")
			return None
	except MeshParseError as e:
		st.error(f"Failed to parse mesh JSON: {e}")
		return None
	except Exception as e:
		st.error(f"Error loading scene: {str(e)}")
		return None


# Global variable to store the building JSON
buildingJSON = None

def main():
	# Load environment variables
	load_dotenv()
	# Initialize global buildingJSON in session state if not exists
	if 'buildingJSON' not in st.session_state:
		st.session_state['buildingJSON'] = None
	with st.sidebar:
		st.header("🔑 Configuration")
		
		# Try to get API key from environment first
		env_api_key = os.getenv("OPENAI_API_KEY")
		
		# Debug information
		if st.checkbox("Show debug info", value=False):
			st.write(f"Environment API key found: {bool(env_api_key)}")
			if env_api_key:
				st.write(f"Environment key starts with: {env_api_key[:10]}...")
		
		# Use environment key as default value if available
		api_key = st.text_input(
			"OpenAI API Key",
			value=env_api_key if env_api_key else "",
			type="password",
			placeholder="sk-...",
			help="Enter your OpenAI API key to enable chatbot functionality"
		)
		
		# Store API key in session state for persistence
		if api_key:
			st.session_state["openai_api_key"] = api_key
		elif "openai_api_key" in st.session_state:
			api_key = st.session_state["openai_api_key"]
		
		if api_key:
			st.success("✅ API key configured")
			st.write(f"API key length: {len(api_key)} characters")
			if env_api_key and api_key == env_api_key:
				st.info("💡 Using API key from environment")
		else:
			st.warning("⚠️ Enter API key to use chatbot")
			st.info("💡 You can also set OPENAI_API_KEY in your .env file")

	client = MCPClient(api_key=api_key if api_key else None)
	
	# Show MCP connection status
	with st.sidebar:
		st.header("🔧 Grasshopper Integration")
		if client.mcp_tools_available:
			st.success("✅ Grasshopper MCP server connected")
			available_tools = client.grasshopper_client.get_available_tools()
			if available_tools:
				st.info(f"🛠️ {len(available_tools)} tools available")
				if st.checkbox("Show available tools", value=False):
					for tool in available_tools:
						st.text(f"• {tool['function']['name']}: {tool['function']['description']}")
		else:
			st.warning("⚠️ Grasshopper MCP server not connected")
			st.info("Make sure compute_mcp.py is working and Rhino Compute is running")

	chat_component = ChatComponent(client)

	col_chat, col_view = st.columns([0.45, 0.55])

	with col_chat:
		uploaded_bytes = chat_component.render()

	scene = None
	active_source = None

	# Check if buildingJSON is set from compute_mcp
	jsonInfo = st.session_state.get('buildingJSON')
	if jsonInfo is not None:
		active_source = "Computed Result"
		scene = load_scene_safe(jsonInfo)
	
	# if uploaded_bytes:
	# 	path = parse_uploaded_bytes(uploaded_bytes)
	# 	if path:
	# 		scene = load_scene_safe(path)
	# 		active_source = "Uploaded file"
	# if scene is None:
	# 	default_path = get_default_json_path()
	# 	if default_path:
	# 		scene = load_scene_safe(default_path)
	# 		active_source = "Default sample"

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
		print('scene', scene)
		charts = ChartsBuilder(scene)
		if any(r.get("embodied_carbon") for r in scene.summary()):
			# Main classifier function for consistency across all charts
			def get_classifier():
				# Simple manual mapping UI
				custom_map_input = st.text_area(
					"Custom mappings (one per line: name_fragment=Group)",
					value="floor=Floor\nbeam=Beam\ncolumn=Column",
					height=60,
					key="classifier_input"
				)
				mapping = {}
				for line in custom_map_input.splitlines():
					if "=" in line:
						frag, grp = line.split("=", 1)
						frag = frag.strip().lower()
						grp = grp.strip()
						if frag:
							mapping[frag] = grp

				def classifier(row):
					# 1. structural_type direct
					stype = row.get("structural_type")
					if stype:
						return stype
					# 2. custom mapping by name fragment
					name_l = row["name"].lower()
					for frag, grp in mapping.items():
						if frag in name_l:
							return grp
					# 3. fallback heuristics
					if any(k in name_l for k in ("slab", "floor", "plate")):
						return "Floor"
					if any(k in name_l for k in ("beam", "girder")):
						return "Beam"
					if any(k in name_l for k in ("column", "pillar", "post")):
						return "Column"
					return "Other"
				
				return classifier

			classifier = get_classifier()

			# KPI Dashboard - Most Important Overview
			with st.expander("📊 Carbon Analytics Dashboard", expanded=True):
				st.caption("Comprehensive carbon footprint analysis with key performance indicators")
				kpi_fig = charts.carbon_kpi_dashboard(classifier=classifier)
				st.plotly_chart(kpi_fig, use_container_width=True)

			# Aggregation Analysis
			with st.expander("📈 Carbon Aggregation by Structure Type", expanded=True):
				st.caption("Total carbon emissions grouped by structural elements (beams, floors, columns)")
				agg_fig = charts.carbon_aggregation_summary(classifier=classifier)
				st.plotly_chart(agg_fig, use_container_width=True)

			# Traditional Pie Chart (kept as requested)
			with st.expander("🥧 Carbon Distribution (Pie Chart)", expanded=True):
				st.caption("Traditional pie chart breakdown by structural type")
				pie = charts.carbon_pie(classifier=classifier)
				st.plotly_chart(pie, use_container_width=True)

			# Carbon Efficiency Analysis
			with st.expander("⚡ Carbon Intensity Analysis", expanded=False):
				st.caption("Carbon efficiency: emissions per unit length - identifies high-impact elements")
				intensity_fig = charts.carbon_intensity_analysis(classifier=classifier)
				st.plotly_chart(intensity_fig, use_container_width=True)

			# Spatial Analysis
			with st.expander("🏢 Carbon by Floor Level", expanded=False):
				st.caption("Vertical distribution of carbon emissions across building levels")
				floor_fig = charts.carbon_by_floor_level()
				st.plotly_chart(floor_fig, use_container_width=True)

			# Debug Information
			if st.checkbox("Show detailed element data", value=False):
				st.subheader("Element Classification Debug")
				summary_df = pd.DataFrame(scene.summary())
				if not summary_df.empty and 'embodied_carbon' in summary_df.columns:
					# Add classifier results for debugging
					summary_df['classified_type'] = summary_df.apply(classifier, axis=1)
					st.dataframe(summary_df)


if __name__ == "__main__":
	main()