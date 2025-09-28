import base64
import requests
from mcp.server.fastmcp import FastMCP
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
    print('response', response)
    res = response.json()
    data = res["values"][0]["InnerTree"]["{0}"][0]["data"]
    print('data', data)
    parsed = json.loads(data)
    print('parsed', parsed)
    return parsed

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
        totalC02 = result["StructuralFrame"]["TotalCO2"]

        return {
            "totalCarbonEmission": totalC02,
        }
    except Exception as e:
        return {"error": str(e), "rawResult": result}

if __name__ == "__main__":
    mcp.run(transport="stdio")