import os
import sys
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                           QLabel, QPushButton, QFileDialog, QSlider, QSpinBox,
                           QDoubleSpinBox, QCheckBox, QGroupBox, QColorDialog,
                           QProgressBar, QMessageBox, QTabWidget, QComboBox,
                           QAction, QToolBar, QStatusBar, QSizePolicy)
from PyQt5.QtGui import QPixmap, QImage, QColor
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QMutex

from core.image_processor import ImageProcessor
from core.stl_generator import STLGenerator
from gui.stl_preview import STLPreviewWidget
from gui.color_mapper import ColorMappingWidget

class STLWorker(QThread):
    """Worker thread for processing STL generation without freezing the UI."""
    # Progress signal to update UI
    progressUpdated = pyqtSignal(int, str)
    # Result signal to return the mesh
    resultReady = pyqtSignal(object)
    
    def __init__(self, image_processor, stl_generator):
        super().__init__()
        self.image_processor = image_processor
        self.stl_generator = stl_generator
        self.params = {}
        self.mutex = QMutex()
        
    def configure(self, params):
        """Set parameters for STL generation."""
        self.mutex.lock()
        self.params = params
        self.mutex.unlock()
        
    def run(self):
        """Main processing method that runs in a separate thread."""
        self.mutex.lock()
        params = self.params.copy()
        self.mutex.unlock()
        
        # Report progress
        self.progressUpdated.emit(10, "Generating height map...")
        
        # Generate height map
        if params.get('has_mappings', False):
            height_map = self.image_processor.generate_height_map_from_colors(
                transparency_threshold=params.get('transparency_threshold', 128))
        else:
            self.image_processor.auto_assign_heights_by_brightness()
            height_map = self.image_processor.height_map
        
        self.progressUpdated.emit(30, "Processing height map...")
        
        # Apply inversion if checked
        if params.get('invert', False):
            self.progressUpdated.emit(35, "Inverting heights...")
            self.image_processor.invert_heights()
        
        # Apply resolution adjustment
        resolution_factor = params.get('resolution_factor', 1.0)
        if resolution_factor != 1.0:
            self.progressUpdated.emit(40, f"Adjusting resolution ({int(resolution_factor*100)}%)...")
            self.image_processor.adjust_resolution(resolution_factor)
            
        # Apply smoothing
        smoothing_factor = params.get('smoothing_factor', 0.0)
        if smoothing_factor > 0:
            self.progressUpdated.emit(50, f"Applying smoothing (factor: {smoothing_factor:.1f})...")
            self.image_processor.apply_smoothing(smoothing_factor)
        
        # Get triangle limit (if any)
        max_triangles = params.get('max_triangles', None)
        if max_triangles == 0:  # 0 means no limit in the UI
            max_triangles = None
            
        # Adjust status message based on whether we're limiting triangles
        if max_triangles:
            self.progressUpdated.emit(60, f"Creating 3D mesh (limit: {max_triangles:,} triangles)...")
        else:
            self.progressUpdated.emit(60, "Creating 3D mesh...")
            
        # Check if we're creating a model with no base
        no_base = params.get('no_base', False)
        if no_base:
            self.progressUpdated.emit(65, "Creating surface-only model (no base)...")
        
        # Create mesh with triangle limit
        mesh = self.stl_generator.create_mesh_from_height_map(
            self.image_processor.height_map,
            base_thickness=params.get('base_thickness', 1.0),
            scale_factor=params.get('scale_factor', 1.0),
            max_triangles=max_triangles,
            no_base=no_base
        )
        
        # Report triangle count
        triangle_count = self.stl_generator.get_triangle_count()
        self.progressUpdated.emit(90, f"Finalizing 3D model ({triangle_count:,} triangles)...")
        
        # Emit the result
        self.resultReady.emit(mesh)
        
        self.progressUpdated.emit(100, f"STL generation complete ({triangle_count:,} triangles)")

