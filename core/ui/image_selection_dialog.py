from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QLabel, QDialogButtonBox, QSplitter
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt

class ImageSelectionDialog(QDialog):
    def __init__(self, images, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Image to Edit")
        self.resize(800, 500)
        self.images = images  # list of (id, name, data, mime)
        self.selected_image = None
        
        layout = QVBoxLayout(self)
        
        splitter = QSplitter(Qt.Horizontal)
        
        self.list_widget = QListWidget()
        for _, name, _, _ in self.images:
            self.list_widget.addItem(name)
        self.list_widget.currentRowChanged.connect(self.on_row_changed)
        
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumWidth(400)
        # Darker background for better contrast with potentially light images
        self.preview_label.setStyleSheet("background-color: #333; border: 1px solid #555;")
        
        splitter.addWidget(self.list_widget)
        splitter.addWidget(self.preview_label)
        splitter.setStretchFactor(1, 1)
        
        layout.addWidget(splitter)
        
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        if self.images:
            self.list_widget.setCurrentRow(0)

    def on_row_changed(self, row):
        if 0 <= row < len(self.images):
            self.selected_image = self.images[row]
            _, _, data, _ = self.selected_image
            if data:
                img = QImage.fromData(data)
                pixmap = QPixmap.fromImage(img)
                
                # Scale to fit label size
                w = self.preview_label.width()
                h = self.preview_label.height()
                if not pixmap.isNull():
                    self.preview_label.setPixmap(pixmap.scaled(
                        w, h,
                        Qt.KeepAspectRatio, 
                        Qt.SmoothTransformation
                    ))
            else:
                self.preview_label.clear()
        else:
            self.selected_image = None
            self.preview_label.clear()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Refresh preview on resize
        self.on_row_changed(self.list_widget.currentRow())
