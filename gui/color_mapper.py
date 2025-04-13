import os
import json
import numpy as np
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
                           QLabel, QPushButton, QColorDialog, QDoubleSpinBox,
                           QSlider, QListWidget, QListWidgetItem, QMessageBox,
                           QSpinBox, QInputDialog)
from PyQt5.QtGui import QColor, QPixmap, QIcon
from PyQt5.QtCore import Qt, pyqtSignal

class ColorMappingWidget(QGroupBox):
    """
    Widget for mapping colors to heights.
    Allows users to pick colors from the image and assign heights to them.
    """
    
    colorMappingChanged = pyqtSignal()
    
    def __init__(self, image_processor, parent=None):
        super().__init__("Color to Height Mapping", parent)
        self.image_processor = image_processor
        self.mappings = {}  # Dictionary to store color-to-height mappings
        self.setup_ui()
    
    def setup_ui(self):
        """Set up the UI components."""
        layout = QVBoxLayout(self)
        
        # Color picker section
        picker_layout = QHBoxLayout()
        
        # Current color display
        self.current_color_label = QLabel()
        self.current_color_label.setFixedSize(40, 40)
        self.current_color_label.setStyleSheet("background-color: #FFFFFF; border: 1px solid black;")
        picker_layout.addWidget(self.current_color_label)
        
        # Color picker button
        self.pick_color_btn = QPushButton("Pick Color")
        self.pick_color_btn.clicked.connect(self.pick_color)
        picker_layout.addWidget(self.pick_color_btn)
        
        # Color tolerance slider
        tolerance_layout = QHBoxLayout()
        tolerance_layout.addWidget(QLabel("Color Tolerance:"))
        self.tolerance_slider = QSlider(Qt.Horizontal)
        self.tolerance_slider.setRange(0, 100)
        self.tolerance_slider.setValue(10)
        tolerance_layout.addWidget(self.tolerance_slider)
        self.tolerance_value = QLabel("10")
        tolerance_layout.addWidget(self.tolerance_value)
        self.tolerance_slider.valueChanged.connect(lambda v: self.tolerance_value.setText(str(v)))
        
        # Height assignment
        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("Height:"))
        self.height_spin = QDoubleSpinBox()
        self.height_spin.setRange(0, 100)
        self.height_spin.setValue(1.0)
        self.height_spin.setSingleStep(0.1)
        height_layout.addWidget(self.height_spin)
        
        # Add mapping button
        self.add_mapping_btn = QPushButton("Add Mapping")
        self.add_mapping_btn.clicked.connect(self.add_mapping)
        
        # Auto-assign button
        self.auto_assign_btn = QPushButton("Auto-Assign by Brightness")
        self.auto_assign_btn.clicked.connect(self.auto_assign)
        
        # Add new button for auto add colors
        self.auto_add_colors_btn = QPushButton("Auto Add Colors in Ranges")
        self.auto_add_colors_btn.clicked.connect(self.auto_add_colors)
        
        # Mapping list
        self.mapping_list = QListWidget()
        self.mapping_list.setSelectionMode(QListWidget.SingleSelection)
        self.mapping_list.setMinimumHeight(100)
        
        # Remove mapping button
        self.remove_mapping_btn = QPushButton("Remove Mapping")
        self.remove_mapping_btn.clicked.connect(self.remove_mapping)
        
        # Add all widgets to main layout
        layout.addLayout(picker_layout)
        layout.addLayout(tolerance_layout)
        layout.addLayout(height_layout)
        layout.addWidget(self.add_mapping_btn)
        layout.addWidget(self.auto_assign_btn)
        layout.addWidget(self.auto_add_colors_btn)  # Add new button
        layout.addWidget(self.mapping_list)
        layout.addWidget(self.remove_mapping_btn)
    
    def pick_color(self):
        """Open color picker dialog to select a color."""
        color = QColorDialog.getColor(parent=self)
        if color.isValid():
            self.current_color_label.setStyleSheet(f"background-color: {color.name()}; border: 1px solid black;")
    
    def add_mapping(self):
        """Add a new color-to-height mapping."""
        # Get the currently selected color
        color_style = self.current_color_label.styleSheet()
        color_name = color_style.split("background-color:")[1].split(";")[0].strip()
        
        # Get the height value
        height = self.height_spin.value()
        
        # Add to mappings
        self.mappings[color_name] = height
        
        # Update the image processor
        self.image_processor.update_height_mapping(color_name, height)
        
        # Add to list widget
        self.update_mapping_list()
        
        # Emit signal that mappings have changed
        self.colorMappingChanged.emit()
    
    def remove_mapping(self):
        """Remove the selected mapping from the list."""
        selected_items = self.mapping_list.selectedItems()
        if not selected_items:
            return
            
        selected_item = selected_items[0]
        color_name = selected_item.data(Qt.UserRole)
        
        # Remove from mappings
        if color_name in self.mappings:
            del self.mappings[color_name]
            
            # Update the list
            self.update_mapping_list()
            
            # Emit signal that mappings have changed
            self.colorMappingChanged.emit()
    
    def update_mapping_list(self):
        """Update the list widget with current mappings."""
        self.mapping_list.clear()
        
        for color_name, height in self.mappings.items():
            # Create a colored square icon
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(color_name))
            
            # Create list item
            item = QListWidgetItem(QIcon(pixmap), f"{color_name} → Height: {height}")
            item.setData(Qt.UserRole, color_name)
            
            self.mapping_list.addItem(item)
    
    def update_image(self):
        """Called when a new image is loaded."""
        # Reset mappings
        self.mappings = {}
        self.update_mapping_list()
    
    def has_mappings(self):
        """Check if any mappings exist."""
        return len(self.mappings) > 0
    
    def auto_assign(self):
        """Automatically assign heights based on image brightness."""
        if not self.image_processor.image:
            QMessageBox.information(self, "No Image", "Please load an image first")
            return
            
        # Call the image processor's auto-assign method
        self.image_processor.auto_assign_heights_by_brightness()
        
        # Clear existing mappings since we're using auto brightness
        self.mappings = {}
        self.update_mapping_list()
        
        # Let the main window know we're using auto assignment
        QMessageBox.information(self, "Auto-Assign", 
                               "Heights automatically assigned based on brightness.\n"
                               "Click 'Generate STL' to create the model.")
        self.colorMappingChanged.emit()
    
    def auto_add_colors(self):
        """Automatically identify and add distinct color ranges from the image."""
        if not self.image_processor.image:
            QMessageBox.information(self, "No Image", "Please load an image first")
            return
            
        # Ask user for number of color ranges to detect
        num_colors, ok = QInputDialog.getInt(
            self, "Number of Colors", 
            "How many distinct color ranges to identify?",
            value=5, min=2, max=20
        )
        
        if not ok:
            return
            
        # Extract dominant colors from image
        colors = self.image_processor.extract_dominant_colors(num_colors)
        
        if not colors:
            QMessageBox.warning(self, "Error", "Failed to extract colors from image")
            return
            
        # Clear existing mappings
        self.mappings = {}
        
        # Add each color with a height based on its brightness
        # Brighter colors will be higher
        for i, color in enumerate(colors):
            # Convert RGB to hex
            hex_color = '#{:02x}{:02x}{:02x}'.format(int(color[0]), int(color[1]), int(color[2]))
            
            # Calculate height based on brightness (0.0-1.0)
            brightness = (color[0] + color[1] + color[2]) / (3 * 255)
            height = brightness * 5.0  # Scale to 0-5 range
            
            # Add mapping
            self.mappings[hex_color] = height
            self.image_processor.update_height_mapping(hex_color, height)
        
        # Update UI
        self.update_mapping_list()
        
        QMessageBox.information(self, "Auto Add Colors", 
                               f"{len(colors)} color ranges identified and added.\n"
                               "You can adjust heights manually if needed.")
        
        self.colorMappingChanged.emit()
    
    def save_preset(self, filename):
        """Save the current color mappings to a preset file."""
        try:
            with open(filename, 'w') as f:
                json.dump(self.mappings, f)
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to save preset: {e}")
            return False
    
    def load_preset(self, filename):
        """Load color mappings from a preset file."""
        try:
            with open(filename, 'r') as f:
                self.mappings = json.load(f)
                
            # Update the image processor with loaded mappings
            for color, height in self.mappings.items():
                self.image_processor.update_height_mapping(color, height)
            
            # Update the UI
            self.update_mapping_list()
            self.colorMappingChanged.emit()
            return True
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load preset: {e}")
            return False