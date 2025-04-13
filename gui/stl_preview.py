import numpy as np
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt

# Import for 3D visualization
try:
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

class STLPreviewWidget(QWidget):
    """
    Widget for displaying a 3D preview of the STL model.
    Uses matplotlib for 3D visualization.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.mesh = None
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        
        if MATPLOTLIB_AVAILABLE:
            self.figure = Figure(figsize=(5, 5), dpi=100)
            self.canvas = FigureCanvas(self.figure)
            layout.addWidget(self.canvas)
            
            # Create initial empty 3D plot
            self.create_empty_plot()
        else:
            # Fallback if matplotlib is not available
            label = QLabel("Matplotlib is required for 3D preview.\nPlease install matplotlib.")
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label)
    
    def create_empty_plot(self):
        """Create an empty 3D plot."""
        self.figure.clear()
        self.ax = self.figure.add_subplot(111, projection='3d')
        self.ax.set_xlabel('X')
        self.ax.set_ylabel('Y')
        self.ax.set_zlabel('Z')
        self.ax.set_title('STL Preview')
        self.canvas.draw()
    
    def display_mesh(self, mesh):
        """
        Display a 3D mesh using matplotlib.
        
        Args:
            mesh: A trimesh object to display
        """
        if not MATPLOTLIB_AVAILABLE:
            return
            
        # Clear the previous plot
        self.figure.clear()
        self.ax = self.figure.add_subplot(111, projection='3d')
        
        # Get mesh data
        vertices = mesh.vertices
        faces = mesh.faces
        
        # Plot the 3D triangular mesh
        x = vertices[:, 0]
        y = vertices[:, 1]
        z = vertices[:, 2]
        
        # Create a more efficient visualization by plotting the triangles
        # This is more efficient than plotting all faces with plot_trisurf
        tri_indices = faces
        
        # Plot the triangular mesh
        self.ax.plot_trisurf(x, y, z, triangles=tri_indices, cmap='viridis', 
                            edgecolor='none', alpha=0.9)
        
        # Set labels and title
        self.ax.set_xlabel('X')
        self.ax.set_ylabel('Y')
        self.ax.set_zlabel('Z')
        self.ax.set_title('STL Preview')
        
        # Make the aspect ratio equal
        self.ax.set_box_aspect([1, 1, 1])
        
        # Update the canvas
        self.canvas.draw()
        
    def clear_preview(self):
        """Clear the preview."""
        if MATPLOTLIB_AVAILABLE:
            self.create_empty_plot()