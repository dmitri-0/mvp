from PySide6.QtWidgets import QDialog, QVBoxLayout, QListWidget, QLabel, QDialogButtonBox, QSplitter
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt

class PreviewLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.original_image = None
        self.setAlignment(Qt.AlignCenter)
        # Darker background for better contrast
        self.setStyleSheet("background-color: #333; border: 1px solid #555;")
        
    def set_image(self, image_data):
        if image_data:
            self.original_image = QImage.fromData(image_data)
            self._update_pixmap()
        else:
            self.original_image = None
            self.clear()
            
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_pixmap()
        
    def _update_pixmap(self):
        if self.original_image and not self.original_image.isNull():
            w = self.width()
            h = self.height()
            if w > 0 and h > 0:
                pixmap = QPixmap.fromImage(self.original_image)
                self.setPixmap(pixmap.scaled(
                    w, h,
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                ))

class ImageSelectionDialog(QDialog):
    def __init__(self, images, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Image to Edit")
        self.resize(800, 500)
        self.images = images  # list of (id, note_id, name, data, mime)
        self.selected_image = None
        
        layout = QVBoxLayout(self)
        
        splitter = QSplitter(Qt.Horizontal)
        
        self.list_widget = QListWidget()
        for img_data in self.images:
            # img_data structure: (id, note_id, name, data, mime)
            name = img_data[2]
            self.list_widget.addItem(name)
        self.list_widget.currentRowChanged.connect(self.on_row_changed)
        
        self.preview_label = PreviewLabel()
        self.preview_label.setMinimumWidth(400)
        
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
            # Structure: (id, note_id, name, data, mime)
            data = self.selected_image[3]
            self.preview_label.set_image(data)
        else:
            self.selected_image = None
            self.preview_label.set_image(None)
