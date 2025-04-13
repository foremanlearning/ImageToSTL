#!/usr/bin/env python3
import sys
import traceback

def main():
    """Main entry point for the Image to STL converter application."""
    try:
        print("Starting Image to STL Converter...")
        from PyQt5.QtWidgets import QApplication
        print("PyQt5 imported successfully")
        
        app = QApplication(sys.argv)
        app.setApplicationName("Image to STL Converter")
        print("QApplication initialized")
        
        # Create and show the main window
        print("Importing MainWindow...")
        from gui.main_window import MainWindow
        print("MainWindow imported")
        
        print("Creating MainWindow instance...")
        main_window = MainWindow()
        print("MainWindow instance created")
        
        print("Showing MainWindow...")
        main_window.show()
        print("MainWindow shown")
        
        print("Starting event loop...")
        # Start the event loop
        return app.exec_()
        
    except Exception as e:
        print(f"Error in main: {e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())