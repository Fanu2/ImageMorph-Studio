import sys
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from PySide6.QtCore import (
    Qt,
    QThread,
    Signal,
    QUrl,
)
from PySide6.QtGui import (
    QAction,
    QDesktopServices,
    QPixmap,
    QMovie,
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QLineEdit,
    QTextEdit,
    QFileDialog,
    QMessageBox,
    QComboBox,
    QSpinBox,
    QProgressBar,
    QSlider,
    QSplitter,
    QGroupBox,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QSizePolicy,
    QStyle,
)

from PIL import Image


SUPPORTED_IMAGE_TYPES = {
    ".png",
    ".jpg",
    ".jpeg",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
}


# ============================================================
# Utilities
# ============================================================

def tool_exists(tool_name):
    return shutil.which(tool_name) is not None


def valid_image(path):
    try:
        with Image.open(path) as image:
            image.verify()
        return True
    except Exception:
        return False


def even(value):
    """Return an even number suitable for H.264 video encoding."""
    return value if value % 2 == 0 else max(2, value - 1)


# ============================================================
# Morph Worker
# ============================================================

class MorphWorker(QThread):

    log_message = Signal(str)
    progress_changed = Signal(int)
    status_changed = Signal(str)
    completed = Signal(str)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        image1,
        image2,
        output_path,
        frame_count,
        fps,
        output_format,
    ):
        super().__init__()

        self.image1 = image1
        self.image2 = image2
        self.output_path = output_path
        self.frame_count = frame_count
        self.fps = fps
        self.output_format = output_format

        self._cancel_requested = False
        self.process = None

    def cancel(self):
        self._cancel_requested = True

        if self.process and self.process.poll() is None:
            try:
                self.process.terminate()
            except Exception:
                pass

    def run_command(self, command):

        self.log_message.emit(
            "\n$ " + " ".join(str(item) for item in command)
        )

        self.process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        while True:

            if self._cancel_requested:

                if self.process.poll() is None:
                    self.process.terminate()

                raise InterruptedError("Operation cancelled.")

            line = self.process.stdout.readline()

            if line:
                self.log_message.emit(line.rstrip())

            if line == "" and self.process.poll() is not None:
                break

        return_code = self.process.returncode

        if return_code != 0:

            raise RuntimeError(
                f"Process failed with exit code {return_code}."
            )

    def run(self):

        temp_dir = None

        try:

            self.status_changed.emit("Checking tools...")

            if not tool_exists("gmic"):
                raise RuntimeError(
                    "G'MIC was not found.\n\n"
                    "Install G'MIC and make sure the 'gmic' command "
                    "is available in your system PATH."
                )

            if not tool_exists("ffmpeg"):
                raise RuntimeError(
                    "FFmpeg was not found.\n\n"
                    "Install FFmpeg and make sure the 'ffmpeg' command "
                    "is available in your system PATH."
                )

            self.progress_changed.emit(5)

            if self._cancel_requested:
                raise InterruptedError()

            self.status_changed.emit("Preparing workspace...")

            temp_dir = Path(
                tempfile.mkdtemp(
                    prefix="image_morph_"
                )
            )

            frames_dir = temp_dir / "frames"
            frames_dir.mkdir()
            frame_pattern = str(
                frames_dir / "frame.png"
            )

            # ------------------------------------------------
            # G'MIC morph
            # ------------------------------------------------

            self.status_changed.emit(
                "Generating morph frames..."
            )

            gmic_command = [
                "gmic",
                self.image1,
                self.image2,
                "-morph",
                str(self.frame_count),
                "-o",
                frame_pattern,
            ]

            self.run_command(gmic_command)

            self.progress_changed.emit(55)

            if self._cancel_requested:
                raise InterruptedError()

            generated_frames = sorted(
                frames_dir.glob("*.png")
            )

            if not generated_frames:
                raise RuntimeError(
                    "G'MIC completed but no frames were generated."
                )

            self.log_message.emit(
                f"\nGenerated {len(generated_frames)} frame(s)."
            )

            # ------------------------------------------------
            # FFmpeg output
            # ------------------------------------------------

            self.status_changed.emit(
                f"Creating {self.output_format.upper()}..."
            )

            output = Path(self.output_path)
            output.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            # ------------------------------------------------
            # Build an FFmpeg concat list from the actual
            # PNG frames generated by G'MIC.
            # ------------------------------------------------

            concat_file = temp_dir / "frames.txt"

            with open(
                concat_file,
                "w",
                encoding="utf-8",
            ) as file:

                for frame in generated_frames:

                    frame_path = str(
                        frame.resolve()
                    )

                    file.write(
                        f"file '{frame_path}'\n"
                    )

            frame_input = str(
                concat_file
            )

            if self.output_format == "mp4":

                ffmpeg_command = [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    frame_input,
                    "-r",
                    str(self.fps),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-crf",
                    "18",
                    "-preset",
                    "medium",
                    str(output),
                ]

                self.run_command(ffmpeg_command)

            else:

                palette = temp_dir / "palette.png"

                self.status_changed.emit(
                    "Generating GIF palette..."
                )

                palette_command = [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    frame_input,
                    "-vf",
                    f"fps={self.fps},palettegen",
                    str(palette),
                ]

                self.run_command(palette_command)

                self.progress_changed.emit(75)

                self.status_changed.emit(
                    "Creating GIF..."
                )

                gif_command = [
                    "ffmpeg",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    frame_input,
                    "-i",
                    str(palette),
                    "-lavfi",
                    f"fps={self.fps},paletteuse",
                    str(output),
                ]

                self.run_command(gif_command)

            if not output.exists():

                raise RuntimeError(
                    "Processing completed but the output file "
                    "was not created."
                )

            self.progress_changed.emit(100)

            self.status_changed.emit(
                "Completed successfully."
            )

            self.completed.emit(
                str(output)
            )

        except InterruptedError:

            self.status_changed.emit(
                "Cancelled."
            )

            self.cancelled.emit()

        except Exception as error:

            self.failed.emit(
                str(error)
            )

        finally:

            if self.process:

                try:
                    if self.process.poll() is None:
                        self.process.terminate()
                except Exception:
                    pass

            if temp_dir:

                try:
                    shutil.rmtree(
                        temp_dir,
                        ignore_errors=True,
                    )
                except Exception:
                    pass


