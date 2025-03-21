import math
import threading
import time
import os
from queue import Queue
import flet as ft
from flet import (
    ButtonStyle,
    Column,
    Container,
    ElevatedButton,
    FilePicker,
    FilePickerResultEvent,
    Icon,
    IconButton,
    Page,
    ProgressBar,
    RoundedRectangleBorder,
    Row,
    Slider,
    Text,
    Theme,
    WindowDragArea,
    alignment,
    border_radius,
    padding,
    Image,
    MainAxisAlignment,
    CrossAxisAlignment,
    TextField,
)
from flet import Icons, Colors
import cv2
import numpy as np
from PIL import Image as PILImage
import io
import base64
import tifffile
from utils.config import NUM_WORKERS


# アプリケーション状態を管理するクラス
class AppState:
    def __init__(self, page):
        self.page = page
        self.current_file_path = ""
        self.current_file_name = ""
        self.current_frame = 0
        self.total_frames = 0
        self.is_playing = False
        self.listeners = []

    def set_file_info(self, file_path, total_frames):
        self.current_file_path = file_path
        self.current_file_name = os.path.basename(file_path) if file_path else ""
        self.total_frames = total_frames
        self.notify_listeners()

    def set_current_frame(self, frame_number):
        self.current_frame = frame_number
        self.notify_listeners()

    def set_playing(self, is_playing):
        self.is_playing = is_playing
        self.notify_listeners()

    def clear_file(self):
        self.current_file_path = ""
        self.current_file_name = ""
        self.total_frames = 0
        self.current_frame = 0
        self.is_playing = False
        self.notify_listeners()

    def add_listener(self, listener):
        self.listeners.append(listener)

    def notify_listeners(self):
        for listener in self.listeners:
            listener(self)
        self.page.update()


class WindowControlButton(IconButton):
    def __init__(self, *args, icon_size: int, **kwargs):
        super().__init__(*args, icon_size=icon_size, **kwargs)
        self.height = 35
        self.width = 45
        self.style = ButtonStyle(
            shape=RoundedRectangleBorder(),
            color="#E0E0E0",  # ダークモード用の明るい色
            overlay_color="#424242",  # ホバー時の色
        )


# class WindowTitleBar(Container):
#     ICON_SIZE = 15
#     HEIGHT = 30

#     def __init__(
#         self, title: str, page: Page, app_state: AppState, on_open_file=None
#     ) -> None:
#         super().__init__()
#         self.page = page
#         self.base_title = title
#         self.on_open_file = on_open_file
#         self.app_state = app_state

#         # 状態変更をリッスン
#         app_state.add_listener(self.on_state_change)

#         # タイトルテキスト
#         self.title_text = Text(
#             self.base_title,
#             color="#E0E0E0",
#         )

#         # ボタンの初期化
#         self.maximize_button = WindowControlButton(
#             Icons.CROP_SQUARE_SHARP,
#             icon_size=self.ICON_SIZE,
#             rotate=math.pi,
#             on_click=self.maximized_button_clicked,
#         )
#         self.minimize_button = WindowControlButton(
#             Icons.MINIMIZE_SHARP,
#             icon_size=self.ICON_SIZE,
#             on_click=self.minimize_button_clicked,
#         )
#         self.close_button = WindowControlButton(
#             Icons.CLOSE_SHARP,
#             icon_size=self.ICON_SIZE,
#             on_click=lambda _: self.page.window.close(),
#         )

#         # メニューの作成
#         self.file_menu = ft.PopupMenuButton(
#             content=Text("ファイル", color="#E0E0E0"),
#             items=[
#                 ft.PopupMenuItem(
#                     text="開く...",
#                     icon=Icons.FOLDER_OPEN,
#                     on_click=lambda _: (
#                         self.on_open_file() if self.on_open_file else None
#                     ),
#                 ),
#                 ft.PopupMenuItem(
#                     text="終了",
#                     icon=Icons.EXIT_TO_APP,
#                     on_click=lambda _: self.page.window.close(),
#                 ),
#             ],
#         )

