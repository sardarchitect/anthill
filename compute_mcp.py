import base64
import requests
from mcp.server.fastmcp import FastMCP
import json

# Optional typing helpers
from typing import Any, Dict

mcp = FastMCP("EmbodiedCarbonBuildingCalculator")

# Path to your Grasshopper definition
GH_PATH = r"C:\Users\sxmoore\Source\Hackathon\AntHill\Streamlit\anthill\grasshopper\antHill_Building Frame.gh"
COMPUTE_URL = "http://localhost:8081/grasshopper"

# Read and base64 encode GH definition once at startup
with open(GH_PATH, "rb") as f:
    gh_bytes = f.read()
encoded_def = base64.b64encode(gh_bytes).decode("utf-8")

def call_compute(xBaySize: float, yBaySize: float, storyHeight: float) -> Dict[str, Any]:
    """Send request to Rhino Compute with bay sizes and story height.

    Returns a bundle containing the parsed scene JSON plus useful metadata so the
    front-end can immediately visualise the generated structure.
    """

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
    response.raise_for_status()
    res = response.json()
    data = res["values"][0]["InnerTree"]["{0}"][0]["data"]
    parsed = json.loads(data)

    structural_frame = parsed.get("StructuralFrame") if isinstance(parsed, dict) else None
    total_carbon = None
    if isinstance(structural_frame, dict):
        total_carbon = structural_frame.get("TotalCO2")
    elif isinstance(structural_frame, list):
        for entry in structural_frame:
            if isinstance(entry, dict) and "TotalCO2" in entry:
                total_carbon = entry.get("TotalCO2")
                break

    bundle: Dict[str, Any] = {
        "scene": parsed,
        "inputs": {
            "xBaySize": xBaySize,
            "yBaySize": yBaySize,
            "storyHeight": storyHeight,
        }
    }
    if total_carbon is not None:
        bundle["totalCarbonEmission"] = total_carbon

    return bundle

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
    bundle = call_compute(xBaySize, yBaySize, storyHeight)

    scene = bundle.get("scene", {})
    total_carbon = bundle.get("totalCarbonEmission")

    if total_carbon is None and isinstance(scene, dict):
        try:
            structural_frame = scene.get("StructuralFrame")
            if isinstance(structural_frame, dict):
                total_carbon = structural_frame.get("TotalCO2")
        except Exception:
            total_carbon = None

    return {
        "inputs": bundle.get("inputs", {}),
        "totalCarbonEmission": total_carbon,
        "scene": scene,
    }

if __name__ == "__main__":
    mcp.run(transport="stdio")