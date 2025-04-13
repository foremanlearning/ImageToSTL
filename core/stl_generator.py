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
        
        # Create trimesh object
        self.mesh = trimesh.Trimesh(vertices=vertices, faces=faces)
        
        # Attempt to repair mesh issues immediately after creation
        if not self.mesh.is_watertight:
            # Merge vertices that are very close to each other
            # This helps eliminate non-manifold edges caused by duplicate vertices
            self.mesh.merge_vertices(merge_tolerance=1e-5)
            
            # Fix face normals to be consistent
            self.mesh.fix_normals()
            
            # Remove any faces with zero area (degenerate faces)
            areas = self.mesh.area_faces
            valid_faces = areas > 1e-8
            if not np.all(valid_faces):
                self.mesh.update_faces(valid_faces)
                print(f"Removed {np.sum(~valid_faces)} degenerate faces")
            
            # Apply additional fixes for non-manifold edges
            self.mesh = self.enforce_edge_consistency(self.mesh)
        
        # Update triangle count after repairs
        self.triangle_count = len(self.mesh.faces)
        
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
            # Fix non-manifold edges before exporting
            if not self.mesh.is_watertight:
                print("Mesh is not watertight, attempting to fix...")
                # First, merge duplicate vertices that might be causing issues
                self.mesh.merge_vertices(merge_tolerance=1e-5)
                
                # Fix normals to ensure consistent orientation
                self.mesh.fix_normals()
                
                # Fill holes if any exist
                if hasattr(self.mesh, 'holes') and callable(getattr(self.mesh, 'holes')):
                    holes = self.mesh.holes()
                    if len(holes) > 0:
                        print(f"Fixing {len(holes)} holes in the mesh")
                        self.mesh.fill_holes()
                
                # Remove duplicate or degenerate faces
                if len(self.mesh.faces) > 0:
                    unique_faces = np.unique(np.sort(self.mesh.faces, axis=1), axis=0)
                    if len(unique_faces) < len(self.mesh.faces):
                        print(f"Removed {len(self.mesh.faces) - len(unique_faces)} duplicate faces")
                        self.mesh.faces = unique_faces
                
                # Apply advanced repair using the edge consistency method
                self.mesh = self.enforce_edge_consistency(self.mesh)
                
                # Final validation
                if not self.mesh.is_watertight:
                    print("Warning: Mesh may still have non-manifold edges after repair")
                else:
                    print("Mesh successfully repaired to be watertight")
            
            # Export the mesh (repaired if needed)
            self.mesh.export(file_path)
            
            # Report triangle count in exported file
            print(f"Exported STL with {len(self.mesh.faces)} triangles")
            # Update the triangle count
            self.triangle_count = len(self.mesh.faces)
            
            return True
        except Exception as e:
            print(f"Error saving STL: {e}")
            return False
            
    def get_mesh(self):
        """Return the current mesh object."""
        return self.mesh

    def enforce_edge_consistency(self, mesh):
        """
        Ensure edge consistency across the mesh to eliminate non-manifold edges.
        This function attempts to fix edges shared by more than two faces.
        
        Parameters:
        - mesh: A trimesh object to check and fix
        
        Returns:
        - Fixed trimesh object
        """
        # First check if there are any non-manifold edges
        if mesh.is_watertight:
            return mesh  # Already good
        
        # Get edges that appear more than twice (non-manifold)
        edge_faces = mesh.edges_face
        edge_counts = np.bincount(mesh.edges.flatten())
        problem_vertex_indices = np.where(edge_counts > 2)[0]
        
        if len(problem_vertex_indices) == 0:
            # No problematic vertices found
            return mesh
            
        print(f"Found {len(problem_vertex_indices)} vertices involved in non-manifold edges")
        
        # Create a small offset for problematic vertices
        # This effectively duplicates vertices that are causing non-manifold edges
        vertices = mesh.vertices.copy()
        offset_factor = 1e-5  # Small enough not to be visible but enough to separate vertices
        
        # Create new faces list to build the mesh with fixed topology
        new_faces = []
        vertex_map = {}  # Map to keep track of duplicated vertices
        next_vertex_id = len(vertices)
        
        # Process each face
        for face in mesh.faces:
            new_face = face.copy()
            
            # Check if any vertex in this face is problematic
            for i, vertex_id in enumerate(face):
                if vertex_id in problem_vertex_indices:
                    # Create a key based on the face and vertex position
                    face_key = tuple(sorted(face))
                    vertex_key = (face_key, vertex_id)
                    
                    if vertex_key not in vertex_map:
                        # Create a slightly offset duplicate vertex
                        vertex_pos = vertices[vertex_id]
                        new_vertex = vertex_pos + np.random.uniform(-offset_factor, offset_factor, 3)
                        vertices = np.vstack([vertices, new_vertex])
                        vertex_map[vertex_key] = next_vertex_id
                        next_vertex_id += 1
                    
                    # Use the duplicated vertex instead
                    new_face[i] = vertex_map[vertex_key]
                    
            new_faces.append(new_face)
        
        # Create new mesh with fixed vertices
        fixed_mesh = trimesh.Trimesh(vertices=vertices, faces=new_faces)
        
        # Ensure normals are consistent
        fixed_mesh.fix_normals()
        
        # Final cleanup - merge vertices that ended up too close
        fixed_mesh.merge_vertices(merge_tolerance=1e-6)
        
        return fixed_mesh