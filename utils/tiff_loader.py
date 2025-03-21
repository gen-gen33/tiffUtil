import threading
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import cv2
import tifffile
import os
import warnings


class TiffLoader:
    """
    マルチスレッドTIFF読み込み処理クラス（エラー処理強化版）
    """

    def __init__(self, max_workers=None):
        """
        初期化

        Args:
            max_workers: スレッドプールで使用する最大ワーカー数
                        Noneの場合はCPUコア数×2 (デフォルト)
        """
        self.max_workers = (
            max_workers if max_workers is not None else os.cpu_count() * 2
        )
        self._stop_event = threading.Event()
        self._progress_callback = None
        self._error_callback = None
        self._complete_callback = None

    def load_tiff(
        self,
        file_path,
        progress_callback=None,
        error_callback=None,
        complete_callback=None,
    ):
        """
        TIFFファイルを非同期に読み込む

        Args:
            file_path: 読み込むTIFFファイルのパス
            progress_callback: 進捗を通知するコールバック関数 (引数: 進捗率0.0-1.0)
            error_callback: エラー発生時のコールバック関数 (引数: エラーメッセージ)
            complete_callback: 完了時のコールバック関数 (引数: フレームリスト, フレーム数)
        """
        self._progress_callback = progress_callback
        self._error_callback = error_callback
        self._complete_callback = complete_callback
        self._stop_event.clear()

        # 別スレッドで読み込み処理を開始
        threading.Thread(
            target=self._load_tiff_thread, args=(file_path,), daemon=True
        ).start()

    def stop(self):
        """読み込み処理を停止する"""
        self._stop_event.set()

    def _load_tiff_thread(self, file_path):
        """TIFFファイル読み込みスレッド"""
        try:
            # tifffileの警告を一時的に抑制
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)

                # まずtifffileライブラリでTIFFを開いてみる
                try:
                    with tifffile.TiffFile(file_path) as tif:
                        # エラーが出やすいタグ処理をスキップするオプションを使用
                        return self._process_with_tifffile(tif)
                except Exception as tiff_err:
                    print(f"tifffileでの読み込みに失敗: {str(tiff_err)}")
                    # tifffileでの読み込みに失敗した場合は、OpenCVで試みる
                    return self._process_with_opencv(file_path)

        except Exception as e:
            print(f"TIFFファイルの読み込みエラー: {str(e)}")
            if self._error_callback:
                self._error_callback(f"TIFFファイルの読み込みエラー: {str(e)}")

    def _process_with_tifffile(self, tif):
        """tifffileライブラリを使ってTIFFを処理"""
        try:
            total_frames = len(tif.pages)
            frames = [None] * total_frames  # 結果を格納する配列を事前に確保

            if total_frames == 0:
                if self._error_callback:
                    self._error_callback("フレームが見つかりませんでした")
                return False

            print(f"総フレーム数: {total_frames}")
            print(f"使用スレッド数: {self.max_workers}")

            # ThreadPoolExecutorを使用して並列処理
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # 各フレームの読み込みをスケジュール
                futures = {}
                for i in range(total_frames):
                    if self._stop_event.is_set():
                        break

                    # 各フレームをスレッドプールで読み込む
                    future = executor.submit(self._load_frame_safe, tif, i)
                    futures[future] = i

                # 完了したフューチャーを処理
                completed = 0
                for future in futures:
                    if self._stop_event.is_set():
                        break

                    try:
                        frame_idx = futures[future]
                        frame_result = future.result()

                        # フレーム読み込みに成功した場合
                        if frame_result is not None:
                            frames[frame_idx] = frame_result
                            completed += 1

                            # 進捗通知
                            if self._progress_callback:
                                self._progress_callback(completed / total_frames)
                        else:
                            print(f"フレーム {frame_idx} の読み込みに失敗")

                    except Exception as e:
                        print(f"フレーム {futures[future]} の処理エラー: {str(e)}")

            # 読み込みに成功したフレームのみを返す
            valid_frames = [f for f in frames if f is not None]
            if len(valid_frames) > 0:
                print(f"読み込み成功: {len(valid_frames)}/{total_frames}フレーム")
                if self._complete_callback:
                    self._complete_callback(valid_frames, len(valid_frames))
                return True
            else:
                print("有効なフレームが読み込めませんでした")
                if self._error_callback:
                    self._error_callback("有効なフレームが読み込めませんでした")
                return False

        except Exception as e:
            print(f"tifffile処理エラー: {str(e)}")
            if self._error_callback:
                self._error_callback(f"tifffile処理エラー: {str(e)}")
            return False

    def _process_with_opencv(self, file_path):
        """OpenCVを使用してTIFFを処理"""
        try:
            print(f"OpenCVで読み込みを試みます: {file_path}")

            # OpenCVでビデオキャプチャを開く
            cap = cv2.VideoCapture(file_path)
            if not cap.isOpened():
                if self._error_callback:
                    self._error_callback("OpenCVでファイルを開けませんでした")
                return False

            # フレーム数を取得
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if total_frames <= 0:
                # フレーム数が不明の場合は推定
                print("フレーム数が不明です。全フレームを読み込みます...")
                frames = []
                frame_idx = 0

                while True:
                    if self._stop_event.is_set():
                        break

                    ret, frame = cap.read()
                    if not ret:
                        break

                    # BGRからRGBに変換
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frames.append(frame_rgb)
                    frame_idx += 1

                    # 進捗の概算（フレーム数が不明のため正確ではない）
                    if self._progress_callback and frame_idx % 10 == 0:
                        self._progress_callback(0.5)  # 仮の進捗
            else:
                # フレーム数が分かっている場合
                frames = []
                for i in range(total_frames):
                    if self._stop_event.is_set():
                        break

                    ret, frame = cap.read()
                    if not ret:
                        break

                    # BGRからRGBに変換
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frames.append(frame_rgb)

                    # 進捗通知
                    if self._progress_callback:
                        self._progress_callback((i + 1) / total_frames)

            # キャプチャをリリース
            cap.release()

            # 読み込み結果を確認
            if len(frames) > 0:
                print(f"OpenCVで読み込み成功: {len(frames)}フレーム")
                if self._complete_callback:
                    self._complete_callback(frames, len(frames))
                return True
            else:
                print("OpenCVでフレームを読み込めませんでした")
                if self._error_callback:
                    self._error_callback("OpenCVでフレームを読み込めませんでした")
                return False

        except Exception as e:
            print(f"OpenCV処理エラー: {str(e)}")
            if self._error_callback:
                self._error_callback(f"OpenCV処理エラー: {str(e)}")
            return False

    def _load_frame_safe(self, tif, frame_idx):
        """安全にフレームを読み込む（エラー処理付き）"""
        try:
            # エラーが出ても続行できるように例外をキャッチ
            page = tif.pages[frame_idx]
            img = page.asarray()
            return self._convert_to_rgb(img)
        except Exception as e:
            print(f"フレーム {frame_idx} 読み込みエラー: {str(e)}")
            return None

    def _convert_to_rgb(self, img):
        """画像をRGBフォーマットに変換"""
        try:
            # 16ビット以上の整数データ型の場合、8ビットに変換
            if img.dtype != np.uint8:
                min_val = np.min(img)
                max_val = np.max(img)
                if max_val > min_val:  # ゼロ除算を防ぐ
                    img = ((img - min_val) / (max_val - min_val) * 255).astype(np.uint8)
                else:
                    img = np.zeros(img.shape, dtype=np.uint8)

            # グレースケールをRGBに変換
            if img.ndim == 2:
                img_rgb = cv2.cvtColor(img, cv2.COLOR_GRAY2RGB)
                return img_rgb
            elif img.ndim == 3 and img.shape[2] == 3:
                return img  # すでにRGB
            elif img.ndim == 3 and img.shape[2] == 4:
                return cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)  # アルファチャンネルを除去
            else:
                print(f"未対応の画像形式: shape={img.shape}, dtype={img.dtype}")
                # どうしても変換できない場合は、グレースケールのダミー画像を返す
                dummy = np.zeros((img.shape[0], img.shape[1], 3), dtype=np.uint8)
                return dummy
        except Exception as e:
            print(f"RGB変換エラー: {str(e)}")
            # エラー時はダミー画像を返す
            try:
                if img.ndim == 2:
                    h, w = img.shape
                    return np.zeros((h, w, 3), dtype=np.uint8)
                elif img.ndim >= 3:
                    h, w = img.shape[:2]
                    return np.zeros((h, w, 3), dtype=np.uint8)
                else:
                    return np.zeros((100, 100, 3), dtype=np.uint8)
            except:
                return np.zeros((100, 100, 3), dtype=np.uint8)
