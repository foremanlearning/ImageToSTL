import numpy as np
from PIL import Image
import matplotlib.colors as mcolors
from scipy.cluster.vq import kmeans, vq
from scipy.ndimage import gaussian_filter

class ImageProcessor:
    """
    Handles image processing operations for the Image to STL converter.
    Responsible for loading images, color analysis, and height mapping.
    """
    
    def __init__(self):
        self.image = None
        self.image_array = None
        self.height_map = None
        self.color_height_mapping = {}  # Maps color values to heights
        
    def load_image(self, image_path):
        """Load an image from the specified path."""
        try:
            self.image = Image.open(image_path)
            # Convert to RGBA to ensure we handle transparency consistently
            if self.image.mode != 'RGBA':
                self.image = self.image.convert('RGBA')
            
            self.image_array = np.array(self.image)
            return True
        except Exception as e:
            print(f"Error loading image: {e}")
            return False
    
    def get_image_dimensions(self):
        """Return the dimensions of the loaded image."""
        if self.image is None:
            return (0, 0)
        return self.image.size
    
    def select_color_range(self, target_color, tolerance=10):
        """
        Select pixels within a color range of the target color.
        Returns a boolean mask of matching pixels.
        """
        if self.image_array is None:
            return None
            
        # Convert target_color to RGB numpy array for comparison
        target_rgb = np.array(mcolors.to_rgb(target_color)) * 255
        
        # Create mask for pixels within tolerance of target color (using Euclidean distance)
        r, g, b = self.image_array[:,:,0], self.image_array[:,:,1], self.image_array[:,:,2]
        color_distance = np.sqrt(
            (r - target_rgb[0])**2 + 
            (g - target_rgb[1])**2 + 
            (b - target_rgb[2])**2
        )
        
        mask = color_distance <= tolerance
        return mask
    
    def update_height_mapping(self, color, height_value):
        """Update the mapping of color to height."""
        self.color_height_mapping[color] = height_value
        
    def auto_assign_heights_by_brightness(self):
        """
        Automatically assign heights based on image brightness.
        Brighter pixels will be higher.
        """
        if self.image_array is None:
            return
            
        # Calculate brightness (average of RGB)
        brightness = np.mean(self.image_array[:,:,:3], axis=2)
        
        # Normalize to 0-1 range
        min_val = np.min(brightness)
        max_val = np.max(brightness)
        if max_val > min_val:
            self.height_map = (brightness - min_val) / (max_val - min_val)
        else:
            self.height_map = np.zeros_like(brightness)
    
    def generate_height_map_from_colors(self, transparency_threshold=128):
        """
        Generate a height map based on the color-to-height mapping.
        Transparent areas (below threshold) will be set to 0 height.
        """
        if self.image_array is None or not self.color_height_mapping:
            return None
            
        height_map = np.zeros(self.image_array.shape[:2], dtype=float)
        
        # Get alpha channel for transparency handling
        alpha = self.image_array[:,:,3]
        transparent_mask = alpha < transparency_threshold
        
        # Apply each color mapping
        for color, height in self.color_height_mapping.items():
            mask = self.select_color_range(color)
            if mask is not None:
                height_map[mask] = height
        
        # Set transparent pixels to zero height
        height_map[transparent_mask] = 0
        
        self.height_map = height_map
        return height_map
    
    def invert_heights(self):
        """Invert the height map."""
        if self.height_map is not None:
            # Find min and max for proper inversion
            min_val = np.min(self.height_map)
            max_val = np.max(self.height_map)
            
            # Invert heights
            self.height_map = max_val + min_val - self.height_map
    
    def adjust_resolution(self, scale_factor):
        """
        Adjust the resolution of the height map by scaling.
        scale_factor: < 1 reduces resolution, > 1 increases resolution
        """
        if self.height_map is None or scale_factor <= 0:
            return
            
        # Resize using PIL for better quality
        h, w = self.height_map.shape
        new_h, new_w = int(h * scale_factor), int(w * scale_factor)
        
        height_map_image = Image.fromarray(self.height_map)
        resized_map = height_map_image.resize((new_w, new_h), Image.BICUBIC)
        
        self.height_map = np.array(resized_map)
        
    def apply_smoothing(self, smoothing_factor=1.0):
        """Apply Gaussian smoothing to the height map."""
        if self.height_map is None:
            return
            
        # Apply gaussian filter for smoothing
        sigma = smoothing_factor
        self.height_map = gaussian_filter(self.height_map, sigma)
    
    def extract_dominant_colors(self, num_colors=5):
        """
        Extract dominant colors from the loaded image using K-means clustering.
        
        Args:
            num_colors: Number of color clusters to extract
            
        Returns:
            List of RGB colors as [r,g,b] arrays
        """
        if self.image_array is None:
            return None
        
        try:
            # Reshape the image data into a list of RGB pixels
            pixels = self.image_array[:,:,:3].reshape(-1, 3)
            
            # Filter out transparent pixels (if alpha < 128)
            if self.image_array.shape[2] == 4:  # If image has alpha channel
                alpha = self.image_array[:,:,3].reshape(-1)
                pixels = pixels[alpha > 128]
            
            # If no valid pixels remain, return empty list
            if len(pixels) == 0:
                return []
                
            # Perform k-means clustering
            centroids, _ = kmeans(pixels.astype(float), num_colors)
            
            # Sort colors by brightness (sum of RGB values)
            centroids = sorted(centroids, key=lambda x: sum(x), reverse=True)
            
            return centroids
            
        except Exception as e:
            print(f"Error extracting colors: {e}")
            return []