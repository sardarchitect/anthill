import base64
import requests
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("AddTwoNumbersCompute")

# Path to your Grasshopper definition
GH_PATH = "D:/Source/anthill/grasshopper/AddTwoNumbers.gh"
COMPUTE_URL = "http://localhost:5000/grasshopper"

# Read and base64 encode GH definition once at startup
with open(GH_PATH, "rb") as f:
    gh_bytes = f.read()
encoded_def = base64.b64encode(gh_bytes).decode("utf-8")

def call_compute(num1: float, num2: float):
    """Send request to Rhino Compute with num1 and num2 inputs"""
    payload = {
        "algo": encoded_def,
        "pointer": None,
        "values": [
            {
                "ParamName": "num1",
                "InnerTree": {
                    "{0}": [
                        {"type": "System.Double", "data": str(num1)}
                    ]
                }
            },
            {
                "ParamName": "num2",
                "InnerTree": {
                    "{0}": [
                        {"type": "System.Double", "data": str(num2)}
                    ]
                }
            }
        ]
    }

    res = requests.post(COMPUTE_URL, json=payload)
    res.raise_for_status()
    response = res.json()
    data = response["values"][0]["InnerTree"]["{0}"][0]["data"]
    num = float(data.strip('"'))
    return num

@mcp.tool()
async def add_numbers_via_compute(
    num1: int | float,
    num2: int | float
) -> float:
    """Add two numbers using a Grasshopper definition on Rhino Compute.
    
    Args:
        num1: First number.
        num2: Second number.
    """
    result = call_compute(num1, num2)

    # Extract Grasshopper output values
    try:
        gh_values = result.get("values", [])
        # usually the computed value is in values[0]["InnerTree"]["{0}"][0]["data"]
        sum_val = gh_values[0]["InnerTree"]["{0}"][0]["data"]
        return float(sum_val)
    except Exception:
        # fallback: return raw response
        return result

if __name__ == "__main__":
    mcp.run(transport="stdio")