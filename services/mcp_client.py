"""OpenAI GPT client for chatbot functionality.

Provides chat capabilities using OpenAI's GPT API with conversation
history management and error handling. Integrates with Grasshopper MCP
server for computational tools.
"""

import openai
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import streamlit as st
from .grasshopper_mcp import DirectGrasshopperClient


class MCPClient:
    """OpenAI GPT client for chat functionality.
    
    Handles API key configuration, message sending, and conversation context
    management for the chatbot interface.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.client = None
        self._connected = False
        self.grasshopper_client = DirectGrasshopperClient()
        self.mcp_tools_available = self.grasshopper_client.available
        
        if api_key:
            self.connect()

    def connect(self):
        """Initialize the OpenAI client with the provided API key."""
        if not self.api_key:
            raise ValueError("API key is required to connect to OpenAI")
        
        try:
            self.client = openai.OpenAI(api_key=self.api_key)
            self._connected = True
        except Exception as e:
            self._connected = False
            raise ConnectionError(f"Failed to connect to OpenAI: {str(e)}")

    def is_connected(self) -> bool:
        return self._connected and self.client is not None

    def send_message(self, prompt: str, conversation_history: Optional[List[Dict[str, str]]] = None) -> str:
        """Send a message to GPT and return the response.

        Parameters
        ----------
        prompt: str
            User prompt to send.
        conversation_history: Optional[List[Dict[str, str]]]
            Previous conversation messages for context.

        Returns
        -------
        str
            GPT's response to the prompt.
        """
        # Debug information
        if not self.api_key:
            return "🔍 Debug: No API key provided to MCPClient"
        
        if not self.is_connected():
            if self.api_key:
                try:
                    self.connect()
                except Exception as e:
                    return f"🔍 Debug: Failed to connect - {str(e)}"
            else:
                return "⚠️ Please configure your OpenAI API key to chat with GPT."

        try:
            # Prepare messages for GPT
            messages = [
                {
                    "role": "system",
                    "content": "You are a helpful assistant for a structural engineering application called Anthill. You can help users with questions about structural analysis, embodied carbon calculations, and interpreting 3D mesh models. Be concise and technical when appropriate."
                }
            ]
            
            # Add conversation history (skip system messages, only user/assistant)
            if conversation_history:
                for msg in conversation_history[-10:]:  # Keep last 10 messages for context
                    if msg["role"] in ["user", "assistant"]:
                        messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })
            
            # Add current prompt
            messages.append({
                "role": "user", 
                "content": prompt
            })

            # Get available MCP tools for function calling
            tools = []
            if self.mcp_tools_available:
                tools = self.grasshopper_client.get_available_tools()
            
            # Call OpenAI API with or without tools
            if tools:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    max_tokens=1500,
                    temperature=0.7
                )
            else:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    max_tokens=1500,
                    temperature=0.7
                )
            
            # Handle function calls
            message = response.choices[0].message
            
            if message.tool_calls:
                return self._handle_tool_calls(message, messages)
            else:
                return message.content

        except openai.AuthenticationError:
            return "❌ Authentication failed. Please check your OpenAI API key."
        except openai.RateLimitError:
            return "⏳ Rate limit exceeded. Please wait a moment and try again."
        except Exception as e:
            return f"⚠️ Error communicating with GPT: {str(e)}"

    def _handle_tool_calls(self, message, messages: List[Dict[str, Any]]) -> str:
        """Handle OpenAI function calls by executing them via MCP."""
        try:
            # Add the assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    } for tc in message.tool_calls
                ]
            })
            
            # Execute each tool call
            for tool_call in message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)
                
                try:
                    # Call the MCP tool
                    result = self.grasshopper_client.call_tool(function_name, arguments)
                    print('result', result)

                    # Persist scene output for visualization if available
                    self._register_scene_result(result)

                    # Add tool result to messages
                    tool_content = self._format_tool_content(result)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_content
                    })
                    
                except Exception as e:
                    # Add error result
                    messages.append({
                        "role": "tool", 
                        "tool_call_id": tool_call.id,
                        "content": f"Error executing {function_name}: {str(e)}"
                    })
            
            # Get final response from OpenAI with tool results
            final_response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=1500,
                temperature=0.7
            )
            
            return final_response.choices[0].message.content
            
        except Exception as e:
            return f"⚠️ Error handling tool calls: {str(e)}"
    
    def update_api_key(self, api_key: str):
        """Update the API key and reconnect."""
        self.api_key = api_key
        self.client = None
        self._connected = False
        if api_key:
            self.connect()

    def _register_scene_result(self, result: Any) -> None:
        if not isinstance(result, dict):
            return

        scene_data = None
        if isinstance(result.get("scene"), (dict, list)):
            scene_data = result["scene"]
        elif "StructuralFrame" in result:
            scene_data = {"StructuralFrame": result["StructuralFrame"]}

        if scene_data is None:
            return

        cache_dir = Path(".cache")
        cache_dir.mkdir(exist_ok=True)
        scene_path = cache_dir / "compute_scene.json"
        try:
            scene_path.write_text(json.dumps(scene_data, indent=2), encoding="utf-8")
        except TypeError:
            # Fallback to serializer that converts unsupported types to strings
            scene_path.write_text(
                json.dumps(scene_data, indent=2, default=str),
                encoding="utf-8",
            )

        st.session_state["generated_scene_path"] = str(scene_path)
        st.session_state["generated_scene_label"] = "Grasshopper MCP"
        if "totalCarbonEmission" in result:
            st.session_state["generated_scene_total"] = result["totalCarbonEmission"]
        st.session_state["scene_ready"] = True

    def _format_tool_content(self, result: Any) -> str:
        if isinstance(result, (dict, list)):
            try:
                return json.dumps(result, indent=2)
            except TypeError:
                return json.dumps(result, default=str)
        return str(result)