# ============================================================
# Frame Preview Dialog
# ============================================================

class FramePreviewDialog(QDialog):

    def __init__(self, frames, parent=None):

        super().__init__(parent)

        self.frames = frames
        self.index = 0

        self.setWindowTitle("Frame Preview")
        self.resize(850, 700)

        self.image_label = QLabel()

        self.image_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.image_label.setMinimumSize(
            600,
            450,
        )

        self.counter_label = QLabel()

        self.counter_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.previous_button = QPushButton(
            "◀ Previous"
        )

        self.next_button = QPushButton(
            "Next ▶"
        )

        self.previous_button.clicked.connect(
            self.previous_frame
        )

        self.next_button.clicked.connect(
            self.next_frame
        )

        buttons = QHBoxLayout()

        buttons.addWidget(
            self.previous_button
        )

        buttons.addWidget(
            self.counter_label
        )

        buttons.addWidget(
            self.next_button
        )

        layout = QVBoxLayout(self)

        layout.addWidget(
            self.image_label,
            1,
        )

        layout.addLayout(
            buttons
        )

        self.show_frame()

    def resizeEvent(self, event):

        super().resizeEvent(event)

        self.show_frame()

    def show_frame(self):

        if not self.frames:
            return

        frame = self.frames[
            self.index
        ]

        pixmap = QPixmap(
            str(frame)
        )

        available_size = (
            self.image_label.size()
        )

        if not pixmap.isNull():

            scaled = pixmap.scaled(
                available_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

            self.image_label.setPixmap(
                scaled
            )

        self.counter_label.setText(
            f"Frame {self.index + 1} "
            f"of {len(self.frames)}"
        )

        self.previous_button.setEnabled(
            self.index > 0
        )

        self.next_button.setEnabled(
            self.index < len(self.frames) - 1
        )

    def previous_frame(self):

        if self.index > 0:

            self.index -= 1

            self.show_frame()

    def next_frame(self):

        if self.index < len(self.frames) - 1:

            self.index += 1

            self.show_frame()


# ============================================================
# Image Preview Widget
# ============================================================

class ImagePreviewCard(QFrame):

    def __init__(
        self,
        title,
        parent=None,
    ):
        super().__init__(parent)

        self.path = ""

        self.setFrameShape(
            QFrame.Shape.StyledPanel
        )

        self.setMinimumHeight(
            240
        )

        self.title_label = QLabel(
            title
        )

        self.title_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.image_label = QLabel(
            "No image selected"
        )

        self.image_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.image_label.setMinimumSize(
            280,
            180,
        )

        self.info_label = QLabel()

        self.info_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.info_label.setWordWrap(
            True
        )

        layout = QVBoxLayout(self)

        layout.addWidget(
            self.title_label
        )

        layout.addWidget(
            self.image_label,
            1,
        )

        layout.addWidget(
            self.info_label
        )

    def set_image(self, path):

        self.path = path

        pixmap = QPixmap(
            path
        )

        if pixmap.isNull():

            self.image_label.setText(
                "Unable to preview image"
            )

            return

        scaled = pixmap.scaled(
            self.image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

        self.image_label.setPixmap(
            scaled
        )

        try:

            with Image.open(path) as image:

                width, height = image.size

            self.info_label.setText(
                f"{Path(path).name}\n"
                f"{width} × {height}"
            )

        except Exception:

            self.info_label.setText(
                Path(path).name
            )

    def resizeEvent(self, event):

        super().resizeEvent(event)

        if self.path:
            self.set_image(
                self.path
            )


# ============================================================
# Main Application
# ============================================================

class ImageMorphStudio(QMainWindow):

    def __init__(self):

        super().__init__()

        self.image1_path = ""
        self.image2_path = ""

        self.output_path = ""

        self.worker = None

        self.last_frames = []

        self.setup_window()
        self.create_ui()
        self.create_menu()
        self.check_tools()

    # --------------------------------------------------------
    # Window
    # --------------------------------------------------------

    def setup_window(self):

        self.setWindowTitle(
            "ImageMorph Studio"
        )

        self.resize(
            1200,
            850,
        )

        self.setMinimumSize(
            900,
            650,
        )

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------

    def create_ui(self):

        central = QWidget()

        self.setCentralWidget(
            central
        )

        root_layout = QVBoxLayout(
            central
        )

        splitter = QSplitter(
            Qt.Orientation.Horizontal
        )

        root_layout.addWidget(
            splitter
        )

        # ================================================
        # Left panel
        # ================================================

        left_panel = QWidget()

        left_layout = QVBoxLayout(
            left_panel
        )

        source_group = QGroupBox(
            "Source Images"
        )

        source_layout = QVBoxLayout(
            source_group
        )

        self.image1_card = ImagePreviewCard(
            "Image 1"
        )

        self.image2_card = ImagePreviewCard(
            "Image 2"
        )

        self.select_image1_button = QPushButton(
            "Select Image 1"
        )

        self.select_image2_button = QPushButton(
            "Select Image 2"
        )

        self.select_image1_button.clicked.connect(
            lambda: self.select_image(1)
        )

        self.select_image2_button.clicked.connect(
            lambda: self.select_image(2)
        )

        source_layout.addWidget(
            self.image1_card
        )

        source_layout.addWidget(
            self.select_image1_button
        )

        source_layout.addWidget(
            self.image2_card
        )

        source_layout.addWidget(
            self.select_image2_button
        )

        left_layout.addWidget(
            source_group
        )

        # ================================================
        # Settings
        # ================================================

        settings_group = QGroupBox(
            "Morph Settings"
        )

        settings_layout = QGridLayout(
            settings_group
        )

        settings_layout.addWidget(
            QLabel(
                "Intermediate Frames:"
            ),
            0,
            0,
        )

        self.frames_spinbox = QSpinBox()

        self.frames_spinbox.setRange(
            2,
            500,
        )

        self.frames_spinbox.setValue(
            30
        )

        settings_layout.addWidget(
            self.frames_spinbox,
            0,
            1,
        )

        settings_layout.addWidget(
            QLabel(
                "Frames Per Second:"
            ),
            1,
            0,
        )

        self.fps_spinbox = QSpinBox()

        self.fps_spinbox.setRange(
            1,
            120,
        )

        self.fps_spinbox.setValue(
            30
        )

        settings_layout.addWidget(
            self.fps_spinbox,
            1,
            1,
        )

        settings_layout.addWidget(
            QLabel(
                "Output Format:"
            ),
            2,
            0,
        )

        self.format_combo = QComboBox()

        self.format_combo.addItems(
            [
                "mp4",
                "gif",
            ]
        )

        self.format_combo.currentTextChanged.connect(
            self.update_output_extension
        )

        settings_layout.addWidget(
            self.format_combo,
            2,
            1,
        )

        left_layout.addWidget(
            settings_group
        )

        # ================================================
        # Output
        # ================================================

        output_group = QGroupBox(
            "Output"
        )

        output_layout = QHBoxLayout(
            output_group
        )

        self.output_edit = QLineEdit()

        self.output_edit.setPlaceholderText(
            "Choose output file..."
        )

        self.output_button = QPushButton(
            "Browse"
        )

        self.output_button.clicked.connect(
            self.select_output
        )

        output_layout.addWidget(
            self.output_edit,
            1,
        )

        output_layout.addWidget(
            self.output_button
        )

        left_layout.addWidget(
            output_group
        )

        # ================================================
        # Action buttons
        # ================================================

        actions_group = QGroupBox(
            "Actions"
        )

        actions_layout = QGridLayout(
            actions_group
        )

        self.start_button = QPushButton(
            "▶ Start Morph"
        )

        self.cancel_button = QPushButton(
            "■ Cancel"
        )

        self.preview_button = QPushButton(
            "Preview Generated Frames"
        )

        self.open_output_button = QPushButton(
            "Open Output"
        )

        self.open_folder_button = QPushButton(
            "Open Output Folder"
        )

        self.cancel_button.setEnabled(
            False
        )

        self.open_output_button.setEnabled(
            False
        )

        self.open_folder_button.setEnabled(
            False
        )

        self.start_button.clicked.connect(
            self.start_morph
        )

        self.cancel_button.clicked.connect(
            self.cancel_morph
        )

        self.preview_button.clicked.connect(
            self.preview_frames
        )

        self.open_output_button.clicked.connect(
            self.open_output
        )

        self.open_folder_button.clicked.connect(
            self.open_output_folder
        )

        actions_layout.addWidget(
            self.start_button,
            0,
            0,
        )

        actions_layout.addWidget(
            self.cancel_button,
            0,
            1,
        )

        actions_layout.addWidget(
            self.preview_button,
            1,
            0,
            1,
            2,
        )

        actions_layout.addWidget(
            self.open_output_button,
            2,
            0,
        )

        actions_layout.addWidget(
            self.open_folder_button,
            2,
            1,
        )

        left_layout.addWidget(
            actions_group
        )

        left_layout.addStretch()

        splitter.addWidget(
            left_panel
        )

        # ================================================
        # Right panel
        # ================================================

        right_panel = QWidget()

        right_layout = QVBoxLayout(
            right_panel
        )

        status_group = QGroupBox(
            "Status"
        )

        status_layout = QVBoxLayout(
            status_group
        )

        self.status_label = QLabel(
            "Ready."
        )

        self.progress_bar = QProgressBar()

        self.progress_bar.setRange(
            0,
            100
        )

        self.progress_bar.setValue(
            0
        )

        status_layout.addWidget(
            self.status_label
        )

        status_layout.addWidget(
            self.progress_bar
        )

        right_layout.addWidget(
            status_group
        )

        log_group = QGroupBox(
            "Processing Log"
        )

        log_layout = QVBoxLayout(
            log_group
        )

        self.log_output = QTextEdit()

        self.log_output.setReadOnly(
            True
        )

        self.log_output.setLineWrapMode(
            QTextEdit.LineWrapMode.NoWrap
        )

        log_layout.addWidget(
            self.log_output
        )

        right_layout.addWidget(
            log_group,
            1,
        )

        splitter.addWidget(
            right_panel
        )

        splitter.setSizes(
            [
                520,
                680,
            ]
        )

        self.statusBar().showMessage(
            "Ready"
        )

    # --------------------------------------------------------
    # Menu
    # --------------------------------------------------------

    def create_menu(self):

        file_menu = self.menuBar().addMenu(
            "&File"
        )

        select_first = QAction(
            "Select Image 1",
            self,
        )

        select_first.triggered.connect(
            lambda: self.select_image(1)
        )

        select_second = QAction(
            "Select Image 2",
            self,
        )

        select_second.triggered.connect(
            lambda: self.select_image(2)
        )

        exit_action = QAction(
            "Exit",
            self,
        )

        exit_action.triggered.connect(
            self.close
        )

        file_menu.addAction(
            select_first
        )

        file_menu.addAction(
            select_second
        )

        file_menu.addSeparator()

        file_menu.addAction(
            exit_action
        )

        tools_menu = self.menuBar().addMenu(
            "&Tools"
        )

        check_tools_action = QAction(
            "Check G'MIC and FFmpeg",
            self,
        )

        check_tools_action.triggered.connect(
            self.check_tools
        )

        tools_menu.addAction(
            check_tools_action
        )

        help_menu = self.menuBar().addMenu(
            "&Help"
        )

        about_action = QAction(
            "About ImageMorph Studio",
            self,
        )

        about_action.triggered.connect(
            self.show_about
        )

        help_menu.addAction(
            about_action
        )

    # --------------------------------------------------------
    # Logging
    # --------------------------------------------------------

    def log(self, message):

        self.log_output.append(
            message
        )

        self.log_output.ensureCursorVisible()

    # --------------------------------------------------------
    # Tool detection
    # --------------------------------------------------------

    def check_tools(self):

        gmic_ok = tool_exists(
            "gmic"
        )

        ffmpeg_ok = tool_exists(
            "ffmpeg"
        )

        message = (
            f"G'MIC: "
            f"{'✓ Found' if gmic_ok else '✗ Not Found'}\n"
            f"FFmpeg: "
            f"{'✓ Found' if ffmpeg_ok else '✗ Not Found'}"
        )

        self.statusBar().showMessage(
            message.replace(
                "\n",
                " | "
            )
        )

        self.log(
            "Tool check:"
        )

        self.log(
            message
        )

    # --------------------------------------------------------
    # Image selection
    # --------------------------------------------------------

    def select_image(
        self,
        number,
    ):

        filename, _ = (
            QFileDialog.getOpenFileName(
                self,
                f"Select Image {number}",
                "",
                (
                    "Images (*.png *.jpg *.jpeg "
                    "*.bmp *.webp *.tif *.tiff)"
                ),
            )
        )

        if not filename:
            return

        suffix = Path(
            filename
        ).suffix.lower()

        if suffix not in SUPPORTED_IMAGE_TYPES:

            QMessageBox.warning(
                self,
                "Unsupported Image",
                "This image format is not supported.",
            )

            return

        if not valid_image(
            filename
        ):

            QMessageBox.warning(
                self,
                "Invalid Image",
                "The selected image could not be opened.",
            )

            return

        if number == 1:

            self.image1_path = filename

            self.image1_card.set_image(
                filename
            )

        else:

            self.image2_path = filename

            self.image2_card.set_image(
                filename
            )

        self.log(
            f"Selected Image {number}: "
            f"{filename}"
        )

    # --------------------------------------------------------
    # Output selection
    # --------------------------------------------------------

    def select_output(self):

        output_format = (
            self.format_combo.currentText()
        )

        filter_text = (
            f"{output_format.upper()} "
            f"Files (*.{output_format})"
        )

        filename, _ = (
            QFileDialog.getSaveFileName(
                self,
                "Save Output",
                f"image_morph.{output_format}",
                filter_text,
            )
        )

        if not filename:
            return

        filename = self.ensure_extension(
            filename,
            output_format,
        )

        self.output_path = filename

        self.output_edit.setText(
            filename
        )

     # --------------------------------------------------------
    # Output extension helpers
    # --------------------------------------------------------

    def ensure_extension(
        self,
        path,
        extension,
    ):

        output = Path(path)

        return str(
            output.with_suffix(
                f".{extension}"
            )
        )

    def update_output_extension(
        self,
        output_format,
    ):

        current = self.output_edit.text().strip()

        if not current:
            return

        updated = self.ensure_extension(
            current,
            output_format,
        )

        self.output_edit.setText(
            updated
        )

    # --------------------------------------------------------
    # Start processing
    # --------------------------------------------------------

    def start_morph(self):

        # Prevent multiple workers from running simultaneously.
        if (
            self.worker is not None
            and self.worker.isRunning()
        ):

            QMessageBox.warning(
                self,
                "Processing Active",
                "A morph operation is already running.",
            )

            return

        # Validate source images.
        if not self.image1_path:

            QMessageBox.warning(
                self,
                "Image Missing",
                "Please select Image 1.",
            )

            return

        if not self.image2_path:

            QMessageBox.warning(
                self,
                "Image Missing",
                "Please select Image 2.",
            )

            return

        # Validate required external tools.
        if not tool_exists("gmic"):

            QMessageBox.critical(
                self,
                "G'MIC Not Found",
                "G'MIC is required to create the morph.",
            )

            return

        if not tool_exists("ffmpeg"):

            QMessageBox.critical(
                self,
                "FFmpeg Not Found",
                "FFmpeg is required to create the output.",
            )

            return

        # ----------------------------------------------------
        # Prepare output
        # ----------------------------------------------------

        output = (
            self.output_edit.text().strip()
        )

        output_format = (
            self.format_combo.currentText()
        )

        if not output:

            default_output = (
                Path(self.image1_path).parent
                / f"image_morph.{output_format}"
            )

            output = str(
                default_output
            )

        output = self.ensure_extension(
            output,
            output_format,
        )

        self.output_edit.setText(
            output
        )

        self.output_path = output

        # ----------------------------------------------------
        # Reset processing information
        # ----------------------------------------------------

        self.log_output.clear()

        self.progress_bar.setValue(
            0
        )

        self.status_label.setText(
            "Starting morph process..."
        )

        self.log(
            "Starting ImageMorph Studio..."
        )

        self.log(
            f"Image 1: {self.image1_path}"
        )

        self.log(
            f"Image 2: {self.image2_path}"
        )

        self.log(
            "Intermediate Frames: "
            f"{self.frames_spinbox.value()}"
        )

        self.log(
            f"FPS: {self.fps_spinbox.value()}"
        )

        self.log(
            f"Output Format: "
            f"{output_format.upper()}"
        )

        self.log(
            f"Output: {output}"
        )

        # ----------------------------------------------------
        # Lock processing controls
        # ----------------------------------------------------

        self.start_button.setEnabled(
            False
        )

        self.cancel_button.setEnabled(
            True
        )

        self.select_image1_button.setEnabled(
            False
        )

        self.select_image2_button.setEnabled(
            False
        )

        self.output_button.setEnabled(
            False
        )

        self.preview_button.setEnabled(
            False
        )

        self.open_output_button.setEnabled(
            False
        )

        self.open_folder_button.setEnabled(
            False
        )

        # ----------------------------------------------------
        # Create worker
        # ----------------------------------------------------

        self.worker = MorphWorker(
            self.image1_path,
            self.image2_path,
            output,
            self.frames_spinbox.value(),
            self.fps_spinbox.value(),
            output_format,
        )

        # ----------------------------------------------------
        # Connect worker signals
        # ----------------------------------------------------

        self.worker.log_message.connect(
            self.log
        )

        self.worker.progress_changed.connect(
            self.progress_bar.setValue
        )

        self.worker.status_changed.connect(
            self.status_label.setText
        )

        self.worker.completed.connect(
            self.morph_completed
        )

        self.worker.failed.connect(
            self.morph_failed
        )

        self.worker.cancelled.connect(
            self.morph_cancelled
        )

        # The worker object is cleaned up only after
        # the QThread has completely stopped.
        self.worker.finished.connect(
            self.worker_finished
        )

        # ----------------------------------------------------
        # Start worker
        # ----------------------------------------------------

        self.worker.start()

    # --------------------------------------------------------
    # Cancel processing
    # --------------------------------------------------------

    def cancel_morph(self):

        if (
            self.worker is not None
            and self.worker.isRunning()
        ):

            self.status_label.setText(
                "Cancelling..."
            )

            self.worker.cancel()

            self.log(
                "Cancellation requested..."
            )

    # --------------------------------------------------------
    # Worker cleanup
    # --------------------------------------------------------

    def worker_finished(self):
        """
        Clean up the worker only after the QThread
        has completely stopped.
        """

        worker = self.sender()

        if worker is not None:

            worker.deleteLater()

            if worker is self.worker:

                self.worker = None

    # --------------------------------------------------------
    # Worker completed
    # --------------------------------------------------------

    def morph_completed(
        self,
        output_path,
    ):

        self.output_path = (
            output_path
        )

        self.progress_bar.setValue(
            100
        )

        self.status_label.setText(
            "Completed successfully."
        )

        self.log(
            "\n✓ Morph completed successfully."
        )

        self.log(
            f"Output: {output_path}"
        )

        self.finish_processing()

        QMessageBox.information(
            self,
            "Completed",
            (
                "Image morph completed successfully.\n\n"
                f"Output:\n{output_path}"
            ),
        )

    # --------------------------------------------------------
    # Worker failed
    # --------------------------------------------------------

    def morph_failed(
        self,
        error,
    ):

        self.status_label.setText(
            "Failed."
        )

        self.log(
            f"\n✗ ERROR:\n{error}"
        )

        self.finish_processing()

        QMessageBox.critical(
            self,
            "Processing Failed",
            error,
        )

    # --------------------------------------------------------
    # Worker cancelled
    # --------------------------------------------------------

    def morph_cancelled(self):

        self.status_label.setText(
            "Cancelled."
        )

        self.log(
            "\nOperation cancelled."
        )

        self.finish_processing()

    # --------------------------------------------------------
    # Restore UI after processing
    # --------------------------------------------------------

    def finish_processing(self):

        # Re-enable normal controls.
        self.start_button.setEnabled(
            True
        )

        self.cancel_button.setEnabled(
            False
        )

        self.select_image1_button.setEnabled(
            True
        )

        self.select_image2_button.setEnabled(
            True
        )

        self.output_button.setEnabled(
            True
        )

        self.preview_button.setEnabled(
            True
        )

        # Enable output actions only when the output
        # file actually exists.
        output_exists = (
            bool(self.output_path)
            and Path(
                self.output_path
            ).exists()
        )

        self.open_output_button.setEnabled(
            output_exists
        )

        self.open_folder_button.setEnabled(
            output_exists
        )

        # IMPORTANT:
        # Do not set self.worker = None here.
        # The QThread may still be finishing.
        # worker_finished() owns final cleanup.

    # --------------------------------------------------------
    # Preview frames
    # --------------------------------------------------------

    def preview_frames(self):

        QMessageBox.information(
            self,
            "Frame Preview",
            (
                "Generated morph frames are temporary and "
                "are automatically cleaned up after output "
                "creation.\n\n"
                "The current version does not keep generated "
                "frames after processing."
            ),
        )

    # --------------------------------------------------------
    # Open output
    # --------------------------------------------------------

    def open_output(self):

        if not self.output_path:
            return

        path = Path(
            self.output_path
        )

        if path.exists():

            QDesktopServices.openUrl(
                QUrl.fromLocalFile(
                    str(path)
                )
            )

    def open_output_folder(self):

        if not self.output_path:
            return

        path = Path(
            self.output_path
        )

        folder = path.parent

        if folder.exists():

            QDesktopServices.openUrl(
                QUrl.fromLocalFile(
                    str(folder)
                )
            )

    # --------------------------------------------------------
    # About
    # --------------------------------------------------------

    def show_about(self):

        QMessageBox.about(
            self,
            "About ImageMorph Studio",
            """
            <h2>ImageMorph Studio</h2>

            <p>A PySide6 desktop application for creating
            image morph animations.</p>

            <p><b>Workflow:</b></p>

            <p>
            Image 1 + Image 2
            → G'MIC Morph
            → Generated Frames
            → FFmpeg
            → MP4 or GIF
            </p>

            <p>
            Built with Python, PySide6, G'MIC and FFmpeg.
            </p>
            """,
        )

    # --------------------------------------------------------
    # Safe close
    # --------------------------------------------------------

    def closeEvent(
        self,
        event,
    ):

        # Allow normal closing when no processing is active.
        if (
            self.worker is None
            or not self.worker.isRunning()
        ):

            event.accept()
            return

        reply = QMessageBox.question(
            self,
            "Processing Active",
            (
                "Image processing is still running.\n\n"
                "Do you want to cancel the operation and exit?"
            ),
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply != QMessageBox.StandardButton.Yes:

            event.ignore()
            return

        self.status_label.setText(
            "Stopping processing..."
        )

        self.log(
            "Application closing: cancellation requested..."
        )

        # Request cancellation.
        self.worker.cancel()

        # Wait until the worker has completely stopped before
        # allowing the application to be destroyed.
        self.worker.wait()

        event.accept()


# ============================================================
# Application Entry Point
# ============================================================

def main():

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        "ImageMorph Studio"
    )

    window = ImageMorphStudio()

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()