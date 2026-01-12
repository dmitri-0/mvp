from PySide6.QtGui import QGuiApplication


class WindowStateMixin:
    """Mixin: сохранение/восстановление состояния окна (геометрия, сплиттер)."""

    def _save_window_geometry(self):
        """Сохранение геометрии окна в config.json"""
        # Не сохраняем состояние если окно свернуто (minimized)
        if self.isMinimized():
            return

        is_maximized = self.isMaximized()
        geometry = self.config.get("window_geometry", {})
        
        # Обновляем флаг развернутости
        geometry["is_maximized"] = is_maximized
        
        # Если окно не развернуто, сохраняем только размеры (без координат)
        if not is_maximized:
            geometry["width"] = self.width()
            geometry["height"] = self.height()
            # Удаляем координаты, чтобы при следующем запуске центрировать
            geometry.pop("x", None)
            geometry.pop("y", None)
            
        self.config.set("window_geometry", geometry)

    def _restore_window_geometry(self):
        """Восстановление геометрии окна из config.json"""
        geometry = self.config.get("window_geometry", {})
        
        # Проверяем, было ли окно развернуто
        is_maximized = geometry.get("is_maximized", False)
        
        if is_maximized:
            # Если окно было развернуто, восстанавливаем maximized состояние
            self.showMaximized()
        else:
            # Иначе восстанавливаем размеры и центрируем
            width = geometry.get("width", 1000)
            height = geometry.get("height", 600)
            
            screen = QGuiApplication.primaryScreen()
            if screen:
                avail = screen.availableGeometry()
                
                # Корректировка размеров, если выходят за пределы экрана
                if width > avail.width():
                    width = avail.width()
                if height > avail.height():
                    height = avail.height()
                    
                # Центрирование окна
                x = avail.x() + (avail.width() - width) // 2
                y = avail.y() + (avail.height() - height) // 2
                
                self.resize(width, height)
                self.move(x, y)
            else:
                self.resize(width, height)

    def _save_splitter_state(self, pos=None, index=None):
        """Сохранение позиции сплиттера"""
        self.config.set("splitter_sizes", self.splitter.sizes())

    def _restore_splitter_state(self):
        """Восстановление позиции сплиттера"""
        sizes = self.config.get("splitter_sizes")
        if sizes:
            self.splitter.setSizes(sizes)