class MainWindow(QMainWindow):
    """Main window of the Image to STL Converter application."""
    
    def __init__(self):
        super().__init__()
        
        # Initialize data
        self.image_processor = ImageProcessor()
        self.stl_generator = STLGenerator()
        self.current_image_path = None
        
        # Create worker thread
        self.stl_worker = STLWorker(self.image_processor, self.stl_generator)
        self.stl_worker.progressUpdated.connect(self.update_progress)
        self.stl_worker.resultReady.connect(self.process_stl_result)
        
        # Set up UI
        self.setWindowTitle("Image to STL Converter")
        self.resize(1200, 800)
        self.setup_ui()
        
        # Set up timers
        self.smoothing_timer = QTimer()
        self.smoothing_timer.setSingleShot(True)
        self.smoothing_timer.timeout.connect(self.apply_smoothing)
        
        self.resolution_timer = QTimer()
        self.resolution_timer.setSingleShot(True)
        self.resolution_timer.timeout.connect(self.apply_resolution)
    
    def setup_ui(self):
        """Set up the user interface."""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        
        # Left panel for controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(10, 10, 10, 10)
        
        # Image loading section
        image_group = QGroupBox("Image")
        image_layout = QVBoxLayout(image_group)
        
        self.image_label = QLabel("No image loaded")
        self.image_label.setAlignment(Qt.AlignCenter)
        self.image_label.setMinimumSize(300, 200)
        self.image_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        load_btn = QPushButton("Load Image")
        load_btn.clicked.connect(self.load_image)
        
        image_layout.addWidget(self.image_label)
        image_layout.addWidget(load_btn)
        
        # Color mapping section
        self.color_mapper = ColorMappingWidget(self.image_processor)
        # Connect color dropper signal
        self.color_mapper.colorDropperToggled.connect(self.toggle_image_click_mode)
        
        # STL generation parameters
        stl_params_group = QGroupBox("STL Parameters")
        stl_params_layout = QVBoxLayout(stl_params_group)
        
        # Base thickness
        base_thickness_layout = QHBoxLayout()
        base_thickness_layout.addWidget(QLabel("Base Thickness:"))
        self.base_thickness_spin = QDoubleSpinBox()
        self.base_thickness_spin.setRange(0.1, 10.0)
        self.base_thickness_spin.setValue(1.0)
        self.base_thickness_spin.setSingleStep(0.1)
        base_thickness_layout.addWidget(self.base_thickness_spin)
        stl_params_layout.addLayout(base_thickness_layout)
        
        # No base checkbox
        self.no_base_checkbox = QCheckBox("No Base (Surface Only)")
        self.no_base_checkbox.setToolTip("Generate only the surface without a solid base")
        self.no_base_checkbox.stateChanged.connect(self.toggle_base_options)
        stl_params_layout.addWidget(self.no_base_checkbox)
        
        # Overall scale
        scale_layout = QHBoxLayout()
        scale_layout.addWidget(QLabel("Scale:"))
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(0.01, 100.0)
        self.scale_spin.setValue(1.0)
        self.scale_spin.setSingleStep(0.1)
        scale_layout.addWidget(self.scale_spin)
        stl_params_layout.addLayout(scale_layout)
        
        # Smoothing
        smooth_layout = QHBoxLayout()
        smooth_layout.addWidget(QLabel("Smoothing:"))
        self.smooth_slider = QSlider(Qt.Horizontal)
        self.smooth_slider.setRange(0, 100)
        self.smooth_slider.setValue(0)
        smooth_layout.addWidget(self.smooth_slider)
        self.smooth_value = QLabel("0")
        smooth_layout.addWidget(self.smooth_value)
        # Update the connection to use the delayed processing
        self.smooth_slider.valueChanged.connect(self.smoothing_value_changed)
        stl_params_layout.addLayout(smooth_layout)
        
        # Invert heights checkbox
        self.invert_checkbox = QCheckBox("Invert Heights")
        stl_params_layout.addWidget(self.invert_checkbox)
        
        # Resolution control
        resolution_layout = QHBoxLayout()
        resolution_layout.addWidget(QLabel("Resolution:"))
        self.resolution_slider = QSlider(Qt.Horizontal)
        self.resolution_slider.setRange(10, 200)
        self.resolution_slider.setValue(100)
        resolution_layout.addWidget(self.resolution_slider)
        self.resolution_value = QLabel("100%")
        resolution_layout.addWidget(self.resolution_value)
        # Update the connection to use the delayed processing
        self.resolution_slider.valueChanged.connect(self.resolution_value_changed)
        stl_params_layout.addLayout(resolution_layout)
        
        # Transparency threshold
        transparency_layout = QHBoxLayout()
        transparency_layout.addWidget(QLabel("Transparency Threshold:"))
        self.transparency_slider = QSlider(Qt.Horizontal)
        self.transparency_slider.setRange(0, 255)
        self.transparency_slider.setValue(128)
        transparency_layout.addWidget(self.transparency_slider)
        self.transparency_value = QLabel("128")
        transparency_layout.addWidget(self.transparency_value)
        self.transparency_slider.valueChanged.connect(lambda v: self.transparency_value.setText(str(v)))
        stl_params_layout.addLayout(transparency_layout)
        
        # Triangle limit control
        triangle_limit_layout = QHBoxLayout()
        triangle_limit_layout.addWidget(QLabel("Triangle Limit:"))
        self.triangle_limit_spin = QSpinBox()
        self.triangle_limit_spin.setRange(0, 1000000)  # 0 means no limit
        self.triangle_limit_spin.setSingleStep(1000)
        self.triangle_limit_spin.setValue(50000)       # Default 50k triangles
        self.triangle_limit_spin.setSuffix(" triangles")
        self.triangle_limit_spin.setSpecialValueText("No limit")
        triangle_limit_layout.addWidget(self.triangle_limit_spin)
        stl_params_layout.addLayout(triangle_limit_layout)
        
        # Triangle count display
        self.triangle_count_label = QLabel("Triangles: 0")
        stl_params_layout.addWidget(self.triangle_count_label)
        
        # Generate and export buttons
        button_layout = QHBoxLayout()
        
        self.generate_btn = QPushButton("Generate STL")
        self.generate_btn.clicked.connect(self.generate_stl)
        self.generate_btn.setEnabled(False)
        
        self.export_btn = QPushButton("Export STL")
        self.export_btn.clicked.connect(self.export_stl)
        self.export_btn.setEnabled(False)
        
        button_layout.addWidget(self.generate_btn)
        button_layout.addWidget(self.export_btn)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        
        # Add to left layout
        left_layout.addWidget(image_group)
        left_layout.addWidget(self.color_mapper)
        left_layout.addWidget(stl_params_group)
        left_layout.addLayout(button_layout)
        left_layout.addWidget(self.progress_bar)
        
        # Right panel for STL preview
        self.stl_preview = STLPreviewWidget()
        
        # Add panels to main layout
        main_layout.addWidget(left_panel, 1)
        main_layout.addWidget(self.stl_preview, 2)
        
        # Status bar
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self.status_label = QLabel("Ready")
        status_bar.addPermanentWidget(self.status_label)
        
        # Create toolbar
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)
        
        # Add toolbar actions
        self.actionLoad = QAction("Load Image", self)
        self.actionLoad.triggered.connect(self.load_image)
        toolbar.addAction(self.actionLoad)
        
        self.actionSave = QAction("Save STL", self)
        self.actionSave.triggered.connect(self.export_stl)
        self.actionSave.setEnabled(False)
        toolbar.addAction(self.actionSave)
        
        self.actionSavePreset = QAction("Save Preset", self)
        self.actionSavePreset.triggered.connect(self.save_preset)
        toolbar.addAction(self.actionSavePreset)
        
        self.actionLoadPreset = QAction("Load Preset", self)
        self.actionLoadPreset.triggered.connect(self.load_preset)
        toolbar.addAction(self.actionLoadPreset)

    def smoothing_value_changed(self, value):
        """Handle smoothing slider value changes with visual feedback."""
        # Update label
        smoothing_factor = value / 10.0
        self.smooth_value.setText(f"{smoothing_factor:.1f}")
        
        # Update status bar with immediate feedback
        self.status_label.setText(f"Smoothing: {smoothing_factor:.1f}")
        
        # Reset and restart the timer to apply changes after user stops moving the slider
        self.smoothing_timer.start(500)  # Wait 500ms before applying

    def apply_smoothing(self):
        """Apply smoothing after user stops adjusting the slider."""
        if self.image_processor.height_map is not None:
            smoothing_factor = self.smooth_slider.value() / 10.0
            self.status_label.setText(f"Applying smoothing (factor: {smoothing_factor:.1f})...")
            
            # Generate the STL again with the new smoothing value
            self.generate_stl()
        
    def resolution_value_changed(self, value):
        """Handle resolution slider value changes with visual feedback."""
        # Update label
        self.resolution_value.setText(f"{value}%")
        
        # Update status bar with immediate feedback
        self.status_label.setText(f"Resolution: {value}%")
        
        # Reset and restart the timer to apply changes after user stops moving the slider
        self.resolution_timer.start(500)  # Wait 500ms before applying

    def apply_resolution(self):
        """Apply resolution change after user stops adjusting the slider."""
        if self.image_processor.height_map is not None:
            resolution = self.resolution_slider.value()
            self.status_label.setText(f"Adjusting resolution ({resolution}%)...")
            
            # Generate the STL again with the new resolution value
            self.generate_stl()

    def load_image(self):
        """Open file dialog to load an image."""
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("Image files (*.png *.jpg *.jpeg *.bmp *.gif *.tif *.tiff)")
        file_dialog.setViewMode(QFileDialog.Detail)
        
        if file_dialog.exec_():
            selected_files = file_dialog.selectedFiles()
            if selected_files:
                image_path = selected_files[0]
                self.status_label.setText(f"Loading image: {os.path.basename(image_path)}...")
                
                if self.image_processor.load_image(image_path):
                    self.current_image_path = image_path
                    self.display_image()
                    self.color_mapper.update_image()
                    self.generate_btn.setEnabled(True)
                    self.status_label.setText(f"Loaded: {os.path.basename(image_path)}")
                else:
                    QMessageBox.critical(self, "Error", "Failed to load the image.")
                    self.status_label.setText("Error loading image")
    
    def display_image(self):
        """Display the loaded image in the preview area."""
        if self.image_processor.image:
            # Convert PIL image to QPixmap
            img = self.image_processor.image.convert("RGBA")
            data = img.tobytes("raw", "RGBA")
            qimage = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
            pixmap = QPixmap.fromImage(qimage)
            
            # Resize pixmap to fit the label while maintaining aspect ratio
            pixmap = pixmap.scaled(self.image_label.size(), 
                                  Qt.KeepAspectRatio, 
                                  Qt.SmoothTransformation)
            
            self.image_label.setPixmap(pixmap)
    
    def update_progress(self, value, message):
        """Update progress bar and status message from the worker thread."""
        self.progress_bar.setValue(value)
        self.status_label.setText(message)
        
    def process_stl_result(self, mesh):
        """Handle the mesh result from the worker thread."""
        if mesh:
            self.stl_preview.display_mesh(mesh)
            self.export_btn.setEnabled(True)
            self.actionSave.setEnabled(True)
            
            # Update the triangle count label
            triangle_count = self.stl_generator.get_triangle_count()
            self.triangle_count_label.setText(f"Triangles: {triangle_count:,}")
        
        # Hide progress bar after a delay
        QTimer.singleShot(2000, lambda: self.progress_bar.setVisible(False))
    
    def generate_stl(self):
        """Generate STL from the current image and settings using a worker thread."""
        if not self.image_processor.image:
            return
        
        # Disable UI controls during processing
        self.generate_btn.setEnabled(False)
        self.export_btn.setEnabled(False)
        
        # Show progress indicator
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText("Preparing STL generation...")
        
        # Prepare parameters for the worker
        params = {
            'has_mappings': self.color_mapper.has_mappings(),
            'transparency_threshold': self.transparency_slider.value(),
            'invert': self.invert_checkbox.isChecked(),
            'resolution_factor': self.resolution_slider.value() / 100.0,
            'smoothing_factor': self.smooth_slider.value() / 10.0,
            'base_thickness': self.base_thickness_spin.value(),
            'scale_factor': self.scale_spin.value(),
            'max_triangles': self.triangle_limit_spin.value(),
            'no_base': self.no_base_checkbox.isChecked()
        }
        
        # Configure and start the worker thread
        self.stl_worker.configure(params)
        self.stl_worker.start()
        
        # Re-enable the generate button
        self.generate_btn.setEnabled(True)
    
    def export_stl(self):
        """Save the generated STL to a file."""
        if not self.stl_generator.get_mesh():
            return
            
        # Suggest filename based on the original image
        suggested_name = "model.stl"
        if self.current_image_path:
            base_name = os.path.splitext(os.path.basename(self.current_image_path))[0]
            suggested_name = f"{base_name}.stl"
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, 'Save STL File', suggested_name, 'STL Files (*.stl)')
            
        if file_path:
            if self.stl_generator.save_stl(file_path):
                self.status_label.setText(f"Saved: {os.path.basename(file_path)}")
            else:
                QMessageBox.critical(self, "Error", "Failed to save the STL file.")
    
    def save_preset(self):
        """Save the current color-to-height mapping as a preset."""
        if not self.color_mapper.has_mappings():
            QMessageBox.information(self, "No Mappings", "No color mappings to save.")
            return
            
        file_path, _ = QFileDialog.getSaveFileName(
            self, 'Save Preset', 'preset.json', 'JSON Files (*.json)')
            
        if file_path:
            self.color_mapper.save_preset(file_path)
            self.status_label.setText(f"Saved preset: {os.path.basename(file_path)}")
    
    def load_preset(self):
        """Load a saved color-to-height mapping preset."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, 'Load Preset', '', 'JSON Files (*.json)')
            
        if file_path:
            if self.color_mapper.load_preset(file_path):
                self.status_label.setText(f"Saved preset: {os.path.basename(file_path)}")
            else:
                QMessageBox.critical(self, "Error", "Failed to load the preset file.")

    def toggle_image_click_mode(self, enabled):
        """Toggle the image click mode for color dropper functionality."""
        if enabled:
            # Change cursor to crosshair to indicate dropper mode
            self.image_label.setCursor(Qt.CrossCursor)
            # Enable mouse tracking for the image label
            self.image_label.setMouseTracking(True)
            # Install event filter to capture mouse clicks on the image
            self.image_label.installEventFilter(self)
            # Update status
            self.status_label.setText("Color dropper active: Click on the image to select a color")
        else:
            # Restore normal cursor
            self.image_label.setCursor(Qt.ArrowCursor)
            # Disable mouse tracking
            self.image_label.setMouseTracking(False)
            # Remove event filter
            self.image_label.removeEventFilter(self)
            # Update status
            self.status_label.setText("Ready")

    def eventFilter(self, obj, event):
        """Filter events to capture mouse clicks on the image when dropper is active."""
        if obj == self.image_label and event.type() == event.MouseButtonPress:
            # Only handle left mouse button
            if event.button() == Qt.LeftButton:
                self.pick_color_from_image(event.pos())
                return True
        return super().eventFilter(obj, event)

    def pick_color_from_image(self, pos):
        """Pick a color from the image at the clicked position."""
        if not self.image_processor.image:
            return

        # Get the pixmap from the label
        pixmap = self.image_label.pixmap()
        if not pixmap:
            return
            
        # Convert position to image coordinates, accounting for aspect ratio scaling
        label_size = self.image_label.size()
        pixmap_size = pixmap.size()
        
        # Calculate scaling factors and offsets for centered image
        scale_w = pixmap_size.width() / label_size.width()
        scale_h = pixmap_size.height() / label_size.height()
        scale = min(1.0, max(scale_w, scale_h))
        
        offset_x = (label_size.width() - pixmap_size.width() / scale) / 2
        offset_y = (label_size.height() - pixmap_size.height() / scale) / 2
        
        # Adjust position based on scaling and centering
        img_x = int((pos.x() - offset_x) * scale)
        img_y = int((pos.y() - offset_y) * scale)
        
        # Make sure the point is within the image bounds
        if img_x < 0 or img_x >= pixmap_size.width() or img_y < 0 or img_y >= pixmap_size.height():
            self.status_label.setText("Click within the image boundaries")
            return
        
        # Create a QImage from the pixmap and get the color at the calculated position
        image = pixmap.toImage()
        color = QColor(image.pixel(img_x, img_y))
        
        # Set the selected color in the color mapper
        self.color_mapper.set_color_from_image(color)
        
        # Update status
        self.status_label.setText(f"Color selected: {color.name()}")
        return color

    def toggle_base_options(self, state):
        """Enable or disable base thickness controls based on the No Base checkbox."""
        has_base = state != Qt.Checked
        self.base_thickness_spin.setEnabled(has_base)
        
        # Update the status bar with information
        if not has_base:
            self.status_label.setText("Base disabled: Model will be generated as a surface only")
        else:
            self.status_label.setText("Base enabled: Model will include a solid base")