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
from PyQt6.QtCore import Qt, QDir, QPointF, QRectF, QSize

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
            self.scene.addItem(item)

    def redo(self):
        for item in self.items:
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
        radius = self.pen_size / 2.0 # 消しゴムの半径
        erase_rect = QRectF(position - QPointF(radius, radius), QSize(int(radius*2), int(radius*2)))
        items_to_erase = [item for item in self.items(erase_rect) if isinstance(item, QGraphicsPathItem)]
        
        if items_to_erase:
            command = RemoveCommand(self, items_to_erase)
            self.undo_stack.push(command)
    
    def clear_drawing(self):
        # QGraphicsPixmapItem (背景画像) 以外を削除
        items_to_remove = [item for item in self.items() if not isinstance(item, QGraphicsPixmapItem)]
        if items_to_remove: # 削除するアイテムがある場合のみコマンドを生成
            # Clear コマンドのようなものがあればそれを使うのが理想だが、ここではRemoveCommandを流用
            # ただし、現状のRemoveCommandは複数のアイテムを一度に処理する前提
            # ここではシンプルに個別に削除する (アンドゥスタックには積まないか、専用コマンドを作るべき)
            # 今回は単純に削除するだけに留める
             for item in items_to_remove:
                self.removeItem(item)
        self.undo_stack.clear() # 描画クリア時はアンドゥスタックもクリアするのが一般的

