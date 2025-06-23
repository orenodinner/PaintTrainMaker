import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QDockWidget, QListWidget,
    QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QGraphicsView,
    QMenuBar, QStatusBar, QGraphicsScene, QGraphicsPixmapItem, QListWidgetItem,
    QGraphicsPathItem, QSlider, QLabel, QColorDialog, QFrame, QMessageBox
)
from PyQt6.QtGui import (
    QAction, QIcon, QPen, QColor, QPainter, QPixmap, QPainterPath,
    QUndoStack, QUndoCommand
)
from PyQt6.QtCore import Qt, QDir, QPointF, QRectF, QSize, QSizeF, QSettings

# --- アンドゥ/リドゥ用のコマンドクラス ---
class AddCommand(QUndoCommand):
    """線画アイテムを追加するコマンド"""
    def __init__(self, scene, item, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.item = item
        self.setText("描画")

    def undo(self):
        self.scene.removeItem(self.item)

    def redo(self):
        if self.item.scene() is None:
            self.scene.addItem(self.item)

class RemoveCommand(QUndoCommand):
    """複数の線画アイテムを削除するコマンド（消しゴム用）"""
    def __init__(self, scene, items, parent=None):
        super().__init__(parent)
        self.scene = scene
        self.items = items
        self.setText("消去")

    def undo(self):
        for item in self.items:
            if item.scene() is None:
                self.scene.addItem(item)

    def redo(self):
        for item in self.items:
            if item.scene() == self.scene:
                 self.scene.removeItem(item)

# --- 描画用シーンクラス (アンドゥ/リドゥ対応) ---
class DrawingScene(QGraphicsScene):
    def __init__(self, undo_stack, parent=None):
        super().__init__(parent)
        self.undo_stack = undo_stack
        self.is_drawing = False
        self.is_eraser_mode = False
        self.pen_color = QColor("black")
        self.pen_size = 5
        self.last_path_item = None

    def create_pen(self):
        pen = QPen(self.pen_color, self.pen_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        return pen

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = True
            if self.is_eraser_mode:
                self.erase_at(event.scenePos())
            else:
                self.last_path_item = QGraphicsPathItem()
                self.last_path_item.setPen(self.create_pen())
                self.current_path = QPainterPath()
                self.current_path.moveTo(event.scenePos())
                self.last_path_item.setPath(self.current_path)
                self.addItem(self.last_path_item)

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            if self.is_eraser_mode:
                self.erase_at(event.scenePos())
            else:
                if self.last_path_item:
                    self.current_path.lineTo(event.scenePos())
                    self.last_path_item.setPath(self.current_path)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            if not self.is_eraser_mode and self.last_path_item and self.last_path_item.path().elementCount() > 1:
                command = AddCommand(self, self.last_path_item)
                self.undo_stack.push(command)
            self.is_drawing = False
            self.last_path_item = None

    def erase_at(self, position):
        radius = self.pen_size / 2.0
        erase_rect = QRectF(position - QPointF(radius, radius), QSizeF(radius*2, radius*2))
        items_to_erase = [item for item in self.items(erase_rect) if isinstance(item, QGraphicsPathItem)]
        
        if items_to_erase:
            command = RemoveCommand(self, list(items_to_erase))
            self.undo_stack.push(command)
    
    def clear_drawing(self):
        items_to_remove = [item for item in self.items() if not isinstance(item, QGraphicsPixmapItem)]
        if items_to_remove:
             for item in items_to_remove:
                self.removeItem(item)
        self.undo_stack.clear()


# --- メインウィンドウ ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.image_files = []
        self.current_image_index = -1
        self.background_item = None
        self.save_dir = None
        self.undo_stack = QUndoStack(self)
        self.image_folder_path = None
        # ### 状態管理: processed_mapは保存済みとスキップ済みの両方を管理します
        # 保存済み: {元ファイルパス: "保存ファイル名.png"}
        # スキップ済み: {元ファイルパス: "_SKIPPED_"}
        self.processed_map = {}

        self.init_ui()
        self.create_actions_and_shortcuts()
        self.init_settings()
        self.load_settings()

    def init_settings(self):
        """設定オブジェクトを初期化する"""
        self.settings = QSettings("MyCompany", "PaintTrainMaker")

    def closeEvent(self, event):
        """ウィンドウが閉じられるときに設定を保存する"""
        self.save_settings()
        super().closeEvent(event)

    def load_settings(self):
        """起動時に前回終了時の設定を読み込む"""
        self.statusBar().showMessage("前回終了時の設定を読み込んでいます...")
        self.save_dir = self.settings.value("save_dir", None)
        if self.save_dir:
            self.statusBar().showMessage(f"保存先フォルダ: {self.save_dir}")
        
        self.processed_map = self.settings.value("processed_map", {}, type=dict)

        last_folder = self.settings.value("last_folder_path", None)
        if last_folder and os.path.isdir(last_folder):
            self.load_folder(last_folder)
        else:
            self.statusBar().showMessage("準備完了。フォルダを開いてください。")

    def save_settings(self):
        """現在の手作業状態を設定に保存する"""
        if self.image_folder_path:
            self.settings.setValue("last_folder_path", self.image_folder_path)
        if self.save_dir:
            self.settings.setValue("save_dir", self.save_dir)
        
        self.settings.setValue("processed_map", self.processed_map)

    def init_ui(self):
        self.setWindowTitle("学習データセット作成支援アプリ")
        self.setGeometry(100, 100, 1400, 900)

        self.scene = DrawingScene(self.undo_stack, self)
        self.canvas_view = QGraphicsView(self.scene)
        self.canvas_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.canvas_view.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setCentralWidget(self.canvas_view)

        tools_dock = QDockWidget("ツール", self)
        tools_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, tools_dock)
        
        tool_widget = QWidget()
        tool_layout = QVBoxLayout(tool_widget)
        tools_dock.setWidget(tool_widget)
        
        self.pen_button = QPushButton("ペン (B)")
        self.pen_button.setCheckable(True)
        self.pen_button.setChecked(True)
        self.pen_button.clicked.connect(self.activate_pen_tool)
        
        self.eraser_button = QPushButton("消しゴム (E)")
        self.eraser_button.setCheckable(True)
        self.eraser_button.clicked.connect(self.activate_eraser_tool)
        
        tool_layout.addWidget(self.pen_button)
        tool_layout.addWidget(self.eraser_button)

        tool_layout.addWidget(self.create_separator())
        
        tool_layout.addWidget(QLabel("ブラシサイズ:"))
        self.pen_size_slider = QSlider(Qt.Orientation.Horizontal)
        self.pen_size_slider.setRange(1, 100)
        self.pen_size_slider.setValue(5)
        self.pen_size_slider.valueChanged.connect(self.change_pen_size)
        tool_layout.addWidget(self.pen_size_slider)
        
        self.color_button = QPushButton("ペンの色を変更")
        self.color_button.clicked.connect(self.open_color_dialog)
        self.update_color_button_style(self.scene.pen_color)
        tool_layout.addWidget(self.color_button)

        tool_layout.addWidget(self.create_separator())

        tool_layout.addWidget(QLabel("背景の不透明度:"))
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(50)
        self.opacity_slider.valueChanged.connect(self.change_background_opacity)
        tool_layout.addWidget(self.opacity_slider)

        tool_layout.addStretch()

        files_dock = QDockWidget("ファイル一覧", self)
        files_dock.setFeatures(QDockWidget.DockWidgetFeature.NoDockWidgetFeatures)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, files_dock)
        file_widget = QWidget()
        file_layout = QVBoxLayout(file_widget)
        files_dock.setWidget(file_widget)

        self.file_list_widget = QListWidget()
        self.file_list_widget.currentItemChanged.connect(self.on_file_selected)

        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("< 前へ (←)")
        self.next_button = QPushButton("> 次へ (→)")
        self.prev_button.clicked.connect(self.show_prev_image)
        self.next_button.clicked.connect(self.show_next_image)
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.next_button)

        ### スキップ機能追加: UI要素の作成 ###
        self.skip_button = QPushButton("スキップ (Ctrl+D)")
        self.skip_button.setStyleSheet("background-color: #E74C3C; color: white;") # 赤系の目立つ色
        self.skip_button.clicked.connect(self.skip_image)

        self.save_button = QPushButton("保存 (Ctrl+S)")
        self.save_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.save_button.clicked.connect(self.save_dataset_pair)

        file_layout.addWidget(self.file_list_widget)
        file_layout.addLayout(nav_layout)
        ### スキップ機能追加: レイアウトへの追加 ###
        file_layout.addWidget(self.skip_button)
        file_layout.addWidget(self.save_button)

        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("準備完了。")

    def create_actions_and_shortcuts(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("ファイル(&F)")
        edit_menu = menu_bar.addMenu("編集(&E)")
        view_menu = menu_bar.addMenu("表示(&V)")

        open_folder_action = QAction("フォルダを開く...", self)
        open_folder_action.setShortcut("Ctrl+O")
        open_folder_action.triggered.connect(self.open_folder_dialog)
        file_menu.addAction(open_folder_action)

        undo_action = self.undo_stack.createUndoAction(self, "元に戻す(&U)")
        undo_action.setShortcut("Ctrl+Z")
        edit_menu.addAction(undo_action)

        redo_action = self.undo_stack.createRedoAction(self, "やり直し(&R)")
        redo_action.setShortcut("Ctrl+Y")
        edit_menu.addAction(redo_action)
        
        zoom_in_action = QAction("ズームイン", self, shortcut="Ctrl++", triggered=self.zoom_in)
        zoom_out_action = QAction("ズームアウト", self, shortcut="Ctrl+-", triggered=self.zoom_out)
        fit_view_action = QAction("全体表示", self, shortcut="Ctrl+0", triggered=self.fit_to_view)
        view_menu.addActions([zoom_in_action, zoom_out_action, fit_view_action])

        shortcut_actions = [
            ("Ctrl+S", self.save_dataset_pair),
            ### スキップ機能追加: ショートカットの定義 ###
            ("Ctrl+D", self.skip_image),
            (Qt.Key.Key_Left, self.show_prev_image),
            (Qt.Key.Key_Right, self.show_next_image),
            (Qt.Key.Key_B, self.pen_button.click),
            (Qt.Key.Key_E, self.eraser_button.click)
        ]
        for key, method in shortcut_actions:
            action = QAction(self)
            action.setShortcut(key)
            action.triggered.connect(method)
            self.addAction(action)

    def wheelEvent(self, event):
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            angle = event.angleDelta().y()
            factor = 1.15 if angle > 0 else 1 / 1.15
            self.canvas_view.scale(factor, factor)
        else:
            super().wheelEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.canvas_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().keyPressEvent(event)
    
    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.canvas_view.setDragMode(QGraphicsView.DragMode.NoDrag)
        super().keyReleaseEvent(event)

    def zoom_in(self):
        self.canvas_view.scale(1.2, 1.2)

    def zoom_out(self):
        self.canvas_view.scale(1/1.2, 1/1.2)
    
    def fit_to_view(self):
        if self.scene.sceneRect().isEmpty():
            if self.background_item:
                 self.canvas_view.fitInView(self.background_item, Qt.AspectRatioMode.KeepAspectRatio)
            return
        self.canvas_view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def create_separator(self):
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        return separator

    def activate_pen_tool(self):
        self.scene.is_eraser_mode = False
        self.pen_button.setChecked(True)
        self.eraser_button.setChecked(False)
        self.color_button.setEnabled(True)
        self.statusBar().showMessage("ペンツールを選択しました。")

    def activate_eraser_tool(self):
        self.scene.is_eraser_mode = True
        self.pen_button.setChecked(False)
        self.eraser_button.setChecked(True)
        self.color_button.setEnabled(False)
        self.statusBar().showMessage("消しゴムツールを選択しました。")

    def change_pen_size(self, value):
        self.scene.pen_size = value
        self.statusBar().showMessage(f"ブラシサイズ: {value}")

    def open_color_dialog(self):
        color = QColorDialog.getColor(self.scene.pen_color, self, "ペンの色を選択")
        if color.isValid():
            self.scene.pen_color = color
            self.update_color_button_style(color)
            self.statusBar().showMessage(f"ペンの色を {color.name()} に変更しました。")

    def update_color_button_style(self, color):
        self.color_button.setStyleSheet(f"background-color: {color.name()}; color: {'white' if color.lightnessF() < 0.5 else 'black'};")

    def change_background_opacity(self, value):
        if self.background_item:
            self.background_item.setOpacity(value / 100.0)
            self.statusBar().showMessage(f"背景の不透明度: {value}%")

    def open_folder_dialog(self):
        start_dir = self.image_folder_path or self.save_dir or QDir.homePath()
        dir_path = QFileDialog.getExistingDirectory(self, "画像フォルダを選択", start_dir)
        if dir_path:
            if dir_path != self.image_folder_path:
                self.processed_map.clear()
            self.load_folder(dir_path)

    def load_folder(self, dir_path):
        """指定されたパスから画像ファイルを読み込み、リストに表示する"""
        self.image_folder_path = dir_path
        self.image_files = []
        self.file_list_widget.clear()
        self.current_image_index = -1
        self.scene.clear_drawing()
        if self.background_item:
            self.scene.removeItem(self.background_item)
            self.background_item = None
        self.scene.setSceneRect(QRectF())

        supported_formats = [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"]
        try:
            for filename in sorted(os.listdir(dir_path)):
                if any(filename.lower().endswith(fmt) for fmt in supported_formats):
                    full_path = os.path.join(dir_path, filename)
                    self.image_files.append(full_path)
                    
                    base_filename = os.path.basename(filename)
                    item = QListWidgetItem(base_filename)
                    
                    ### スキップ機能修正: 処理済みファイルの表示分け ###
                    if full_path in self.processed_map:
                        status = self.processed_map[full_path]
                        if status == "_SKIPPED_":
                            item.setText(f"⊘ {base_filename} (スキップ)")
                            item.setForeground(QColor("darkGray"))
                        else:
                            # 保存済みの場合はファイル名(status)を表示するより、マークで示す方が簡潔
                            item.setText(f"✓ {base_filename} (保存済)")
                            item.setForeground(QColor("gray"))

                    self.file_list_widget.addItem(item)
        except OSError as e:
            QMessageBox.warning(self, "エラー", f"フォルダの読み込みに失敗しました: {e}")
            self.statusBar().showMessage("フォルダの読み込みに失敗しました。")
            return

        if self.image_files:
            first_unprocessed_index = -1
            for i, f_path in enumerate(self.image_files):
                if f_path not in self.processed_map:
                    first_unprocessed_index = i
                    break
            
            select_index = 0 if first_unprocessed_index == -1 else first_unprocessed_index
            if self.file_list_widget.count() > select_index:
                self.file_list_widget.setCurrentRow(select_index)
            
            self.statusBar().showMessage(f"{len(self.image_files)}個の画像を読み込みました。")
        else:
            self.statusBar().showMessage("選択されたフォルダにサポートされている画像ファイルが見つかりませんでした。")
            QMessageBox.information(self, "情報", "選択されたフォルダにサポートされている画像ファイルが見つかりませんでした。")

    def on_file_selected(self, current_item, previous_item):
        if current_item is None:
            return
        index = self.file_list_widget.row(current_item)
        if 0 <= index < len(self.image_files):
            if index != self.current_image_index:
                self.current_image_index = index
                self.load_image_to_canvas()
        else:
            self.current_image_index = -1
            self.scene.clear_drawing()
            if self.background_item:
                self.scene.removeItem(self.background_item)
                self.background_item = None
            self.scene.setSceneRect(QRectF())

    def load_image_to_canvas(self):
        if not (0 <= self.current_image_index < len(self.image_files)):
            self.statusBar().showMessage("表示する画像がありません。")
            return
            
        self.undo_stack.clear()
        self.scene.clear_drawing()
        
        image_path = self.image_files[self.current_image_index]
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.statusBar().showMessage(f"エラー: 画像を読み込めません {os.path.basename(image_path)}")
            QMessageBox.warning(self, "読込エラー", f"画像を読み込めませんでした:\n{image_path}")
            return
            
        if self.background_item:
            self.scene.removeItem(self.background_item)
            self.background_item = None
        
        self.background_item = QGraphicsPixmapItem(pixmap)
        self.background_item.setOpacity(self.opacity_slider.value() / 100.0)
        self.background_item.setZValue(-1)
        self.scene.addItem(self.background_item)
        self.scene.setSceneRect(self.background_item.boundingRect())
        
        self.fit_to_view()
        self.activate_pen_tool()
        self.statusBar().showMessage(f"表示中: {os.path.basename(image_path)}")

    def show_prev_image(self):
        if self.file_list_widget.count() == 0: return
        current_row = self.file_list_widget.currentRow()
        if current_row > 0:
            self.file_list_widget.setCurrentRow(current_row - 1)

    def show_next_image(self):
        if self.file_list_widget.count() == 0: return
        current_row = self.file_list_widget.currentRow()
        if current_row < self.file_list_widget.count() - 1:
            self.file_list_widget.setCurrentRow(current_row + 1)

    ### スキップ機能追加: スキップ処理を行うメソッド ###
    def skip_image(self):
        """現在の画像をスキップとしてマークし、次の画像へ移動する。"""
        if self.current_image_index < 0 or not self.image_files:
            QMessageBox.warning(self, "スキップエラー", "スキップ対象の画像が選択されていません。")
            return

        current_image_path = self.image_files[self.current_image_index]

        # processed_map にスキップ情報を記録 ("_SKIPPED_" は特別なフラグ)
        self.processed_map[current_image_path] = "_SKIPPED_"
        
        # 変更を永続化するために設定に即時保存
        self.settings.setValue("processed_map", self.processed_map)

        # QListWidget の表示を更新
        list_widget_item = self.file_list_widget.item(self.current_image_index)
        if list_widget_item:
            base_filename = os.path.basename(current_image_path)
            list_widget_item.setText(f"⊘ {base_filename} (スキップ)")
            list_widget_item.setForeground(QColor("darkGray"))

        self.statusBar().showMessage(f"{os.path.basename(current_image_path)} をスキップしました。")
        
        # 次の画像へ移動
        self.show_next_image()

    def save_dataset_pair(self):
        if self.current_image_index < 0 or not self.image_files:
            QMessageBox.warning(self, "保存エラー", "保存対象の画像が選択されていません。")
            return
        if not self.background_item:
            QMessageBox.warning(self, "保存エラー", "背景画像がロードされていません。")
            return

        if not self.save_dir:
            self.save_dir = QFileDialog.getExistingDirectory(self, "データセットの保存先フォルダを選択", QDir.homePath())
            if not self.save_dir:
                self.statusBar().showMessage("保存がキャンセルされました。")
                return
        
        self.settings.setValue("save_dir", self.save_dir)
        self.statusBar().showMessage(f"保存先フォルダ: {self.save_dir}")

        input_dir = os.path.join(self.save_dir, "input")
        target_dir = os.path.join(self.save_dir, "target")
        try:
            os.makedirs(input_dir, exist_ok=True)
            os.makedirs(target_dir, exist_ok=True)
        except OSError as e:
            QMessageBox.critical(self, "保存エラー", f"保存フォルダの作成に失敗しました: {e}")
            return
        
        next_index = 0
        existing_indices = set()
        if os.path.exists(input_dir):
            for f_name in os.listdir(input_dir):
                base, ext = os.path.splitext(f_name)
                if ext.lower() == ".png" and base.isdigit():
                    existing_indices.add(int(base))
        if os.path.exists(target_dir):
            for f_name in os.listdir(target_dir):
                base, ext = os.path.splitext(f_name)
                if ext.lower() == ".png" and base.isdigit():
                    existing_indices.add(int(base))
        if existing_indices:
            next_index = max(existing_indices) + 1
        base_name = f"{next_index:05d}.png"
        
        current_image_path = self.image_files[self.current_image_index]
        original_pixmap = QPixmap(current_image_path)
        if original_pixmap.isNull():
            QMessageBox.critical(self, "保存エラー", "元の画像の読み込みに失敗しました。")
            return

        if not original_pixmap.save(os.path.join(input_dir, base_name), "PNG"):
            QMessageBox.critical(self, "保存エラー", f"Input画像 ({base_name}) の保存に失敗しました。")
            return
        
        self.background_item.hide()
        render_rect = self.scene.itemsBoundingRect()
        if render_rect.isNull() or render_rect.isEmpty():
            target_size = self.background_item.pixmap().size()
            render_rect = QRectF(QPointF(0,0), QSizeF(target_size))
        else:
            target_size = render_rect.size().toSize()
        if target_size.width() <= 0 or target_size.height() <= 0:
            target_size = original_pixmap.size()
            render_rect = QRectF(QPointF(0,0), QSizeF(target_size))
        target_pixmap = QPixmap(target_size)
        target_pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(target_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.scene.render(painter, QRectF(target_pixmap.rect()), render_rect)
        painter.end()
        if not target_pixmap.save(os.path.join(target_dir, base_name), "PNG"):
            QMessageBox.critical(self, "保存エラー", f"Target画像 ({base_name}) の保存に失敗しました。")
            os.remove(os.path.join(input_dir, base_name)) # ロールバック
            self.background_item.show()
            return
        
        self.background_item.show()
        self.statusBar().showMessage(f"{base_name} として input/target ペアを保存しました。")
        
        self.processed_map[current_image_path] = base_name
        self.settings.setValue("processed_map", self.processed_map)

        ### スキップ機能修正: リストアイテムの表示更新を堅牢化 ###
        # スキップ済みであっても、保存時に正しく表示が上書きされるようにする
        list_widget_item = self.file_list_widget.item(self.current_image_index)
        if list_widget_item:
            base_filename = os.path.basename(current_image_path)
            list_widget_item.setText(f"✓ {base_filename} (保存済)")
            list_widget_item.setForeground(QColor("gray"))
        
        self.show_next_image()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())