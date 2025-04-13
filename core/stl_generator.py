import numpy as np
import trimesh
from stl.mesh import Mesh  # Updated import to use the correct numpy-stl package

class STLGenerator:
    """
    Handles the generation of 3D STL models from height maps.
    """
    
    def __init__(self):
        self.mesh = None
        self.triangle_count = 0
        
    def create_mesh_from_height_map(self, height_map, base_thickness=1.0, scale_factor=1.0, max_triangles=None, no_base=False):
        """
        Convert a height map to a 3D mesh.
        
        Parameters:
        - height_map: 2D numpy array representing heights
        - base_thickness: Thickness of the base in units
        - scale_factor: Scale factor to apply to the final mesh
        - max_triangles: Maximum number of triangles to generate (None for no limit)
        - no_base: If True, only the surface will be generated without a base
        
        Returns:
        - A trimesh object representing the 3D model
        """
        if height_map is None:
            return None
            
        # Get dimensions
        height, width = height_map.shape
        
        # Calculate target downsample factor if max_triangles is specified
        # Adjust the triangle estimate based on whether we're creating a base or not
        downsample_factor = 1
        if no_base:
            estimated_triangles = 2 * (width-1) * (height-1)  # Only top surface triangles
        else:
            estimated_triangles = 2 * (width-1) * (height-1) * 3  # Top, bottom, sides
        
        if max_triangles is not None and max_triangles > 0 and estimated_triangles > max_triangles:
            # Calculate the factor needed to get below max_triangles
            target_factor = np.sqrt(max_triangles / estimated_triangles) * 0.9  # 10% safety margin
            
            # Find the nearest integer downsample factor (must be at least 1)
            downsample_factor = max(1, int(1 / target_factor))
            
            # Downsample the height map
            if downsample_factor > 1:
                from PIL import Image
                height_map_img = Image.fromarray(height_map)
                new_width = width // downsample_factor
                new_height = height // downsample_factor
                
                # Ensure minimum dimensions
                new_width = max(2, new_width)
                new_height = max(2, new_height)
                
                downsampled = height_map_img.resize((new_width, new_height), Image.BICUBIC)
                height_map = np.array(downsampled)
                height, width = height_map.shape
        
        # Create vertex array from height map
        vertices = []
        
        # Create top vertices from height map
        for y in range(height):
            for x in range(width):
                # If no base, don't add base_thickness
                if no_base:
                    z = height_map[y, x]
                else:
                    z = height_map[y, x] + base_thickness
                vertices.append([x * scale_factor, y * scale_factor, z * scale_factor])
        
        # If creating a base, add bottom vertices
        if not no_base:
            # Create bottom vertices (flat base)
            for y in range(height):
                for x in range(width):
                    vertices.append([x * scale_factor, y * scale_factor, 0.0])
        
        vertices = np.array(vertices)
        
        # Create faces
        faces = []
        
        # Top faces (height map surface)
        for y in range(height - 1):
            for x in range(width - 1):
                v1 = y * width + x
                v2 = y * width + (x + 1)
                v3 = (y + 1) * width + x
                v4 = (y + 1) * width + (x + 1)
                
                # Create two triangles for each quad
                faces.append([v1, v2, v3])
                faces.append([v2, v4, v3])
        
        # If creating a base, add bottom and side faces
        if not no_base:
            # Bottom faces (base)
            bottom_offset = height * width
            for y in range(height - 1):
                for x in range(width - 1):
                    v1 = bottom_offset + y * width + x
                    v2 = bottom_offset + y * width + (x + 1)
                    v3 = bottom_offset + (y + 1) * width + x
                    v4 = bottom_offset + (y + 1) * width + (x + 1)
                    
                    # Create two triangles for each quad (opposite direction to top)
                    faces.append([v1, v3, v2])
                    faces.append([v2, v3, v4])
            
            # Side faces - front and back
            for x in range(width - 1):
                # Front side
                v1 = x
                v2 = x + 1
                v3 = bottom_offset + x
                v4 = bottom_offset + x + 1
                faces.append([v1, v3, v2])
                faces.append([v2, v3, v4])
                
                # Back side
                v1 = (height - 1) * width + x
                v2 = (height - 1) * width + x + 1
                v3 = bottom_offset + (height - 1) * width + x
                v4 = bottom_offset + (height - 1) * width + x + 1
                faces.append([v1, v2, v3])
                faces.append([v2, v4, v3])
            
            # Side faces - left and right
            for y in range(height - 1):
                # Left side
                v1 = y * width
                v2 = (y + 1) * width
                v3 = bottom_offset + y * width
                v4 = bottom_offset + (y + 1) * width
                faces.append([v1, v2, v3])
                faces.append([v2, v4, v3])
                
                # Right side
                v1 = y * width + (width - 1)
                v2 = (y + 1) * width + (width - 1)
                v3 = bottom_offset + y * width + (width - 1)
                v4 = bottom_offset + (y + 1) * width + (width - 1)
                faces.append([v1, v3, v2])
                faces.append([v2, v3, v4])
            
        faces = np.array(faces)
        
        # Store the triangle count
        self.triangle_count = len(faces)
        
        # Create trimesh object
        self.mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
        
        return self.mesh
    
    def get_triangle_count(self):
        """Get the number of triangles in the current mesh."""
        if self.mesh is None:
            return 0
        return self.triangle_count
    
    def save_stl(self, file_path):
        """Save the current mesh as an STL file."""
        if self.mesh is None:
            return False
            
        try:
            self.mesh.export(file_path)
            return True
        except Exception as e:
            print(f"Error saving STL: {e}")
            return False
            
    def get_mesh(self):
        """Return the current mesh object."""
        return self.mesh