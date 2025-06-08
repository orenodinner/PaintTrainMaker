import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QDockWidget, QListWidget,
    QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QGraphicsView,
    QMenuBar, QStatusBar, QGraphicsScene, QGraphicsPixmapItem, QListWidgetItem,
    QGraphicsPathItem  # 描画アイテムをインポート
)
from PyQt6.QtGui import (
    QAction, QIcon, QPen, QColor, QPainter, QPixmap, QPainterPath
)
from PyQt6.QtCore import Qt, QDir, QPointF, QRectF # QRectF をインポート

# --- 描画用シーンクラス ---
class DrawingScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_path = None
        self.current_path_item = None # リアルタイム描画用のアイテム
        self.pen = QPen(QColor("black"), 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        self.is_drawing = False

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.current_path = QPainterPath()
            self.current_path.moveTo(event.scenePos())
            # リアルタイム表示用のパスアイテムを作成
            self.current_path_item = self.addPath(self.current_path, self.pen)
            self.is_drawing = True

    def mouseMoveEvent(self, event):
        if self.is_drawing:
            self.current_path.lineTo(event.scenePos())
            # パスアイテムのパスを更新してリアルタイムに線が見えるようにする
            self.current_path_item.setPath(self.current_path)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_drawing:
            # 暫定アイテムをNoneにして、描画を確定
            self.current_path_item = None
            self.is_drawing = False

    def clear_drawing(self):
        """描画内容を全てクリアする"""
        items_to_remove = [item for item in self.items() if isinstance(item, QGraphicsPathItem)]
        for item in items_to_remove:
            self.removeItem(item)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.image_files = []
        self.current_image_index = -1
        self.background_item = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("学習データセット作成支援アプリ (MVP)")
        self.setGeometry(100, 100, 1200, 800)

        # (中略) UIの定義は変更なし ...
        # --- メニューバー ---
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("ファイル(&F)")
        open_folder_action = QAction("フォルダを開く...", self)
        open_folder_action.triggered.connect(self.open_folder_dialog)
        file_menu.addAction(open_folder_action)

        # --- 中央のキャンバスエリア ---
        self.scene = DrawingScene(self)
        self.canvas_view = QGraphicsView(self.scene)
        self.setCentralWidget(self.canvas_view)

        # --- 左側: ツールパネル ---
        tools_dock = QDockWidget("ツール", self)
        tools_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        tool_widget = QWidget()
        tool_layout = QVBoxLayout(tool_widget)
        self.pen_button = QPushButton("ペン (B)")
        self.eraser_button = QPushButton("消しゴム (E)")
        tool_layout.addWidget(self.pen_button)
        tool_layout.addWidget(self.eraser_button)
        tool_layout.addStretch()
        tools_dock.setWidget(tool_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, tools_dock)

        # --- 右側: ファイルパネル ---
        files_dock = QDockWidget("ファイル一覧", self)
        files_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        file_widget = QWidget()
        file_layout = QVBoxLayout(file_widget)
        self.file_list_widget = QListWidget()
        self.file_list_widget.currentItemChanged.connect(self.on_file_selected)

        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("< 前へ")
        self.next_button = QPushButton("> 次へ")
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
        files_dock.setWidget(file_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, files_dock)

        # --- ステータスバー ---
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("準備完了。ファイル > フォルダを開く... から開始してください。")


    def open_folder_dialog(self):
        """フォルダを開き、中の画像ファイルをリストに表示する"""
        home_dir = QDir.homePath()
        dir_path = QFileDialog.getExistingDirectory(self, "フォルダを選択", home_dir)

        if dir_path:
            self.image_files = []
            self.file_list_widget.clear()
            supported_formats = [".png", ".jpg", ".jpeg", ".bmp"]
            
            for filename in sorted(os.listdir(dir_path)):
                if any(filename.lower().endswith(fmt) for fmt in supported_formats):
                    full_path = os.path.join(dir_path, filename)
                    self.image_files.append(full_path)
                    item = QListWidgetItem(filename)
                    self.file_list_widget.addItem(item)
            
            if self.image_files:
                self.file_list_widget.setCurrentRow(0)
                self.statusBar().showMessage(f"{len(self.image_files)}個の画像を読み込みました。")
            else:
                self.statusBar().showMessage("選択されたフォルダに画像ファイルが見つかりませんでした。")

    def on_file_selected(self, current_item, previous_item):
        if current_item is None:
            return
        
        index = self.file_list_widget.row(current_item)
        if index != self.current_image_index:
            self.current_image_index = index
            self.load_image_to_canvas()

    def load_image_to_canvas(self):
        """現在のインデックスの画像をキャンバスに読み込む"""
        if self.current_image_index < 0 or self.current_image_index >= len(self.image_files):
            return

        image_path = self.image_files[self.current_image_index]
        pixmap = QPixmap(image_path)
        
        # 既存の背景をクリア
        if self.background_item:
            self.scene.removeItem(self.background_item)
        
        # 既存の描画をクリア
        self.scene.clear_drawing()

        # 新しい背景画像を設定
        self.background_item = QGraphicsPixmapItem(pixmap)
        self.background_item.setOpacity(0.5)
        self.background_item.setZValue(-1)
        self.scene.addItem(self.background_item)

        # ★★★★★★★★★★★★★★★★★★★
        # ★★★ ここが修正箇所 ★★★
        # ★★★★★★★★★★★★★★★★★★★
        self.scene.setSceneRect(QRectF(pixmap.rect()))
        
        self.canvas_view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.statusBar().showMessage(f"表示中: {os.path.basename(image_path)}")

    def show_prev_image(self):
        if self.current_image_index > 0:
            self.file_list_widget.setCurrentRow(self.current_image_index - 1)

    def show_next_image(self):
        if self.current_image_index < len(self.image_files) - 1:
            self.file_list_widget.setCurrentRow(self.current_image_index + 1)
    
    def save_dataset_pair(self):
        if self.current_image_index < 0:
            self.statusBar().showMessage("保存対象の画像がありません。")
            return

        # 1. 保存先フォルダを選択 (初回のみ)
        if not hasattr(self, 'save_dir') or not self.save_dir:
            self.save_dir = QFileDialog.getExistingDirectory(self, "データセットの保存先フォルダを選択")
            if not self.save_dir:
                self.statusBar().showMessage("保存がキャンセルされました。")
                return
        
        # 2. inputとtargetフォルダを作成
        input_dir = os.path.join(self.save_dir, "input")
        target_dir = os.path.join(self.save_dir, "target")
        os.makedirs(input_dir, exist_ok=True)
        os.makedirs(target_dir, exist_ok=True)

        # 3. 連番ファイル名を決定
        file_count = len(os.listdir(input_dir))
        base_name = f"{file_count:05d}.png"

        # 4. 元画像の保存
        original_image_path = self.image_files[self.current_image_index]
        original_pixmap = QPixmap(original_image_path)
        original_pixmap.save(os.path.join(input_dir, base_name))

        # 5. 線画の保存
        self.background_item.hide()
        
        # シーンのバウンディングレクタングルを計算して正確なサイズを取得
        rect = self.scene.itemsBoundingRect()
        target_pixmap = QPixmap(rect.size().toSize())
        target_pixmap.fill(Qt.GlobalColor.transparent)
        
        painter = QPainter(target_pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # シーンの描画範囲と描画先を指定
        self.scene.render(painter, QRectF(target_pixmap.rect()), rect)
        painter.end()

        target_pixmap.save(os.path.join(target_dir, base_name))
        
        self.background_item.show()
        
        self.statusBar().showMessage(f"{base_name} としてペアを保存しました。")
        self.show_next_image()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())