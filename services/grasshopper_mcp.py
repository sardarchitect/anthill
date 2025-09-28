"""Simple Grasshopper compute integration.

Direct integration with the Grasshopper compute functions without MCP overhead.
"""

import importlib.util
import sys
from pathlib import Path
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class DirectGrasshopperClient:
    """Direct client for Grasshopper compute functions."""
    
    def __init__(self):
        self.compute_module = None
        self.available = False
        self._load_compute_module()
    
    def _load_compute_module(self):
        """Load the compute_mcp module directly."""
        try:
            # Import compute_mcp module
            import compute_mcp
            self.compute_module = compute_mcp
            self.available = True
            logger.info("Successfully loaded Grasshopper compute module")
        except ImportError as e:
            logger.error(f"Failed to import compute_mcp: {e}")
            self.available = False
        except Exception as e:
            logger.error(f"Error loading compute module: {e}")
            self.available = False
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get available tools formatted for OpenAI function calling."""
        if not self.available:
            return []
        
        # Define the add_numbers_via_compute function for OpenAI
        function_schema = {
            "description": "Calculate embodied carbon of a building given bay width, bay height, and story height",
            "parameters": {
                "type": "object",
                "properties": {
                    "xBaySize": {
                        "type": "number",
                        "description": "Bay width in X direction"
                    },
                    "yBaySize": {
                        "type": "number",
                        "description": "Bay width in Y direction"
                    },
                    "storyHeight": {
                        "type": "number",
                        "description": "story height"
                    }
                },
                "required": ["xBaySize", "yBaySize", "storyHeight"]
            }
        }

        tools = [
            {
                "type": "function",
                "function": {"name": "calculateBuildingEmbodiedCarbon", **function_schema}
            },
            {
                "type": "function",
                "function": {"name": "compute_mcp", **function_schema}
            }
        ]
        
        return tools
    
    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a Grasshopper compute function."""
        if not self.available:
            raise RuntimeError("Grasshopper compute module not available")
        
        if tool_name in {"calculateBuildingEmbodiedCarbon", "compute_mcp"}:
            try:
                xBaySize = float(arguments.get("xBaySize", 0))
                yBaySize = float(arguments.get("yBaySize", 0))
                storyHeight = float(arguments.get("storyHeight", 0))
                
                # Call the compute function directly and return structured bundle
                result = self.compute_module.call_compute(xBaySize, yBaySize, storyHeight)
                return result
                
            except Exception as e:
                raise RuntimeError(f"Error calling Grasshopper compute: {str(e)}")
        else:
            raise ValueError(f"Unknown tool: {tool_name}")


# Alias for backward compatibility
SyncGrasshopperMCPClient = DirectGrasshopperClient