#         self.content = Row(
#             [
#                 WindowDragArea(
#                     Row(
#                         [
#                             Container(
#                                 Icon(
#                                     Icons.MOVIE,
#                                     color="#E0E0E0",
#                                     size=self.ICON_SIZE,
#                                 ),
#                                 padding=padding.only(5, 2, 0, 2),
#                             ),
#                             self.title_text,
#                         ],
#                         height=self.HEIGHT,
#                         alignment=alignment.center,
#                         # alignment=MainAxisAlignment.CENTER,
#                     ),
#                     expand=True,
#                 ),
#                 self.file_menu,
#                 self.minimize_button,
#                 self.maximize_button,
#                 self.close_button,
#             ],
#             spacing=0,
#         )
#         self.bgcolor = "#212121"  # ダークモード用の暗い色

#     def on_state_change(self, state):
#         # ファイル名が設定されている場合、タイトルをファイル名に変更
#         if state.current_file_name:
#             self.title_text.value = state.current_file_name
#         else:
#             self.title_text.value = self.base_title

#     def minimize_button_clicked(self, e):
#         self.page.window_minimized = True
#         self.page.update()

#     def maximized_button_clicked(self, e):
#         self.page.window.maximized = True if not self.page.window.maximized else False
#         self.page.update()

#         if self.page.window.maximized:
#             self.maximize_button.icon = Icons.FILTER_NONE
#             self.maximize_button.icon_size = 12
#         else:
#             self.maximize_button.icon = Icons.CROP_SQUARE_SHARP
#             self.maximize_button.icon_size = 15
#         self.update()


