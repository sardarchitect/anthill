## Anthill Prototype

Streamlit prototype for structural embodied carbon analysis on massing models.

### Structure

```
app.py                # Streamlit entrypoint
models/               # Domain models (mesh geometry & scene)
services/             # External integration services (MCP client stub)
utils/                # Parsers & helpers
components/           # UI components (chat, mesh viewer, charts)
```

### Roadmap
1. Implement mesh domain dataclasses
2. Implement JSON parser for Three.js-like export
3. Build chat interface w/ upload
4. 3D mesh visualization (Plotly)
5. Analytical charts (counts, bounding boxes, volumes)

### Running
1. Install dependencies
```
pip install -r requirements.txt
```
2. Launch
```
streamlit run app.py
```

Upload a JSON mesh export (or the included `Test 01.json` is used as default) and interact via the chat panel.
