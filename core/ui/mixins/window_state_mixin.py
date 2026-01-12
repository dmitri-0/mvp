class WindowStateMixin:
    """Mixin: сохранение/восстановление состояния окна (геометрия, сплиттер)."""

    def _save_window_geometry(self):
        """Сохранение геометрии окна в config.json"""
        geometry = {
            "width": self.width(),
            "height": self.height(),
            "x": self.x(),
            "y": self.y(),
        }
        self.config.set("window_geometry", geometry)

    def _restore_window_geometry(self):
        """Восстановление геометрии окна из config.json"""
        geometry = self.config.get("window_geometry")
        if geometry:
            self.resize(geometry.get("width", 1000), geometry.get("height", 600))
            x = geometry.get("x")
            y = geometry.get("y")
            if x is not None and y is not None:
                self.move(x, y)

    def _save_splitter_state(self, pos=None, index=None):
        """Сохранение позиции сплиттера"""
        self.config.set("splitter_sizes", self.splitter.sizes())

    def _restore_splitter_state(self):
        """Восстановление позиции сплиттера"""
        sizes = self.config.get("splitter_sizes")
        if sizes:
            self.splitter.setSizes(sizes)
