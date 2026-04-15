#!/usr/bin/env python3
"""
Calimoto APK Patcher Tool v3.0 - PySide6 Edition
- Modern Qt-based GUI with Material Design 3
- .env-based Setup
- Automatic Keystore creation with random password
"""

import os
import re
import sys
import json
import logging
import subprocess
import shutil
import string
import secrets
import time
from pathlib import Path
from datetime import datetime
from threading import Thread, Event, Lock

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QCheckBox, QPlainTextEdit,
    QFileDialog, QMessageBox, QGroupBox, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, QThread, Signal, QSize, QTimer, QObject
from PySide6.QtGui import QColor, QFont, QGuiApplication

# UTF-8 for Windows
os.environ['PYTHONIOENCODING'] = 'utf-8'

logging.basicConfig(
    level=logging.DEBUG,
    format='[%(asctime)s] %(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# .env file always load/save relative to script directory
ENV_FILE = Path(__file__).resolve().parent / '.calimoto-patcher.env'
DEFAULT_KEYSTORE_FILE = Path(__file__).resolve().parent / 'calimoto.keystore'


class KeystoreGenerator:
    """Create keystores with automatic inputs"""

    @staticmethod
    def generate_password(length: int = 16) -> str:
        """Generate random password"""
        alphabet = string.ascii_letters + string.digits + "_-"
        password = ''.join(secrets.choice(alphabet) for i in range(length))
        return password

    @staticmethod
    def create_keystore(keystore_path: str, alias: str = "myalias") -> tuple[bool, str, str]:
        """Create keystore with automatic inputs"""
        password = KeystoreGenerator.generate_password()

        logger.info(f"Creating keystore: {keystore_path}")
        logger.info(f"Alias: {alias}")
        logger.info(f"Password generated: {'*' * len(password)}")

        try:
            cmd = [
                'keytool',
                '-genkeypair',
                '-v',
                '-keystore', keystore_path,
                '-alias', alias,
                '-keyalg', 'RSA',
                '-keysize', '2048',
                '-validity', '10000',
                '-storepass', password,
                '-keypass', password,
                '-dname', 'CN=APK-Signer,OU=Mobile,O=CalimotoPatcher,L=Local,ST=Local,C=DE'
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.stdout:
                for line in result.stdout.splitlines():
                    logger.info(line)
            if result.stderr:
                for line in result.stderr.splitlines():
                    logger.info(line)

            if result.returncode == 0:
                logger.info("Keystore created successfully")
                return True, password, None
            else:
                error = result.stderr or result.stdout
                logger.error(f"keytool error: {error}")
                return False, None, error

        except Exception as e:
            logger.error(f"Error: {str(e)}")
            return False, None, str(e)


class EnvConfig:
    """Manages .env configuration"""

    @staticmethod
    def load() -> dict[str, str]:
        """Load .env file"""
        if not ENV_FILE.exists():
            return {}

        try:
            with open(ENV_FILE, 'r') as f:
                data = json.load(f)
            logger.info(f"Config loaded: {ENV_FILE}")
            return data
        except Exception as e:
            logger.error(f"Error loading .env: {e}")
            return {}

    @staticmethod
    def save(data: dict[str, str]):
        """Save .env file"""
        try:
            with open(ENV_FILE, 'w') as f:
                json.dump(data, f, indent=2)
            logger.info(f"Config saved: {ENV_FILE}")
        except Exception as e:
            logger.error(f"Error saving .env: {e}")

    @staticmethod
    def exists() -> bool:
        """Check if .env exists"""
        return ENV_FILE.exists()

    @staticmethod
    def get(key: str, default: str = None) -> str:
        """Get single value"""
        config = EnvConfig.load()
        return config.get(key, default)


class ToolFinder:
    """Finds apktool and apksigner everywhere"""

    @staticmethod
    def find_in_path(tool_name: str) -> str | None:
        """Search tool in system PATH"""
        try:
            if sys.platform == 'win32':
                result = subprocess.run(['where', tool_name],
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return result.stdout.strip().split('\n')[0]
            else:
                result = subprocess.run(['which', tool_name],
                                      capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    return result.stdout.strip()
        except:
            pass
        return None

    @staticmethod
    def find_apktool() -> str | None:
        """Find apktool - prefer JAR to avoid pause issues"""
        for name in ['apktool.jar', 'apktool', 'apktool.bat']:
            path = ToolFinder.find_in_path(name)
            if path:
                if name != 'apktool.jar':
                    sibling_jar = Path(path).with_name('apktool.jar')
                    if sibling_jar.exists():
                        return str(sibling_jar)
                return path

        common_paths = [
            Path.home() / 'AppData/Local/apktool',
            Path('C:/apktool'),
            Path('/opt/apktool'),
            Path('/usr/local/bin/apktool'),
        ]

        for p in common_paths:
            if p.exists():
                jar_path = p / 'apktool.jar'
                if jar_path.exists():
                    return str(jar_path)
                return str(p)

        return None

    @staticmethod
    def find_apksigner() -> str | None:
        """Find apksigner"""
        for name in ['apksigner', 'apksigner.bat']:
            path = ToolFinder.find_in_path(name)
            if path:
                return path

        android_home = os.environ.get('ANDROID_HOME')
        if android_home:
            apksigner_path = Path(android_home) / 'build-tools'
            if apksigner_path.exists():
                for version_dir in sorted(apksigner_path.iterdir(), reverse=True):
                    exe = version_dir / ('apksigner.bat' if sys.platform == 'win32' else 'apksigner')
                    if exe.exists():
                        return str(exe)

        common_paths = [
            Path.home() / 'Android/Sdk/build-tools',
            Path('C:/Android/Sdk/build-tools'),
        ]

        for base_path in common_paths:
            if base_path.exists():
                for version_dir in sorted(base_path.iterdir(), reverse=True):
                    exe = version_dir / ('apksigner.bat' if sys.platform == 'win32' else 'apksigner')
                    if exe.exists():
                        return str(exe)

        return None


class PatchManager:
    """Manages patches"""
    PATCH_DEFINITIONS = {
        'patch_0_unlock_navigation_and_offline_maps': {
            'name': 'Unlock Navigation',
            'file': 'smali_classes3/com/calimoto/calimoto/parse/user/a.smali',
            'type': 'smali_method',
            'search': r'\.method public static O\(\)Z\s+\.locals 4.*?invoke-static \{\}, Lcom/calimoto/calimoto/parse/user/a;->P\(\)Z.*?return v2\n\.end method',
            'replace': r'''.method public static O()Z
    .locals 1

    const/4 v0, 0x1

    return v0
.end method'''
        },
        'patch_1_xml_config': {
            'name': 'Dissable Popup Ad',
            'file': 'res/xml/remote_config_defaults.xml',
            'type': 'xml_value',
            'search': r'<key>skipPaywallInfoPercentAndroid</key>\s*<value>0\.5</value>',
            'replace': '<key>skipPaywallInfoPercentAndroid</key>\n<value>1.0</value>'
        },
    }

    def __init__(self, working_dir: Path):
        self.working_dir = working_dir

    def _resolve_candidate_files(self, operation: dict[str, str]) -> list[Path]:
        """Resolve primary, fallback and glob candidate files for one operation."""
        candidates: list[Path] = []

        primary_file = operation.get('file')
        if primary_file:
            candidates.append(self.working_dir / primary_file)

        for rel_path in operation.get('file_candidates', []):
            candidates.append(self.working_dir / rel_path)

        file_glob = operation.get('file_glob')
        if file_glob:
            candidates.extend(sorted(self.working_dir.glob(file_glob)))

        # Keep insertion order while deduplicating
        unique_candidates: list[Path] = []
        seen: set[str] = set()
        for candidate in candidates:
            candidate_key = str(candidate)
            if candidate_key in seen:
                continue
            seen.add(candidate_key)
            unique_candidates.append(candidate)

        return unique_candidates

    def _apply_single_operation(self, operation: dict[str, str], patch_name: str) -> tuple[bool, bool, str]:
        """Apply one regex replacement operation and report if it changed content. Returns (success, applied, error_msg)."""
        ANSI_RED = "\033[91m"
        ANSI_WHITE = "\033[0m"

        file_candidates = self._resolve_candidate_files(operation)
        if not file_candidates:
            msg = f"{ANSI_RED}SKIP: No file candidates defined{ANSI_WHITE}"
            logger.warning(msg)
            return True, False, msg

        try:
            pattern = operation['search']
            flags = re.DOTALL if 'method' in operation.get('type', '') else 0
            checked_files = 0

            for file_path in file_candidates:
                if not file_path.exists() or not file_path.is_file():
                    continue

                checked_files += 1
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                if not re.search(pattern, content, flags=flags):
                    continue

                updated_content, replacements = re.subn(pattern, operation['replace'], content, flags=flags)
                if replacements == 0:
                    continue

                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(updated_content)

                rel_path = file_path.relative_to(self.working_dir)
                logger.info(f"OK: {patch_name} ({rel_path})")
                return True, True, ""

            display_file = operation.get('file') or 'n/a'
            if checked_files == 0:
                msg = f"{ANSI_RED}SKIP: File not found: {display_file}{ANSI_WHITE}"
            else:
                msg = f"{ANSI_RED}SKIP: Pattern not found (files checked: {checked_files}){ANSI_WHITE}"
            logger.warning(msg)
            return True, False, msg

        except Exception as e:
            error_msg = f"ERROR in {operation.get('file', 'n/a')}: {str(e)}"
            logger.error(error_msg)
            return False, False, error_msg

    def apply_patch(self, patch_name: str) -> tuple[bool, str]:
        if patch_name not in self.PATCH_DEFINITIONS:
            return False, f"Patch not defined"

        patch = self.PATCH_DEFINITIONS[patch_name]
        logger.info(f"Patch: {patch['name']}")
        operations = patch.get('operations', [patch])
        applied_any = False
        skip_messages = []

        for operation in operations:
            success, applied, error_msg = self._apply_single_operation(operation, patch['name'])
            if not success:
                return False, f"ERROR: {patch['name']} - {error_msg}"
            if not applied and error_msg:
                skip_messages.append(error_msg)
            applied_any = applied_any or applied

        if applied_any:
            logger.info(f"OK: {patch['name']}")
            return True, f"OK: {patch['name']}"

        if skip_messages:
            skip_msg = " | ".join(skip_messages)
            return True, f"SKIP: {patch['name']} - {skip_msg}"

        return True, f"SKIP: {patch['name']}"

    def apply_all(self, patches: list[str]) -> dict[str, tuple[bool, str]]:
        results = {}
        for patch_name in patches:
            success, msg = self.apply_patch(patch_name)
            results[patch_name] = (success, msg)
        return results


class APKWorker:
    """APK operations"""

    def __init__(self, apktool_path: str, apksigner_path: str, log_callback=None, stop_event: Event | None = None):
        self.apktool = apktool_path
        self.apksigner = apksigner_path
        self.log_callback = log_callback
        self.stop_event = stop_event or Event()
        self._current_process = None
        self._process_lock = Lock()

    def request_stop(self):
        """Request cancellation and terminate running process if needed."""
        self.stop_event.set()

        with self._process_lock:
            process = self._current_process

        if process and process.poll() is None:
            try:
                process.terminate()
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception:
                # Best effort cleanup for external tools.
                pass

    def _emit_process_line(self, line: str):
        """Stream one process output line to GUI in real time."""
        if self.log_callback:
            self.log_callback(line)
            return
        logger.info(line)

    def _run_command(self, cmd: list[str], timeout: int) -> subprocess.CompletedProcess:
        if self.stop_event.is_set():
            raise InterruptedError("Cancelled")

        logger.info(f"Command: {' '.join(cmd)}")
        process = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
        )

        with self._process_lock:
            self._current_process = process

        output_lines: list[str] = []

        def _stream_reader():
            if not process.stdout:
                return

            for raw_line in process.stdout:
                line = raw_line.rstrip('\r\n')
                output_lines.append(line)
                self._emit_process_line(line)

        reader_thread = Thread(target=_stream_reader, daemon=True)
        reader_thread.start()

        try:
            start_time = time.monotonic()
            while process.poll() is None:
                if self.stop_event.is_set():
                    self.request_stop()
                    reader_thread.join(timeout=1)
                    raise InterruptedError("Cancelled")

                if time.monotonic() - start_time > timeout:
                    process.kill()
                    reader_thread.join(timeout=1)
                    raise subprocess.TimeoutExpired(cmd, timeout)

                time.sleep(0.05)

            reader_thread.join(timeout=1)
            stdout_text = '\n'.join(output_lines)

            return subprocess.CompletedProcess(
                args=cmd,
                returncode=process.returncode,
                stdout=stdout_text,
                stderr="",
            )
        finally:
            with self._process_lock:
                if self._current_process is process:
                    self._current_process = None

    def _prepare_apktool_cmd(self, *args) -> list[str]:
        """Prepare apktool command - handle .jar and .bat differently"""
        if self.apktool.endswith('.jar'):
            return ['java', '-jar', self.apktool] + list(args)
        else:
            return [self.apktool] + list(args)

    @staticmethod
    def _contains_apktool_error(output: str) -> bool:
        """Detect apktool failures that can still return 0 on some wrappers."""
        if not output:
            return False

        markers = [
            'AndrolibException',
            'brut.androlib.exceptions',
            'Could not smali file',
            'Error for input',
            'Exception in thread "main"',
        ]
        return any(marker in output for marker in markers)

    def decompile(self, apk_path: str, output_dir: str) -> tuple[bool, str]:
        logger.info(f"Decompiling: {apk_path}")
        try:
            if Path(output_dir).exists():
                logger.info(f"Deleting old output: {output_dir}")
                shutil.rmtree(output_dir)

            cmd = self._prepare_apktool_cmd('d', '-f', apk_path, '-o', output_dir)
            result = self._run_command(cmd, timeout=300)

            if result.returncode == 0 and not self._contains_apktool_error(result.stdout) and Path(output_dir).exists():
                logger.info("Decompile OK")
                return True, "OK"
            else:
                logger.error(f"apktool decompile failed (rc={result.returncode})")
                return False, f"apktool error: Decompile failed (rc={result.returncode})"

        except subprocess.TimeoutExpired:
            logger.error("TIMEOUT: apktool decompile took too long")
            return False, "Timeout: Decompile took too long"
        except InterruptedError:
            logger.warning("Decompile cancelled")
            return False, "Cancelled"
        except Exception as e:
            logger.error(f"Exception: {str(e)}")
            return False, str(e)

    def rebuild(self, apk_dir: str, output_apk: str) -> tuple[bool, str]:
        logger.info(f"Building APK: {apk_dir}")
        try:
            cmd = self._prepare_apktool_cmd('b', '-o', output_apk, apk_dir)
            result = self._run_command(cmd, timeout=600)

            if result.returncode == 0 and not self._contains_apktool_error(result.stdout) and Path(output_apk).exists():
                logger.info("Rebuild OK")
                return True, "OK"
            else:
                logger.error(f"apktool rebuild failed (rc={result.returncode})")
                if not Path(output_apk).exists():
                    return False, "apktool error: Output APK was not created"
                return False, f"apktool error: Rebuild failed (rc={result.returncode})"
        except subprocess.TimeoutExpired:
            logger.error("TIMEOUT: apktool rebuild took too long")
            return False, "Timeout: Rebuild took too long"
        except InterruptedError:
            logger.warning("Rebuild cancelled")
            return False, "Cancelled"
        except Exception as e:
            logger.error(f"Exception: {str(e)}")
            return False, str(e)

    def sign(self, apk_path: str, keystore: str, alias: str, password: str = None) -> tuple[bool, str]:
        logger.info(f"Signing APK")
        try:
            cmd = [self.apksigner, 'sign', '--ks', keystore, '--ks-key-alias', alias]

            if password:
                cmd.extend(['--ks-pass', f'pass:{password}', '--key-pass', f'pass:{password}'])

            cmd.append(apk_path)
            logger.info(f"apksigner command: sign --ks [keystore] --ks-key-alias {alias} --ks-pass pass:*** {apk_path}")

            result = self._run_command(cmd, timeout=60)

            if result.returncode == 0:
                logger.info("Signing OK")
                return True, "OK"
            else:
                logger.error(f"apksigner returned {result.returncode}")
                return False, f"apksigner error: Return code {result.returncode}"
        except subprocess.TimeoutExpired:
            logger.error("TIMEOUT: Signing took too long")
            return False, "Timeout: Signing took too long"
        except InterruptedError:
            logger.warning("Signing cancelled")
            return False, "Cancelled"
        except Exception as e:
            logger.error(f"Exception: {str(e)}")
            return False, str(e)


class APKWorkerThread(QThread):
    """QThread for APK workflow with signal-based logging"""
    log_message = Signal(str)
    patch_status = Signal(str, bool, str)  # patch_id, success, message
    workflow_finished = Signal(bool, str)

    def __init__(self, apk_path: str, patch_vars: dict, config: dict, apktool_path: str, apksigner_path: str):
        super().__init__()
        self.apk_path = apk_path
        self.patch_vars = patch_vars
        self.config = config
        self.apktool_path = apktool_path
        self.apksigner_path = apksigner_path
        self.stop_event = Event()
        self.worker = None

    def request_stop(self):
        """Request workflow stop and forward it to active command worker."""
        self.stop_event.set()
        self.log_message.emit("Stop requested...")
        if self.worker:
            self.worker.request_stop()

    def _was_stopped(self) -> bool:
        return self.stop_event.is_set()

    def run(self):
        try:
            self.log_message.emit("=" * 60)
            self.log_message.emit("PATCHING STARTED")
            self.log_message.emit("=" * 60)

            if self._was_stopped():
                self.workflow_finished.emit(False, "Cancelled")
                return

            keystore_path = self.config.get('keystore_path')
            alias = self.config.get('alias')
            keystore_password = self.config.get('keystore_password')

            if not keystore_path or not Path(keystore_path).exists():
                self.log_message.emit("Keystore not found!")
                self.workflow_finished.emit(False, "Keystore not found")
                return

            work_dir = Path(self.apk_path).parent / "calimoto_work"
            output_apk = Path(self.apk_path).parent / f"patched-{datetime.now().strftime('%Y%m%d-%H%M%S')}.apk"

            self.log_message.emit("\n[1/6] Decompiling APK...")
            self.worker = APKWorker(
                self.apktool_path,
                self.apksigner_path,
                log_callback=logger.info,
                stop_event=self.stop_event,
            )
            success, msg = self.worker.decompile(self.apk_path, str(work_dir))

            if not success:
                if msg == "Cancelled":
                    self.log_message.emit("Workflow cancelled.")
                    self.workflow_finished.emit(False, "Cancelled")
                    return
                self.log_message.emit(f"Error: {msg}")
                self.workflow_finished.emit(False, msg)
                return

            if self._was_stopped():
                self.log_message.emit("Workflow cancelled.")
                self.workflow_finished.emit(False, "Cancelled")
                return

            self.log_message.emit("\n[2/6] Applying patches...")
            patches = [name for name, var in self.patch_vars.items() if var.isChecked()]
            patcher = PatchManager(work_dir)
            for patch_name in patches:
                if self._was_stopped():
                    self.log_message.emit("Workflow cancelled.")
                    self.workflow_finished.emit(False, "Cancelled")
                    return
                success, msg = patcher.apply_patch(patch_name)
                self.log_message.emit(msg)

                # Determine if patch was applied successfully or skipped
                is_success = success and not msg.startswith("SKIP")
                self.patch_status.emit(patch_name, is_success, msg)

                if not success:
                    self.log_message.emit(f"Error: {msg}")
                    self.workflow_finished.emit(False, msg)
                    return

            self.log_message.emit("\n[3/6] Building APK...")
            success, msg = self.worker.rebuild(str(work_dir), str(output_apk))

            if not success:
                if msg == "Cancelled":
                    self.log_message.emit("Workflow cancelled.")
                    self.workflow_finished.emit(False, "Cancelled")
                    return
                self.log_message.emit(f"Error: {msg}")
                self.workflow_finished.emit(False, msg)
                return

            if self._was_stopped():
                self.log_message.emit("Workflow cancelled.")
                self.workflow_finished.emit(False, "Cancelled")
                return

            self.log_message.emit("\n[4/6] Signing APK...")
            success, msg = self.worker.sign(str(output_apk), keystore_path, alias, keystore_password)

            if not success:
                if msg == "Cancelled":
                    self.log_message.emit("Workflow cancelled.")
                    self.workflow_finished.emit(False, "Cancelled")
                    return
                self.log_message.emit(f"Error: {msg}")
                self.workflow_finished.emit(False, msg)
                return

            self.log_message.emit("\n[5/6] Cleanup...")
            shutil.rmtree(work_dir, ignore_errors=True)

            self.log_message.emit("\n[6/6] DONE!")
            self.log_message.emit(f"Output: {output_apk}")
            self.log_message.emit("=" * 60)

            self.workflow_finished.emit(True, str(output_apk))

        except Exception as e:
            self.log_message.emit(f"Error: {str(e)}")
            self.workflow_finished.emit(False, str(e))
        finally:
            self.worker = None


# Material Design 3 QSS Stylesheet
QSS_STYLESHEET = """
QMainWindow, QWidget, QFrame, QGroupBox {
    background-color: #131313;
    color: #e5e2e1;
}

QLabel {
    background-color: transparent;
    color: #e5e2e1;
}

QLabel[style*="muted"] {
    color: #bccabb;
}

QLineEdit {
    background-color: #1b1b1c;
    color: #e5e2e1;
    border: 1px solid #3d4a3e;
    padding: 6px;
    border-radius: 4px;
}

QLineEdit:focus {
    border: 1px solid #56e084;
}

QPushButton {
    background-color: #2a2a2a;
    color: #e5e2e1;
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: bold;
}

QPushButton:hover {
    background-color: #353535;
}

QPushButton:pressed {
    background-color: #202020;
}

QPushButton[style*="primary"] {
    background-color: #33c36b;
    color: #003919;
}

QPushButton[style*="primary"]:hover {
    background-color: #56e084;
}

QPushButton[style*="primary"]:pressed {
    background-color: #2f9d59;
}

QPushButton:disabled {
    background-color: #1b1b1c;
    color: #bccabb;
}

QCheckBox {
    background-color: transparent;
    color: #e5e2e1;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 20px;
    height: 20px;
    background-color: #202020;
    border: 1px solid #3d4a3e;
    border-radius: 3px;
}

QCheckBox::indicator:checked {
    background-color: #56e084;
    border: 1px solid #56e084;
}

QPlainTextEdit {
    background-color: #0e0e0e;
    color: #d4d4d4;
    border: none;
    font-family: "Courier New";
    font-size: 11px;
}

QGroupBox {
    border: 1px solid #3d4a3e;
    border-radius: 4px;
    padding: 12px;
    margin-top: 6px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 3px 0 3px;
}

QScrollBar:vertical {
    background-color: #131313;
    width: 12px;
}

QScrollBar::handle:vertical {
    background-color: #353535;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background-color: #56e084;
}
"""


class MainWindow(QMainWindow):
    """Modern PySide6 UI with Material Design 3"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Calimoto Patcher")
        self.resize(1000, 600)
        self.center()

        # Colors (Material Design 3)
        self.colors = {
            'surface': '#131313',
            'surface_dim': '#131313',
            'surface_container': '#202020',
            'surface_container_low': '#1b1b1c',
            'surface_container_high': '#2a2a2a',
            'surface_container_highest': '#353535',
            'text': '#e5e2e1',
            'text_muted': '#bccabb',
            'primary': '#56e084',
            'primary_container': '#33c36b',
            'on_primary': '#003919',
            'outline': '#869486',
            'outline_variant': '#3d4a3e',
            'error': '#ffb4ab',
        }

        # State variables
        self.java_ok = False
        self.apktool_path = None
        self.apksigner_path = None
        self.apk_path = ""
        self.is_running = False
        self.config = EnvConfig.load()
        self.patch_vars = {}
        self.patch_status_labels = {}
        self.worker_thread = None
        self.control_start_btn = None
        self.control_start_label = None
        self.control_stop_btn = None
        self.loading_frames = ['|', '/', '-', '\\']
        self.loading_index = 0
        self.loading_timer = QTimer(self)
        self.loading_timer.timeout.connect(self._update_start_button_loading)

        # Setup UI
        self.setup_ui()
        self.setStyleSheet(QSS_STYLESHEET)

        # Cleanup old APKs on startup
        self.cleanup_old_apks()

        # Auto-check tools on startup
        self.check_tools()


    def center(self):
        screen = self.screen() or QGuiApplication.primaryScreen()
        screen_geometry = screen.availableGeometry()

        x = screen_geometry.x() + (screen_geometry.width() - self.width()) // 2
        y = screen_geometry.y() + (screen_geometry.height() - self.height()) // 2

        self.move(x, y)

    def cleanup_old_apks(self):
        """Delete old patched APKs and signature files on startup"""
        script_dir = Path(__file__).parent.resolve()

        patterns = ['patched-*.apk', 'patched-*.idsig']
        deleted_count = 0

        for pattern in patterns:
            for file_path in script_dir.glob(pattern):
                try:
                    file_path.unlink()
                    logger.info(f"Deleted old APK: {file_path.name}")
                    deleted_count += 1
                except Exception as e:
                    logger.warning(f"Could not delete {file_path.name}: {e}")

        if deleted_count > 0:
            logger.info(f"Cleanup: Removed {deleted_count} old APK files")

    def setup_ui(self):
        """Setup main layout"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(24, 12, 24, 12)
        main_layout.setSpacing(12)

        # HEADER
        header_layout = QHBoxLayout()
        header_label = QLabel("Calimoto Patcher")
        header_label.setFont(QFont("Inter", 28, QFont.Bold))
        header_label.setStyleSheet(f"color: {self.colors['primary']};")
        header_layout.addWidget(header_label)
        main_layout.addLayout(header_layout)

        # CENTER CARD
        card_widget = QFrame()
        card_widget.setStyleSheet(f"background-color: {self.colors['surface_container']}; border-radius: 4px;")
        card_layout = QVBoxLayout(card_widget)
        card_layout.setContentsMargins(24, 24, 24, 24)
        card_layout.setSpacing(12)

        # Control Bar
        control_layout = self._create_control_bar()
        card_layout.addLayout(control_layout)

        # Config Section
        config_layout = self._create_config_section()
        card_layout.addLayout(config_layout)

        # Status Label
        self.status_label = QLabel("Ready")
        self.status_label.setFont(QFont("Inter", 10, QFont.Bold))
        self.status_label.setStyleSheet(f"color: {self.colors['primary']};")
        card_layout.addWidget(self.status_label)

        main_layout.addWidget(card_widget, 1)

        # TERMINAL AREA
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(200)
        main_layout.addWidget(self.log_text)

        # Connect logger to log widget
        self._setup_logging()

    def _create_control_bar(self) -> QHBoxLayout:
        """Create control bar with 3 buttons"""
        layout = QHBoxLayout()
        layout.setSpacing(32)
        layout.addStretch()

        buttons = [
            ("⟳", "Check\nDependencies", self.check_tools),
            ("▶", "Start\nPatch", self.run_workflow),
            ("■", "Stop", self.stop_workflow),
        ]

        for icon, label, cmd in buttons:
            btn_layout = QVBoxLayout()
            btn_layout.setSpacing(8)

            btn = QPushButton(icon)
            btn.setFont(QFont("Arial", 28))
            btn.setFixedSize(QSize(70, 70))
            btn.clicked.connect(cmd)

            if icon == "▶":
                btn.setStyleSheet(f"QPushButton {{ background-color: {self.colors['primary_container']}; color: {self.colors['on_primary']}; border-radius: 8px; }}")
            else:
                btn.setStyleSheet(f"QPushButton {{ background-color: {self.colors['surface_container_highest']}; color: {self.colors['primary']}; border-radius: 8px; }}")

            label_widget = QLabel(label)
            label_widget.setFont(QFont("Inter", 8))
            label_widget.setAlignment(Qt.AlignCenter)
            label_widget.setStyleSheet(f"color: {self.colors['text_muted']}; background-color: transparent;")

            if icon == "▶":
                self.control_start_btn = btn
                self.control_start_label = label_widget
            elif icon == "■":
                self.control_stop_btn = btn

            btn_layout.addWidget(btn, alignment=Qt.AlignCenter)
            btn_layout.addWidget(label_widget, alignment=Qt.AlignCenter)
            btn_layout.addStretch()

            layout.addLayout(btn_layout)

        layout.addStretch()
        return layout

    def _create_config_section(self) -> QVBoxLayout:
        """Create configuration section"""
        layout = QVBoxLayout()
        layout.setSpacing(12)

        # File selection
        layout.addWidget(self._create_label("TARGET APPLICATION"))
        file_layout = QHBoxLayout()
        self.apk_entry = QLineEdit()
        self.apk_entry.setPlaceholderText("No APK file selected...")
        self.apk_entry.textChanged.connect(self.refresh_run_button_state)
        file_layout.addWidget(self.apk_entry)

        select_btn = QPushButton("SELECT APK")
        select_btn.setStyleSheet(f"QPushButton {{ background-color: {self.colors['primary_container']}; color: {self.colors['on_primary']}; }}")
        select_btn.clicked.connect(self._browse_apk)
        file_layout.addWidget(select_btn)
        layout.addLayout(file_layout)

        # Patch options
        layout.addWidget(self._create_label("ACTIVE PATCH MODULES"))
        patches_layout = QVBoxLayout()
        patches_layout.setSpacing(4)

        for patch_id, patch in PatchManager.PATCH_DEFINITIONS.items():
            patch_row_layout = QHBoxLayout()
            patch_row_layout.setSpacing(8)

            checkbox = QCheckBox(patch['name'].upper())
            checkbox.setChecked(True)
            self.patch_vars[patch_id] = checkbox

            status_label = QLabel("")
            status_label.setFont(QFont("Inter", 9))
            status_label.setStyleSheet(f"color: {self.colors['text_muted']}; background-color: transparent;")
            self.patch_status_labels[patch_id] = status_label

            patch_row_layout.addWidget(checkbox)
            patch_row_layout.addStretch()
            patch_row_layout.addWidget(status_label)

            patches_layout.addLayout(patch_row_layout)

        layout.addLayout(patches_layout)

        return layout

    def _create_label(self, text: str) -> QLabel:
        """Create a muted label"""
        label = QLabel(text)
        label.setFont(QFont("Inter", 8))
        label.setStyleSheet(f"color: {self.colors['text_muted']}; background-color: transparent;")
        return label

    def _setup_logging(self):
        """Setup logging to GUI"""
        class LogEmitter(QObject):
            message = Signal(str)

        class GUILogHandler(logging.Handler):
            def __init__(self, emitter):
                super().__init__()
                self.emitter = emitter

            def emit(self, record):
                msg = self.format(record)
                self.emitter.message.emit(msg)

        self.log_emitter = LogEmitter(self)
        self.log_emitter.message.connect(self.log_text.appendPlainText)

        handler = GUILogHandler(self.log_emitter)
        handler.setFormatter(logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s'))
        logger.addHandler(handler)

    def _browse_apk(self):
        """Browse for APK file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select APK",
            "",
            "APK Files (*.apk);;All Files (*.*)"
        )
        if file_path:
            self.apk_path = file_path
            self.apk_entry.setText(file_path)
            self.refresh_run_button_state()

    def check_tools(self):
        """Check for required tools"""
        logger.info("Dependency check started...")

        self.config = EnvConfig.load()

        try:
            result = subprocess.run(['java', '-version'],
                                  capture_output=True, text=True, timeout=5)
            self.java_ok = result.returncode == 0
        except:
            self.java_ok = False

        logger.info(f"Java: {'OK' if self.java_ok else 'NOT FOUND'}")

        self.apktool_path = ToolFinder.find_apktool()
        logger.info(f"apktool: {self.apktool_path or 'NOT FOUND'}")

        self.apksigner_path = ToolFinder.find_apksigner()
        logger.info(f"apksigner: {self.apksigner_path or 'NOT FOUND'}")

        if self.java_ok:
            keystore_ok, keystore_msg = self._ensure_keystore_exists(strict=False)
            if not keystore_ok:
                logger.warning(f"Keystore auto-create during dependency check failed: {keystore_msg}")
            elif keystore_msg == "CREATED":
                logger.info("Keystore was automatically created during dependency check")
            elif keystore_msg == "EXISTS":
                logger.info("Keystore exists")
        else:
            logger.info("Keystore check skipped: Java not found")

        logger.info("Dependency check completed")

        self.refresh_run_button_state()

    def refresh_run_button_state(self):
        """Update button state based on validation"""
        if self.is_running:
            if self.control_start_btn:
                self.control_start_btn.setEnabled(False)
            if self.control_stop_btn:
                self.control_stop_btn.setEnabled(True)
            self.status_label.setText("Patching running...")
            self.status_label.setStyleSheet(
                f"color: {self.colors['primary']}; background-color: transparent;"
            )
            return

        ready, status = self._can_start_patching()
        if self.control_start_btn:
            self.control_start_btn.setEnabled(ready)
        if self.control_stop_btn:
            self.control_stop_btn.setEnabled(False)
        self.status_label.setText(status)
        self.status_label.setStyleSheet(
            f"color: {self.colors['primary'] if ready else self.colors['error']}; background-color: transparent;"
        )

    def _set_running_ui_state(self, running: bool):
        """Toggle start button into loading mode while workflow is running"""
        self.is_running = running

        if running:
            if self.control_start_btn:
                self.control_start_btn.setEnabled(False)
            if self.control_stop_btn:
                self.control_stop_btn.setEnabled(True)
            if self.control_start_label:
                self.control_start_label.setText("Patching\n...")
            self.loading_index = 0
            self._update_start_button_loading()
            self.loading_timer.start(120)
            self.status_label.setText("Patching running...")
            self.status_label.setStyleSheet(
                f"color: {self.colors['primary']}; background-color: transparent;"
            )
            return

        self.loading_timer.stop()
        if self.control_start_btn:
            self.control_start_btn.setText("▶")
        if self.control_start_label:
            self.control_start_label.setText("Start\nPatch")
        if self.control_stop_btn:
            self.control_stop_btn.setEnabled(False)
        self.refresh_run_button_state()

    def stop_workflow(self):
        """Request graceful stop for running patch process."""
        if not self.is_running or not self.worker_thread:
            QMessageBox.information(self, "Stop", "No running patch process.")
            return

        if self.control_stop_btn:
            self.control_stop_btn.setEnabled(False)

        self.status_label.setText("Stopping...")
        self.status_label.setStyleSheet(
            f"color: {self.colors['primary']}; background-color: transparent;"
        )
        logger.warning("Stop requested by user")
        self.worker_thread.request_stop()

    def _update_start_button_loading(self):
        """Animate a simple spinner on the center start button"""
        if not self.control_start_btn:
            return

        frame = self.loading_frames[self.loading_index]
        self.loading_index = (self.loading_index + 1) % len(self.loading_frames)
        self.control_start_btn.setText(frame)

    def _can_start_patching(self) -> tuple[bool, str]:
        """Validate readiness to start patching"""
        if not self.java_ok:
            return False, "Java not found"
        if not self.apktool_path:
            return False, "apktool not found"
        if not self.apksigner_path:
            return False, "apksigner not found"

        if not self.config:
            return False, "Setup/Keystore missing"

        required_keys = ['keystore_path']
        missing = [k for k in required_keys if not self.config.get(k)]
        if missing:
            return False, f"Setup incomplete: {', '.join(missing)}"

        keystore_path = self.config.get('keystore_path', '')
        if keystore_path and Path(keystore_path).exists() and not self.config.get('keystore_password'):
            return False, "Setup incomplete: keystore_password"

        if not self.apk_path:
            return False, "Select APK file"
        if not Path(self.apk_path).exists():
            return False, "APK file not found"

        return True, "Ready to start"

    def _ensure_keystore_exists(self, strict: bool = True) -> tuple[bool, str]:
        """Create missing keystore automatically from env configuration."""
        self.config = self.config or {}
        keystore_path = self.config.get('keystore_path', '')
        alias = self.config.get('alias') or 'myalias'

        if not keystore_path:
            if not strict:
                keystore_path = str(DEFAULT_KEYSTORE_FILE)
                self.config['keystore_path'] = keystore_path
                self.config['alias'] = alias
                EnvConfig.save(self.config)
                logger.info(f"Keystore path missing in env - using default path: {keystore_path}")
            else:
                return False, "Setup incomplete: keystore_path"

        keystore_file = Path(keystore_path)
        if keystore_file.exists():
            return True, "EXISTS"

        logger.warning("Keystore missing - starting automatic creation from env...")

        try:
            keystore_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            return False, f"Keystore path error: {e}"

        success, generated_password, error = KeystoreGenerator.create_keystore(str(keystore_file), alias)
        if not success:
            return False, f"Keystore creation failed: {error}"

        self.config['keystore_path'] = str(keystore_file)
        self.config['alias'] = alias
        self.config['keystore_password'] = generated_password
        EnvConfig.save(self.config)
        logger.info("Keystore created automatically and env updated")
        return True, "CREATED"

    def run_workflow(self):
        """Start the patching workflow"""
        if self.is_running:
            QMessageBox.warning(self, "Running", "Patching is already running!")
            return

        ready, reason = self._can_start_patching()
        if not ready:
            QMessageBox.critical(self, "Error", f"Cannot start: {reason}")
            return

        self.config = EnvConfig.load()
        success, msg = self._ensure_keystore_exists()
        if not success:
            QMessageBox.critical(self, "Error", f"Cannot prepare keystore: {msg}")
            self.refresh_run_button_state()
            return

        # Reset patch status labels
        for patch_id, label in self.patch_status_labels.items():
            label.setText("")
            label.setStyleSheet(f"color: {self.colors['text_muted']}; background-color: transparent;")

        self._set_running_ui_state(True)

        # Create and start worker thread
        self.worker_thread = APKWorkerThread(
            self.apk_path,
            self.patch_vars,
            self.config,
            self.apktool_path,
            self.apksigner_path
        )

        self.worker_thread.log_message.connect(self._on_log_message)
        self.worker_thread.patch_status.connect(self._on_patch_status)
        self.worker_thread.workflow_finished.connect(self._on_workflow_finished)
        self.worker_thread.start()

    def _on_patch_status(self, patch_id: str, success: bool, message: str):
        """Handle patch status update"""
        if patch_id not in self.patch_status_labels:
            return

        label = self.patch_status_labels[patch_id]

        if success:
            label.setText("✓ OK")
            label.setStyleSheet(f"color: {self.colors['primary']}; background-color: transparent; font-weight: bold;")
        else:
            label.setText("✗ SKIP")
            label.setStyleSheet(f"color: {self.colors['error']}; background-color: transparent; font-weight: bold;")

    def _on_log_message(self, message: str):
        """Handle log messages from worker thread"""
        self.log_text.appendPlainText(message)

    def _on_workflow_finished(self, success: bool, message: str):
        """Handle workflow completion"""
        self._set_running_ui_state(False)

        if success:
            QMessageBox.information(self, "Success", f"Patching completed!\n\n{message}")
        elif message == "Cancelled":
            QMessageBox.information(self, "Stopped", "Patching was cancelled.")
        else:
            QMessageBox.critical(self, "Error", f"Patching failed: {message}")


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == '__main__':
    main()
