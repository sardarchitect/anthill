from pathlib import Path
from utils.json_loader import load_scene
from components.mesh_viewer import MeshViewer
from components.charts import ChartsBuilder

def main():
    path = Path('Test 01.json')
    scene = load_scene(path)
    print('Meshes:', len(scene.meshes))
    print('Total vertices:', scene.total_vertices())
    print('Total faces:', scene.total_faces())
    viewer = MeshViewer(scene)
    fig = viewer.build_figure()
    print('Viewer traces:', len(fig.data))
    charts = ChartsBuilder(scene)
    print('Faces bar traces:', len(charts.faces_bar().data))
    print('Vertices bar traces:', len(charts.vertices_bar().data))
    print('Volume scatter traces:', len(charts.volume_scatter().data))
    print('VALIDATION SUCCESS')

if __name__ == '__main__':
    main()