class WindowTitleBar(Container):
    ICON_SIZE = 15
    HEIGHT = 30

    def __init__(
        self, title: str, page: Page, app_state: AppState, on_open_file=None
    ) -> None:
        super().__init__()
        self.page = page
        self.base_title = title
        self.on_open_file = on_open_file
        self.app_state = app_state

        # 状態変更をリッスン
        app_state.add_listener(self.on_state_change)

        # タイトルテキスト
        self.title_text = Text(
            self.base_title,
            color="#E0E0E0",
        )

        # アプリケーションアイコン
        self.app_icon = Container(
            content=Icon(
                Icons.MOVIE,
                color="#E0E0E0",
                size=self.ICON_SIZE,
            ),
            padding=padding.only(left=10, right=5),  # アイコンの余白を調整
        )

        # ボタンの初期化
        self.maximize_button = WindowControlButton(
            Icons.CROP_SQUARE_SHARP,
            icon_size=self.ICON_SIZE,
            rotate=math.pi,
            on_click=self.maximized_button_clicked,
        )
        self.minimize_button = WindowControlButton(
            Icons.MINIMIZE_SHARP,
            icon_size=self.ICON_SIZE,
            on_click=self.minimize_button_clicked,
        )
        self.close_button = WindowControlButton(
            Icons.CLOSE_SHARP,
            icon_size=self.ICON_SIZE,
            on_click=lambda _: self.page.window.close(),
        )

        # メニューの作成
        # self.file_menu = ft.PopupMenuButton(
        #     content=Text("ファイル", color="#E0E0E0"),
        #     items=[
        #         ft.PopupMenuItem(
        #             text="開く...",
        #             icon=Icons.FOLDER_OPEN,
        #             on_click=lambda _: (
        #                 self.on_open_file() if self.on_open_file else None
        #             ),
        #         ),
        #         ft.PopupMenuItem(
        #             text="終了",
        #             icon=Icons.EXIT_TO_APP,
        #             on_click=lambda _: self.page.window.close(),
        #         ),
        #     ],
        # )

        # メニューの作成
        self.file_menu = Row(
            [
                Container(
                    content=ft.PopupMenuButton(
                        content=Text("ファイル", color="#E0E0E0"),
                        items=[
                            ft.PopupMenuItem(
                                text="開く...",
                                icon=Icons.FOLDER_OPEN,
                                on_click=lambda _: (
                                    self.on_open_file() if self.on_open_file else None
                                ),
                            ),
                            ft.PopupMenuItem(
                                text="終了",
                                icon=Icons.EXIT_TO_APP,
                                on_click=lambda _: self.page.window.close(),
                            ),
                        ],
                    ),
                    padding=padding.only(left=8, right=4),  # 左右のパディングを追加
                ),
                Container(
                    content=ft.PopupMenuButton(
                        content=Text("ヘルプ", color="#E0E0E0"),
                        items=[
                            ft.PopupMenuItem(
                                text="バージョン情報",
                                icon=Icons.INFO,
                                on_click=lambda _: self.show_version_info(),
                            ),
                        ],
                    ),
                    padding=padding.only(left=4, right=8),  # 左右のパディングを追加
                ),
            ],
            spacing=5,  # メニュー項目間の間隔を追加
        )

        # 左側のコンテンツ（ファイルメニュー）
        left_content = Container(
            content=self.file_menu,
            alignment=alignment.center_left,
        )

        # 中央のコンテンツ（タイトル）
        center_content = Container(
            content=Row(
                [
                    Icon(
                        Icons.MOVIE,
                        color="#E0E0E0",
                        size=self.ICON_SIZE,
                    ),
                    self.title_text,
                ],
                alignment=MainAxisAlignment.CENTER,
            ),
            expand=True,
            alignment=alignment.center,
        )

        # 右側のコンテンツ（ウィンドウコントロール）
        right_content = Row(
            [
                self.minimize_button,
                self.maximize_button,
                self.close_button,
            ],
            spacing=0,
        )

        self.content = WindowDragArea(
            Row(
                [
                    left_content,
                    center_content,
                    right_content,
                ],
                spacing=0,
            ),
        )
        self.bgcolor = "#212121"  # ダークモード用の暗い色

    def on_state_change(self, state):
        # ファイル名が設定されている場合、タイトルをファイル名に変更
        if state.current_file_name:
            self.title_text.value = state.current_file_name
        else:
            self.title_text.value = self.base_title

    def minimize_button_clicked(self, e):
        self.page.window_minimized = True
        self.page.update()

    def maximized_button_clicked(self, e):
        self.page.window.maximized = True if not self.page.window.maximized else False
        self.page.update()

        if self.page.window.maximized:
            self.maximize_button.icon = Icons.FILTER_NONE
            self.maximize_button.icon_size = 12
        else:
            self.maximize_button.icon = Icons.CROP_SQUARE_SHARP
            self.maximize_button.icon_size = 15
        self.update()


