import base64
import requests
from mcp.server.fastmcp import FastMCP
import streamlit as st
import json

mcp = FastMCP("EmbodiedCarbonBuildingCalculator")

# Path to your Grasshopper definition
GH_PATH = r"C:\Users\sxmoore\Source\Hackathon\AntHill\Streamlit\anthill\grasshopper\antHill_Building Frame.gh"
COMPUTE_URL = "http://localhost:8081/grasshopper"

# Read and base64 encode GH definition once at startup
with open(GH_PATH, "rb") as f:
    gh_bytes = f.read()
encoded_def = base64.b64encode(gh_bytes).decode("utf-8")

def call_compute(xBaySize: float, yBaySize: float, storyHeight: float):
    print('calling compute')
    """Send request to Rhino Compute with with X bay size, Y bay size, and story height"""
    payload = {
        "algo": encoded_def,
        "pointer": None,
        "values": [
            {
                "ParamName": "xBaySize",
                "InnerTree": {
                    "{0}": [
                        {"type": "System.Double", "data": str(xBaySize)}
                    ]
                }
            },
            {
                "ParamName": "yBaySize",
                "InnerTree": {
                    "{0}": [
                        {"type": "System.Double", "data": str(yBaySize)}
                    ]
                }
            },
            {
                "ParamName": "storyHeight",
                "InnerTree": {
                    "{0}": [
                        {"type": "System.Double", "data": str(storyHeight)}
                    ]
                }
            }
        ]
    }
    response = requests.post(COMPUTE_URL, json=payload)
    res = response.json()
    data = res["values"][0]["InnerTree"]["{0}"][0]["data"]
    print("Raw response data:")
    print(data)
    try:
        parsed = json.loads(data)
        print("\nFull Grasshopper data structure:")
        print(json.dumps(parsed, indent=2))
        print("\nStructure analysis:")
        if isinstance(parsed, dict):
            def analyze_structure(d, prefix=""):
                for key, value in d.items():
                    if isinstance(value, dict):
                        print(f"{prefix}Dict key: {key}")
                        analyze_structure(value, prefix + "  ")
                    elif isinstance(value, list):
                        print(f"{prefix}List key: {key} (length: {len(value)})")
                        if value and isinstance(value[0], dict):
                            print(f"{prefix}  First item keys: {list(value[0].keys())}")
            analyze_structure(parsed)
        st.session_state.buildingJSON = parsed
        return parsed
    except json.JSONDecodeError as e:
        print("Error parsing JSON:", e)
        return None

def parse_point(s: str):
    """Convert '{x, y, z}' string into a tuple of floats."""
    return tuple(float(v) for v in s.strip("{}").split(","))

@mcp.tool()
async def calculateBuildingEmbodiedCarbon(
    xBaySize: int | float,
    yBaySize: int | float,
    storyHeight: int | float
) -> dict:
    """Run embodied carbon analysis using Rhino Compute Grasshopper definition.

    Args:
        xBaySize: The bay size in the X direction.
        yBaySize: The bay size in the Y direction.
        storyHeight: The story height of the frame.

    Returns:
        A dictionary containing the StructuralFrame and total carbon emission.
    """
    result = call_compute(xBaySize, yBaySize, storyHeight)

    # Extract Grasshopper output values
    try:
        print('result', result)
        # Return the full structure for visualization
        return result
    except Exception as e:
        return {"error": str(e), "rawResult": result}

if __name__ == "__main__":
    mcp.run(transport="stdio")