import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QFileDialog, QDockWidget, QListWidget,
    QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QGraphicsView,
    QMenuBar, QStatusBar
)
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import Qt, QDir, QSize

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """UIの初期化とレイアウト設定を行う"""
        self.setWindowTitle("学習データセット作成支援アプリ")
        self.setGeometry(100, 100, 1200, 800)  # ウィンドウの初期位置とサイズ

        # --- メニューバーの作成 ---
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("ファイル(&F)")

        open_folder_action = QAction("フォルダを開く...", self)
        open_folder_action.setShortcut("Ctrl+O")
        open_folder_action.triggered.connect(self.open_folder_dialog)
        file_menu.addAction(open_folder_action)

        # --- 中央のキャンバスエリア ---
        self.canvas_view = QGraphicsView()
        self.setCentralWidget(self.canvas_view)

        # --- 左側: ツールパネル（Dock Widget） ---
        tools_dock = QDockWidget("ツール", self)
        tools_dock.setObjectName("tools_dock")
        tools_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)

        # ツールパネルの中身を作成
        tool_widget = QWidget()
        tool_layout = QVBoxLayout()
        tool_widget.setLayout(tool_layout)

        self.pen_button = QPushButton("ペン (B)")
        self.eraser_button = QPushButton("消しゴム (E)")
        # TODO: 将来的にブラシ設定などをここに追加

        tool_layout.addWidget(self.pen_button)
        tool_layout.addWidget(self.eraser_button)
        tool_layout.addStretch() # ボタンを上部に寄せる

        tools_dock.setWidget(tool_widget)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, tools_dock)

        # --- 右側: ファイルパネル（Dock Widget） ---
        files_dock = QDockWidget("ファイル一覧", self)
        files_dock.setObjectName("files_dock")
        files_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)

        # ファイルパネルの中身を作成
        file_widget = QWidget()
        file_layout = QVBoxLayout()
        file_widget.setLayout(file_layout)

        self.file_list_widget = QListWidget()
        # TODO: 将来的にサムネイル表示に対応

        nav_layout = QHBoxLayout()
        self.prev_button = QPushButton("< 前へ")
        self.next_button = QPushButton("> 次へ")
        nav_layout.addWidget(self.prev_button)
        nav_layout.addWidget(self.next_button)

        self.save_button = QPushButton("保存 (Ctrl+S)")
        self.save_button.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;") # 目立たせる

        file_layout.addWidget(self.file_list_widget)
        file_layout.addLayout(nav_layout)
        file_layout.addWidget(self.save_button)

        files_dock.setWidget(file_widget)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, files_dock)

        # --- ステータスバー ---
        self.setStatusBar(QStatusBar(self))

    def open_folder_dialog(self):
        """
        「フォルダを開く」ダイアログを表示し、選択されたフォルダのパスを取得する
        """
        home_dir = QDir.homePath()
        dir_path = QFileDialog.getExistingDirectory(self, "フォルダを選択", home_dir)

        if dir_path:
            # フォルダが選択された場合の処理（Step 3で実装）
            print(f"選択されたフォルダ: {dir_path}")
            # ここでファイルリストを更新する処理を後ほど追加する


# アプリケーションのエントリポイント
if __name__ == '__main__':
    # PyQt6の依存関係をインストールするように促す（親切なメッセージ）
    try:
        from PyQt6 import QtWidgets
    except ImportError:
        print("エラー: PyQt6がインストールされていません。")
        print("以下のコマンドでインストールしてください:")
        print("pip install PyQt6")
        sys.exit(1)
        
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())