class TiffPlayer:
    def __init__(self, page: Page, app_state: AppState):
        self.page = page
        self.app_state = app_state
        self.frames = []
        self.frame_count = 0
        self.current_frame = 0
        self.is_playing = False
        self.fps = 10  # デフォルトのフレームレート
        self.frame_queue = Queue(maxsize=30)  # フレームバッファ用キュー
        self.preload_thread = None
        self.play_thread = None
        self.stop_threads = False

        # UIコンポーネント
        self.file_picker = FilePicker(on_result=self.file_picker_result)
        self.page.overlay.append(self.file_picker)

        self.loading_progress = ProgressBar(visible=False, width=400, color="#2196F3")

        # スライダー（1行目）
        self.frame_slider = Slider(
            min=0,
            max=100,
            value=0,
            divisions=100,
            on_change=self.slider_changed,
            visible=False,
            expand=True,
            active_color="#2196F3",
            inactive_color="#757575",
        )

        # フレームカウンター（テキストフィールド化）
        self.frame_counter_field = TextField(
            value="0",
            width=80,
            text_align="right",
            visible=False,
            on_submit=self.frame_field_submitted,
            border_color="#424242",
            focused_border_color="#2196F3",
            color="#E0E0E0",
        )

        self.total_frames_text = Text(
            "/0",
            visible=False,
            color="#E0E0E0",
        )

        # 再生コントロール
        self.play_button = IconButton(
            Icons.PLAY_ARROW,
            icon_size=30,
            on_click=self.toggle_play,
            visible=False,
            icon_color="#E0E0E0",
            style=ButtonStyle(
                overlay_color="#424242",
            ),
        )
        self.prev_button = IconButton(
            Icons.SKIP_PREVIOUS,
            icon_size=30,
            on_click=self.prev_frame,
            visible=False,
            icon_color="#E0E0E0",
            style=ButtonStyle(
                overlay_color="#424242",
            ),
        )
        self.next_button = IconButton(
            Icons.SKIP_NEXT,
            icon_size=30,
            on_click=self.next_frame,
            visible=False,
            icon_color="#E0E0E0",
            style=ButtonStyle(
                overlay_color="#424242",
            ),
        )

        # FPS調整
        self.fps_text = Text(
            "FPS: 10", visible=False, color="#E0E0E0", width=60, text_align="right"
        )
        self.fps_slider = Slider(
            min=1,
            max=100,
            value=10,
            divisions=29,
            on_change=self.fps_changed,
            visible=False,
            width=120,
            active_color="#2196F3",
            inactive_color="#757575",
        )

        self.image_view = Image(
            src=None,
            fit="contain",
            width=600,
            height=400,
        )

        # ファイル選択前の表示テキスト
        self.no_file_text = Text(
            "ファイルを選択してください",
            size=16,
            color="#AAAAAA",
            weight="bold",
        )

        self.open_button = ElevatedButton(
            "TIFFファイルを開く",
            icon=Icons.FOLDER_OPEN,
            on_click=lambda _: self.file_picker.pick_files(
                allowed_extensions=["tif", "tiff"]
            ),
            style=ButtonStyle(
                color="#E0E0E0",
                bgcolor="#2196F3",
            ),
            visible=False,  # ボタンを非表示（タイトルバーからのみ操作）
        )

        self.file_info = Text("", style="bodySmall", color="#E0E0E0")

    def create_layout(self):
        # 画像表示コンテナ
        self.image_view.visible = False

        self.image_container = Container(
            content=Column(
                [self.no_file_text, self.image_view],
                alignment=MainAxisAlignment.CENTER,
                horizontal_alignment=CrossAxisAlignment.CENTER,
            ),
            alignment=alignment.center,
            border_radius=border_radius.all(10),
            bgcolor="#1E1E1E",  # ダークモード用の色
            padding=10,
            expand=True,  # 高さを拡張して利用可能な空間を使用
        )

        # 再生コントロールパネル
        self.control_panel = Container(
            content=Column(
                [
                    # 1行目: スライダー
                    Row(
                        [self.frame_slider],
                        alignment=MainAxisAlignment.START,
                    ),
                    # 2行目: FPS設定、再生コントロール、フレームカウンター
                    Row(
                        [
                            # 左: FPS設定
                            Row(
                                [self.fps_text, self.fps_slider],
                                alignment=MainAxisAlignment.START,
                            ),
                            # 中央: 再生コントロール
                            Row(
                                [self.prev_button, self.play_button, self.next_button],
                                alignment=MainAxisAlignment.CENTER,
                            ),
                            # 右: フレームカウンター
                            Row(
                                [self.frame_counter_field, self.total_frames_text],
                                alignment=MainAxisAlignment.END,
                            ),
                        ],
                        alignment=MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=5,
            ),
            padding=padding.all(10),
            bgcolor="#212121",
            visible=False,  # 最初は非表示
        )

        return Column(
            [
                Container(
                    content=Column(
                        [
                            # 進捗バーのみを残す
                            self.loading_progress,
                            # メインコンテンツ（画像表示）
                            self.image_container,
                        ],
                        horizontal_alignment=CrossAxisAlignment.CENTER,
                        expand=True,
                    ),
                    padding=padding.all(10),
                    expand=True,
                ),
                # 再生コントロールパネル（下部固定）
                self.control_panel,
            ],
            expand=True,
        )

    def frame_field_submitted(self, e):
        """フレームカウンターフィールドが編集されたときの処理"""
        try:
            frame_index = int(e.control.value) - 1  # 0-indexedに変換
            frame_index = max(
                0, min(frame_index, self.frame_count - 1)
            )  # 範囲内に収める
            self.display_frame(frame_index)
        except ValueError:
            # 無効な入力の場合は現在のフレーム番号に戻す
            e.control.value = str(self.current_frame + 1)
            self.page.update()

    def file_picker_result(self, e: FilePickerResultEvent):
        if e.files and len(e.files) == 1:
            self.stop_playback()
            file_path = e.files[0].path
            file_name = os.path.basename(file_path)

            # UIリセット
            self.loading_progress.visible = True
            self.file_info.value = f"ファイル: {file_name} (読み込み中...)"
            self.no_file_text.visible = False
            self.page.update()

            # 別スレッドで読み込み
            threading.Thread(target=self.load_tiff, args=(file_path,)).start()
        else:
            # ファイル選択がキャンセルされた場合
            if not self.app_state.current_file_path:
                self.no_file_text.visible = True
                self.image_view.visible = False
                self.page.update()

    def load_tiff(self, file_path):
        try:
            # フレームをリセット
            self.frames = []
            self.frame_count = 0

            # まずtifffileライブラリでTIFFを読み込む
            try:
                # tifffileを使って読み込み
                with tifffile.TiffFile(file_path) as tif:
                    total_frames = len(tif.pages)
                    print("loading tifffile...")
                    print(f"total frames: {total_frames}")
                    print(f"size: {tif.pages[0].shape}")
                    for i, page in enumerate(tif.pages):
                        # ページを画像として読み込む
                        img = page.asarray()

                        img = self._convert_to_rgb(img)

                        self.frames.append(img)
                        self.frame_count += 1

                        # 進捗更新
                        self.loading_progress.value = (i + 1) / total_frames
                        self.page.update()
                    print("complete loading tifffile!")
                # 読み込みが成功したのでUIを更新
                self.update_ui_after_loading(file_path)
                return
            except Exception as pil_err:
                print(f"failed to load tiff file: {str(pil_err)}")
                # 両方のメソッドが失敗した場合
                raise Exception("サポートされていないTIFFフォーマットです")

        except Exception as e:
            self.file_info.value = f"エラー: {str(e)}"
            self.loading_progress.visible = False
            self.no_file_text.visible = True
            self.image_view.visible = False
            self.app_state.clear_file()
            self.page.update()

    def _convert_to_rgb(self, img):
        print(f"Original data type: {img.dtype}, Shape: {img.shape}")

        # For 16-bit integers
        if img.dtype != np.uint8:
            print("Converting image to 8-bit")
            min_val = np.min(img)
            max_val = np.max(img)
            img = ((img - min_val) / (max_val - min_val) * 255).astype(np.uint8)

        # Convert grayscale to RGB
        if img.ndim == 2:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
            print("Conversion successful (Grayscale to RGB)")
        else:
            img_rgb = img
            print("Already in RGB format or unsupported")

        return img_rgb

    def update_ui_after_loading(self, file_path):
        """読み込み成功後のUI更新処理"""
        if self.frame_count > 0:
            # アプリケーション状態を更新
            self.app_state.set_file_info(file_path, self.frame_count)

            # コントロールパネルの更新
            self.frame_slider.max = max(0, self.frame_count - 1)
            self.frame_slider.divisions = max(1, self.frame_count - 1)
            self.frame_slider.value = 0
            self.frame_counter_field.value = "1"
            self.total_frames_text.value = f"/{self.frame_count}"
            self.current_frame = 0

            # コントロールを表示
            self.show_controls()

            # 最初のフレームを表示
            self.display_frame(0)
        else:
            self.file_info.value = f"エラー: フレームを読み込めませんでした"
            self.loading_progress.visible = False
            self.no_file_text.visible = True
            self.image_view = False
            self.app_state.clear_file()
            self.page.update()

    def show_controls(self):
        self.loading_progress.visible = False
        self.frame_slider.visible = True
        self.frame_counter_field.visible = True
        self.total_frames_text.visible = True
        self.play_button.visible = True
        self.prev_button.visible = True
        self.next_button.visible = True
        self.fps_text.visible = True
        self.fps_slider.visible = True
        self.no_file_text.visible = False
        self.control_panel.visible = True
        self.page.update()

    def display_frame(self, frame_index):
        print("frame index: ", frame_index)
        print("frame count: ", self.frame_count)
        print("frames: ", self.frames)
        if 0 <= frame_index < self.frame_count:
            frame = self.frames[frame_index]

            # NumPy配列をPIL画像に変換
            pil_img = PILImage.fromarray(frame)

            # PILイメージをbase64エンコードしてfletのイメージとして表示
            with io.BytesIO() as output:
                pil_img.save(output, format="PNG")
                img_base64 = base64.b64encode(output.getvalue()).decode("utf-8")

            self.image_view.visible = True
            self.image_view.src_base64 = img_base64
            self.current_frame = frame_index
            self.frame_slider.value = frame_index
            self.frame_counter_field.value = str(frame_index + 1)

            # アプリケーション状態を更新
            self.app_state.set_current_frame(frame_index)

            self.page.update()

    def slider_changed(self, e):
        frame_index = int(e.control.value)
        self.display_frame(frame_index)

    def fps_changed(self, e):
        self.fps = int(e.control.value)
        self.fps_text.value = f"FPS: {self.fps}"
        self.page.update()

    def toggle_play(self, e=None):
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()

        # 再生状態をアプリケーション状態に反映
        self.app_state.set_playing(self.is_playing)

    def start_playback(self):
        if not self.is_playing and self.frame_count > 0:
            self.is_playing = True
            self.play_button.icon = Icons.PAUSE
            self.stop_threads = False

            # 既存のスレッドを終了させる
            if self.play_thread and self.play_thread.is_alive():
                self.stop_threads = True
                self.play_thread.join(timeout=0.5)

            if self.preload_thread and self.preload_thread.is_alive():
                self.preload_thread.join(timeout=0.5)

            # キューをクリア
            with self.frame_queue.mutex:
                self.frame_queue.queue.clear()

            self.stop_threads = False

            # フレームをプリロードするスレッド
            self.preload_thread = threading.Thread(target=self.preload_frames)
            self.preload_thread.daemon = True

            # 再生スレッド
            self.play_thread = threading.Thread(target=self.play_frames)
            self.play_thread.daemon = True

            # スレッド開始
            self.preload_thread.start()
            self.play_thread.start()

            self.page.update()

    def preload_frames(self):
        """次のフレームをキューに追加するスレッド"""
        current_idx = self.current_frame

        while not self.stop_threads:
            try:
                # キューが満杯でなければフレームを追加
                if not self.frame_queue.full():
                    next_idx = (current_idx + 1) % self.frame_count

                    # フレームとインデックスをキューに追加
                    self.frame_queue.put((next_idx, self.frames[next_idx]))
                    current_idx = next_idx

                time.sleep(0.001)  # 少し待機してCPU使用率を下げる
            except Exception as e:
                print(f"プリロードエラー: {str(e)}")
                time.sleep(0.1)  # エラー時に少し待機

    def play_frames(self):
        frame_time = 1.0 / self.fps

        while not self.stop_threads and self.is_playing:
            start_time = time.time()

            try:
                # キューからフレームを取得（ブロックせずにタイムアウト設定）
                next_idx, _ = self.frame_queue.get(timeout=0.5)

                # ローカル変数にインデックスを保存（クロージャでの参照問題を回避）
                frame_idx = next_idx

                # UIを直接更新（非同期なし）
                self.current_frame = frame_idx
                self.frame_slider.value = frame_idx
                self.frame_counter_field.value = str(frame_idx + 1)

                # フレーム画像を更新
                frame = self.frames[frame_idx]
                pil_img = PILImage.fromarray(frame)

                with io.BytesIO() as output:
                    pil_img.save(output, format="PNG")
                    img_base64 = base64.b64encode(output.getvalue()).decode("utf-8")

                self.image_view.src_base64 = img_base64

                # アプリケーション状態を更新
                self.app_state.set_current_frame(frame_idx)

                self.page.update()  # ページを更新

                # 処理時間を計算して、必要に応じて待機
                process_time = time.time() - start_time
                sleep_time = max(0, frame_time - process_time)
                time.sleep(sleep_time)

            except Exception as e:
                # キューからのタイムアウトやその他のエラー
                print(f"再生エラー: {str(e)}")
                time.sleep(0.1)  # エラー時に少し待機

        # スレッド終了時にUIを更新
        self.is_playing = False
        self.play_button.icon = Icons.PLAY_ARROW
        self.app_state.set_playing(False)
        self.page.update()

    def stop_playback(self):
        """再生を停止する"""
        if self.is_playing:
            # スレッドを停止するフラグを設定
            self.stop_threads = True
            self.is_playing = False
            self.play_button.icon = Icons.PLAY_ARROW

            # アプリケーション状態を更新
            self.app_state.set_playing(False)

            # UIを即時更新
            self.page.update()

            # キューをクリア（ロックを使用）
            with self.frame_queue.mutex:
                self.frame_queue.queue.clear()

            # スレッドの終了を待機（ただし長時間ブロックしない）
            if self.play_thread and self.play_thread.is_alive():
                self.play_thread.join(timeout=0.5)

            if self.preload_thread and self.preload_thread.is_alive():
                self.preload_thread.join(timeout=0.5)

    def next_frame(self, e):
        if self.frame_count > 0:
            next_idx = (self.current_frame + 1) % self.frame_count
            self.display_frame(next_idx)

    def prev_frame(self, e):
        if self.frame_count > 0:
            prev_idx = (self.current_frame - 1) % self.frame_count
            self.display_frame(prev_idx)


class Content(Container):
    def __init__(self, page: Page, app_state: AppState):
        super().__init__()
        self.tiff_player = TiffPlayer(page, app_state)

        self.content = self.tiff_player.create_layout()
        self.padding = padding.all(0)
        self.expand = True
        self.bgcolor = "#1A1A1A"  # ダークモードの背景色


class MainWindow(Container):
    def __init__(self, page: Page, window_title: str):
        super().__init__()
        page.window.frameless = True
        page.window_title_bar_hidden = True
        page.window_title_bar_buttons_hidden = True
        page.padding = 0

        page.theme_mode = "dark"
        page.theme = Theme(color_scheme_seed="blue")
        self.page = page

        # アプリケーション状態の作成
        self.app_state = AppState(page)

        # コンテンツを先に作成
        self.content_container = Content(page, self.app_state)

        # タイトルバーにファイル選択関数を渡す
        self.title_bar = WindowTitleBar(
            "TIFF動画プレーヤー",
            self.page,
            self.app_state,
            on_open_file=lambda: self.content_container.tiff_player.file_picker.pick_files(
                allowed_extensions=["tif", "tiff"]
            ),
        )

        self.content = Column(
            [
                self.title_bar,
                self.content_container,
            ],
            spacing=0,
        )
        self.bgcolor = "#121212"  # ダークモードのバックグラウンド
        self.expand = True


def main(page: Page):
    # Fletのテーマと設定
    page.theme = Theme(
        color_scheme_seed=Colors.BLUE,
        # color_scheme_seed_color="#2196F3",
        use_material3=True,
        visual_density="comfortable",
    )
    page.theme_mode = "dark"

    app = MainWindow(page, window_title="TIFF動画プレーヤー")
    page.add(app)


if __name__ == "__main__":
    ft.app(main)