# --- メインウィンドウ ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.image_files = []
        self.current_image_index = -1
        self.background_item = None
        self.save_dir = None
        self.undo_stack = QUndoStack(self)
        self.init_ui()
        self.create_actions_and_shortcuts()

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

        self.save_button = QPushButton("保存 (Ctrl+S)")
        self.save_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.save_button.clicked.connect(self.save_dataset_pair)

        file_layout.addWidget(self.file_list_widget)
        file_layout.addLayout(nav_layout)
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

        # ショートカットキーの重複を避けるため、QPushButtonに直接関連付けられているものはaddActionしない
        # QAction経由で統一するか、QPushButtonのショートカット設定を活かす
        shortcut_actions = [
            ("Ctrl+S", self.save_dataset_pair),
            (Qt.Key.Key_Left, self.show_prev_image), # Qt.Key.Key_Left を使用
            (Qt.Key.Key_Right, self.show_next_image),# Qt.Key.Key_Right を使用
            (Qt.Key.Key_B, self.pen_button.click),    # Qt.Key.Key_B を使用
            (Qt.Key.Key_E, self.eraser_button.click)  # Qt.Key.Key_E を使用
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
            super().wheelEvent(event) # 通常のスクロールイベントを親クラスに渡す

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.canvas_view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        super().keyPressEvent(event) # 他のキーイベント処理のために呼び出す
    
    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self.canvas_view.setDragMode(QGraphicsView.DragMode.NoDrag)
        super().keyReleaseEvent(event) # 他のキーイベント処理のために呼び出す

    def zoom_in(self):
        self.canvas_view.scale(1.2, 1.2)

    def zoom_out(self):
        self.canvas_view.scale(1/1.2, 1/1.2)
    
    def fit_to_view(self):
        if self.scene.sceneRect().isEmpty():
            if self.background_item: # 背景があればそれに合わせる
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
        self.color_button.setEnabled(False) # 消しゴムモードでは色は関係ないので無効化
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
        dir_path = QFileDialog.getExistingDirectory(self, "画像フォルダを選択", self.save_dir or QDir.homePath())
        if dir_path:
            self.image_files = []
            self.file_list_widget.clear()
            self.current_image_index = -1 # インデックスをリセット
            self.scene.clear_drawing() # シーンの描画内容をクリア
            if self.background_item: # 古い背景画像を削除
                self.scene.removeItem(self.background_item)
                self.background_item = None
            self.scene.setSceneRect(QRectF()) # シーンの矩形をリセット

            supported_formats = [".png", ".jpg", ".jpeg", ".bmp", ".gif", ".tiff"] # 対応フォーマットを追加
            try:
                for filename in sorted(os.listdir(dir_path)):
                    if any(filename.lower().endswith(fmt) for fmt in supported_formats):
                        full_path = os.path.join(dir_path, filename)
                        self.image_files.append(full_path)
                        item = QListWidgetItem(os.path.basename(filename))
                        self.file_list_widget.addItem(item)
            except OSError as e:
                QMessageBox.warning(self, "エラー", f"フォルダの読み込みに失敗しました: {e}")
                self.statusBar().showMessage("フォルダの読み込みに失敗しました。")
                return

            if self.image_files:
                self.file_list_widget.setCurrentRow(0) # 最初の画像を選択状態にする
                # on_file_selected が呼ばれるので load_image_to_canvas も実行される
                self.statusBar().showMessage(f"{len(self.image_files)}個の画像を読み込みました。")
            else:
                self.statusBar().showMessage("選択されたフォルダにサポートされている画像ファイルが見つかりませんでした。")
                QMessageBox.information(self, "情報", "選択されたフォルダにサポートされている画像ファイルが見つかりませんでした。")


    def on_file_selected(self, current_item, previous_item):
        if current_item is None:
            # self.scene.clear_drawing() # 何も選択されていない場合はクリア
            # if self.background_item:
            #     self.scene.removeItem(self.background_item)
            #     self.background_item = None
            # self.scene.setSceneRect(QRectF())
            return
        index = self.file_list_widget.row(current_item)
        if 0 <= index < len(self.image_files): # index が有効範囲内か確認
            if index != self.current_image_index: # 実際に選択が変更された場合のみロード
                self.current_image_index = index
                self.load_image_to_canvas()
        else: # リストがクリアされた場合など current_item があるが index が不正な場合
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
            
        self.undo_stack.clear() # 新しい画像なのでアンドゥスタックをクリア
        self.scene.clear_drawing() # 既存の描画（線画）をクリア
        
        image_path = self.image_files[self.current_image_index]
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            self.statusBar().showMessage(f"エラー: 画像を読み込めません {os.path.basename(image_path)}")
            QMessageBox.warning(self, "読込エラー", f"画像を読み込めませんでした:\n{image_path}")
            # 不正な画像をリストから削除するなどの処理も考えられる
            return
            
        if self.background_item: # 既存の背景アイテムがあれば削除
            self.scene.removeItem(self.background_item)
            self.background_item = None # 参照をクリア
        
        self.background_item = QGraphicsPixmapItem(pixmap)
        self.background_item.setOpacity(self.opacity_slider.value() / 100.0)
        self.background_item.setZValue(-1) # 描画アイテムより奥に配置
        self.scene.addItem(self.background_item)
        self.scene.setSceneRect(self.background_item.boundingRect()) # シーンの大きさを背景画像に合わせる
        
        self.fit_to_view()
        self.activate_pen_tool() # 新しい画像を開いたらペンツールをデフォルトにする
        self.statusBar().showMessage(f"表示中: {os.path.basename(image_path)}")

    def show_prev_image(self):
        if self.file_list_widget.count() == 0: return
        current_row = self.file_list_widget.currentRow()
        if current_row > 0:
            self.file_list_widget.setCurrentRow(current_row - 1)
        # currentItemChangedシグナルにより on_file_selected -> load_image_to_canvas が呼ばれる

    def show_next_image(self):
        if self.file_list_widget.count() == 0: return
        current_row = self.file_list_widget.currentRow()
        if current_row < self.file_list_widget.count() - 1:
            self.file_list_widget.setCurrentRow(current_row + 1)
        # currentItemChangedシグナルにより on_file_selected -> load_image_to_canvas が呼ばれる
    
    def save_dataset_pair(self):
        if self.current_image_index < 0 or not self.image_files:
            self.statusBar().showMessage("保存対象の画像が選択されていません。")
            QMessageBox.warning(self, "保存エラー", "保存対象の画像が選択されていません。")
            return
        if not self.background_item: # 背景画像がロードされていない場合
            self.statusBar().showMessage("背景画像がロードされていません。")
            QMessageBox.warning(self, "保存エラー", "背景画像がロードされていません。")
            return

        if not self.save_dir:
            self.save_dir = QFileDialog.getExistingDirectory(self, "データセットの保存先フォルダを選択", QDir.homePath())
            if not self.save_dir:
                self.statusBar().showMessage("保存がキャンセルされました。")
                return
            else: # 保存先フォルダが設定されたら、ステータスバーに表示などしても良い
                self.statusBar().showMessage(f"保存先フォルダ: {self.save_dir}")


        input_dir = os.path.join(self.save_dir, "input")
        target_dir = os.path.join(self.save_dir, "target")
        try:
            os.makedirs(input_dir, exist_ok=True)
            os.makedirs(target_dir, exist_ok=True)
        except OSError as e:
            QMessageBox.critical(self, "保存エラー", f"保存フォルダの作成に失敗しました: {e}")
            self.statusBar().showMessage(f"保存フォルダの作成に失敗: {e}")
            return
        
        # --- ここから修正されたファイル名生成ロジック ---
        next_index = 0
        existing_indices = set() # 重複を避けるためにセットを使用

        # input_dir をスキャン
        if os.path.exists(input_dir):
            for f_name in os.listdir(input_dir):
                # PNGファイルのみを対象とし、ファイル名が数値であることを確認
                base, ext = os.path.splitext(f_name)
                if ext.lower() == ".png" and base.isdigit():
                    existing_indices.add(int(base))
        
        # target_dir をスキャン (input_dir と同期しているはずだが、念のため両方確認)
        if os.path.exists(target_dir):
            for f_name in os.listdir(target_dir):
                base, ext = os.path.splitext(f_name)
                if ext.lower() == ".png" and base.isdigit():
                    existing_indices.add(int(base))
        
        if existing_indices:
            next_index = max(existing_indices) + 1
        
        base_name = f"{next_index:05d}.png" # 5桁ゼロ埋め
        # --- ここまで修正されたファイル名生成ロジック ---
        
        original_pixmap = QPixmap(self.image_files[self.current_image_index])
        if original_pixmap.isNull():
            QMessageBox.critical(self, "保存エラー", "元の画像の読み込みに失敗しました。")
            self.statusBar().showMessage("元の画像の読み込みに失敗しました。")
            return

        # input画像の保存 (PNG形式)
        if not original_pixmap.save(os.path.join(input_dir, base_name), "PNG"):
            QMessageBox.critical(self, "保存エラー", f"Input画像 ({base_name}) の保存に失敗しました。")
            self.statusBar().showMessage(f"Input画像 ({base_name}) の保存に失敗しました。")
            return
        
        self.background_item.hide() # target画像生成のために背景を一時的に隠す
        
        # 描画領域を取得
        # itemsBoundingRect は描画アイテムのみのバウンディングボックス
        # sceneRect は背景画像に合わせたシーン全体の矩形
        # ここでは描画内容を保存するので itemsBoundingRect を基本とするが、
        # 何も描かれていない場合は背景画像と同じサイズの透明画像とする
        render_rect = self.scene.itemsBoundingRect()
        if render_rect.isNull() or render_rect.isEmpty(): # 何も描画されていない場合
            # 背景画像のサイズで透明なtarget画像を作成
            target_size = self.background_item.pixmap().size()
            render_rect = QRectF(QPointF(0,0), target_size) # 描画元はシーンの(0,0)から背景サイズ
        else:
            # 描画内容が存在する場合、そのバウンディングボックスのサイズにする
            target_size = render_rect.size().toSize()


        if target_size.width() <= 0 or target_size.height() <= 0:
             # フォールバックとして元の画像のサイズを使う (ほぼありえないが念のため)
            target_size = original_pixmap.size()
            if target_size.width() <= 0 or target_size.height() <= 0: # それでもダメならエラー
                QMessageBox.critical(self, "保存エラー", "Target画像のサイズが不正です。")
                self.statusBar().showMessage("Target画像のサイズが不正です。")
                self.background_item.show() # 隠した背景を戻す
                return
            render_rect = QRectF(QPointF(0,0), target_size) # この場合、描画元も調整が必要


        target_pixmap = QPixmap(target_size)
        target_pixmap.fill(Qt.GlobalColor.transparent) # 透明背景で初期化
        
        painter = QPainter(target_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # scene.render に渡す source_rect は、シーンのどの部分を切り出すか
        # ここでは render_rect (描画アイテムのバウンディングボックスまたは背景サイズ) を指定
        self.scene.render(painter, QRectF(target_pixmap.rect()), render_rect)
        painter.end()
        
        if not target_pixmap.save(os.path.join(target_dir, base_name), "PNG"):
            QMessageBox.critical(self, "保存エラー", f"Target画像 ({base_name}) の保存に失敗しました。")
            self.statusBar().showMessage(f"Target画像 ({base_name}) の保存に失敗しました。")
            self.background_item.show() # 隠した背景を戻す
            # 既に保存したinput画像を削除するロールバック処理も考えられる
            # os.remove(os.path.join(input_dir, base_name))
            return
        
        self.background_item.show() # 隠した背景を戻す
        
        self.statusBar().showMessage(f"{base_name} として input/target ペアを保存しました。")
        
        # リストアイテムに進捗マークを付ける
        list_widget_item = self.file_list_widget.item(self.current_image_index)
        if list_widget_item and not list_widget_item.text().startswith("✓ "):
            list_widget_item.setText(f"✓ {list_widget_item.text()}")
            list_widget_item.setForeground(QColor("gray")) # 色をグレーに変更
        
        self.show_next_image() # 自動で次の画像へ

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())