#!/usr/bin/env python3

import sys
import os
import subprocess
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QVBoxLayout, QWidget,
    QPushButton, QMessageBox, QGroupBox, QFormLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

def get_total_ram_gb():
    """Get total physical RAM in gigabytes (rounded up)."""
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                if line.startswith('MemTotal:'):
                    kb = int(line.split()[1])
                    # Convert KB to GB, round up
                    return (kb + 1024 * 1024 - 1) // (1024 * 1024)
    except Exception:
        return None
    return None

def get_swap_info():
    """
    Returns list of dicts: [{'name': '/swapfile', 'size_gb': 8, 'type': 'file'}, ...]
    """
    try:
        result = subprocess.run(
            ['swapon', '--show=NAME,SIZE,TYPE'],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return []

        lines = result.stdout.strip().split('\n')
        if len(lines) <= 1:
            return []

        swaps = []
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 3:
                continue
            name = parts[0]
            size_str = parts[1]
            swap_type = parts[2]

            # Parse size like '8G', '16.0G', '512M'
            size_gb = 0
            if size_str.endswith('G'):
                try:
                    size_gb = int(float(size_str.rstrip('G')))
                except ValueError:
                    size_gb = 0
            elif size_str.endswith('M'):
                try:
                    size_gb = int(float(size_str.rstrip('M')) / 1024 + 0.5)
                except ValueError:
                    size_gb = 0
            elif size_str.endswith('K'):
                try:
                    size_gb = int(float(size_str.rstrip('K')) / (1024 * 1024) + 0.5)
                except ValueError:
                    size_gb = 0

            swaps.append({
                'name': name,
                'size_gb': size_gb,
                'type': swap_type
            })
        return swaps
    except Exception:
        return []
    
def get_kernel_resume_config():
    """Check if kernel cmdline has resume= and possibly resume_offset="""
    try:
        with open('/proc/cmdline', 'r') as f:
            cmdline = f.read()
        resume = None
        resume_offset = None
        for part in cmdline.split():
            if part.startswith('resume='):
                resume = part.split('=', 1)[1]
            elif part.startswith('resume_offset='):
                resume_offset = part.split('=', 1)[1]
        return resume, resume_offset
    except Exception:
        return None, None    

def get_swap_partition_uuid():
    """Get UUID of the first non-zram swap partition (if any)."""
    try:
        swaps = get_swap_info()
        for swap in swaps:
            if swap['type'] == 'partition' and not swap['name'].startswith('/dev/zram'):
                # Get UUID via blkid
                result = subprocess.run(['blkid', '-s', 'UUID', '-o', 'value', swap['name']],
                                        capture_output=True, text=True)
                if result.returncode == 0:
                    uuid = result.stdout.strip()
                    if uuid:
                        return uuid
    except Exception:
        pass
    return None

def get_free_space_gb(path="/"):
    """Get free space on filesystem (in GB, rounded down)."""
    try:
        stat = os.statvfs(path)
        free_bytes = stat.f_frsize * stat.f_bavail
        return free_bytes // (1024**3)
    except Exception:
        return 0
    
class HibernationHelper(QMainWindow):
    def __init__(self):
        super().__init__()
        # Set window icon (uses system theme)
        icon = QIcon.fromTheme("system-suspend-hibernate")
        if icon.isNull():
            # Fallback if icon not found
            icon = QIcon.fromTheme("preferences-system-power")
        self.setWindowIcon(icon)        
        self.hibernation_ready = False  # ← new state tracker        
        self.setWindowTitle("Hibernation Helper")
        self.resize(600, 450)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        title = QLabel("🐧 Hibernation Helper for Fedora")
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold; margin: 10px;")
        layout.addWidget(title)

        desc = QLabel(
            "This tool checks if your system can hibernate.<br>"
            "Hibernation requires disk-based swap ≥ your RAM size.<br>"
            "<b>zram does NOT support hibernation.</b>"
        )
        desc.setTextFormat(Qt.TextFormat.RichText)  # ← This enables HTML
        desc.setAlignment(Qt.AlignCenter)
        desc.setStyleSheet("margin-bottom: 20px; color: #555;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.status_group = QGroupBox("System Status")
        self.status_layout = QFormLayout()
        self.status_group.setLayout(self.status_layout)
        layout.addWidget(self.status_group)

        self.check_btn = QPushButton("🔍 Check Hibernation Readiness")
        self.check_btn.clicked.connect(self.check_status)
        layout.addWidget(self.check_btn)

        self.test_btn = QPushButton("💤 Test Hibernation Now")
        self.test_btn.clicked.connect(self.test_hibernate)
        self.test_btn.setEnabled(False)  # ← start disabled until check runs
        layout.addWidget(self.test_btn)      

        self.enable_btn = QPushButton("🛠️ Enable Hibernation")
        self.enable_btn.clicked.connect(self.enable_hibernation)
        layout.addWidget(self.enable_btn)

        layout.addStretch()

    def add_status_row(self, label_text, value_text):
        label = QLabel(f"<b>{label_text}:</b>")
        value = QLabel(value_text)
        value.setTextInteractionFlags(Qt.TextSelectableByMouse)
        value.setWordWrap(True)
        self.status_layout.addRow(label, value)

    def show_result(self, message, success):
        icon = QMessageBox.Information if success else QMessageBox.Warning
        box = QMessageBox(self)
        box.setIcon(icon)
        box.setWindowTitle("Hibernation Check Result")
        box.setText(message)
        box.setModal(True)
        box.raise_()
        box.exec()

    def check_status(self):
        ram_gb = get_total_ram_gb()
        swaps = get_swap_info()

        # Clear previous status
        while self.status_layout.count():
            child = self.status_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if ram_gb is None:
            self.add_status_row("RAM", "❌ Failed to read RAM")
            return

        self.add_status_row("Total RAM", f"{ram_gb} GB")

        if not swaps:
            self.add_status_row("Swap", "❌ No swap active")
            self.show_result("Hibernation not possible: no swap configured.", False)
            return

        # Filter out zram (not usable for hibernation)
        hibernation_swaps = [s for s in swaps if not s['name'].startswith('/dev/zram')]
        total_hibernation_swap_gb = sum(s['size_gb'] for s in hibernation_swaps)
        total_swap_gb = sum(s['size_gb'] for s in swaps)

        # Show full swap in status (including zram)
        swap_details = ", ".join(f"{s['name']} ({s['size_gb']} GB, {s['type']})" for s in swaps)
        self.add_status_row("Swap (total)", f"{total_swap_gb} GB ({swap_details})")

        if hibernation_swaps:
            hib_details = ", ".join(f"{s['name']} ({s['size_gb']} GB)" for s in hibernation_swaps)
            self.add_status_row("Swap (hibernation)", f"{total_hibernation_swap_gb} GB ({hib_details})")
        else:
            self.add_status_row("Swap (hibernation)", "❌ None (zram doesn't support hibernation)")

        # Check kernel resume setup
        resume, resume_offset = get_kernel_resume_config()
        if resume:
            info = f"UUID or device: {resume}"
            if resume_offset:
                info += f" (offset: {resume_offset})"
            self.add_status_row("Kernel Resume", info)
        else:
            self.add_status_row("Kernel Resume", "❌ Not set — hibernation may fail")            

        # Determine if hibernation is fully ready
        self.hibernation_ready = (
            total_hibernation_swap_gb >= ram_gb and
            resume is not None
        )

        # Enable/disable test button
        self.test_btn.setEnabled(self.hibernation_ready)

        # Show verdict
        if self.hibernation_ready:
            self.show_result("✅ Hibernation is fully configured and ready!", True)
        else:
            if total_hibernation_swap_gb < ram_gb:
                needed = ram_gb - total_hibernation_swap_gb
                msg = (
                    f"⚠️ Not enough disk-based swap.\n"
                    f"Need {ram_gb} GB, have {total_hibernation_swap_gb} GB.\n"
                    f"Short by {needed} GB."
                )
            elif resume is None:
                msg = "⚠️ Kernel resume is not configured.\nUse 'Enable Hibernation' to set it up."
            else:
                msg = "⚠️ Hibernation is not ready."

            self.show_result(msg, False)

    def test_hibernate(self):
        reply = QMessageBox.question(
            self,
            "Confirm Hibernation Test",
            "This will attempt to hibernate your system immediately.\n"
            "<b>⚠️ Save all your work first!</b>\n\n"
            "Your screen will turn off, and the system will resume in a few seconds.\n"
            "Continue?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                # Use pkexec to run hibernation with authentication
                subprocess.Popen(['pkexec', 'systemctl', 'hibernate'])
                # We don't wait for it — system will hibernate
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to start hibernation:\n{str(e)}"
                )            

    def enable_hibernation(self):
        # Check if already enabled
        resume, _ = get_kernel_resume_config()
        if resume:
            QMessageBox.information(
                self,
                "Already Enabled",
                "✅ Hibernation is already configured!"
            )
            return

        # Try to get swap partition UUID first
        uuid = get_swap_partition_uuid()
        if uuid:
            # Use existing partition
            self._configure_hibernation_with_uuid(uuid)
            return

        # If no partition, offer to create a swap file
        ram_gb = get_total_ram_gb()
        if ram_gb is None:
            ram_gb = 8  # fallback

        free_gb = get_free_space_gb("/")
        if free_gb < ram_gb + 2:
            QMessageBox.warning(
                self,
                "Not Enough Space",
                f"Need at least {ram_gb + 2} GB free on root filesystem.\n"
                f"You have {free_gb} GB free.\n"
                "Free up space or add a swap partition manually."
            )
            return

        reply = QMessageBox.question(
            self,
            "Create Swap File?",
            f"No swap partition found.\n"
            f"Would you like to create a {ram_gb} GB swap file to enable hibernation?\n\n"
            f"• File will be created at: /swapfile\n"
            f"• Requires {ram_gb} GB free space (you have {free_gb} GB)\n"
            f"• Your password will be required.",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self._create_and_configure_swap_file(ram_gb)

    def _configure_hibernation_with_uuid(self, uuid):
        reply = QMessageBox.question(
            self,
            "Enable Hibernation?",
            f"Configure kernel to resume from:\nUUID={uuid}\n\nProceed?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                cmd = ['grubby', '--update-kernel=ALL', f'--args=resume=UUID={uuid}']
                result = subprocess.run(['pkexec'] + cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    QMessageBox.information(
                        self,
                        "Success",
                        "✅ Hibernation enabled!\nPlease reboot to apply."
                    )
                else:
                    QMessageBox.critical(self, "Error", f"grubby failed:\n{result.stderr}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed: {str(e)}")

    def _create_and_configure_swap_file(self, size_gb):
        try:
            cmd = [
                'pkexec', 'sh', '-c',
                f'set -e; '
                f'dd if=/dev/zero of=/swapfile bs=1M count={size_gb * 1024} status=progress; '
                f'chmod 600 /swapfile; '
                f'mkswap /swapfile; '
                f'swapon /swapfile; '
                f'echo "/swapfile none swap defaults 0 0" >> /etc/fstab; '
                f'uuid=$(findmnt / -o UUID -n); '
                f'offset=$(filefrag -v /swapfile | awk "NR==4 {{print \\$4}}"); '
                f'grubby --update-kernel=ALL --args="resume=UUID=$uuid resume_offset=$offset"; '
                f'echo "Success"'
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            if result.returncode == 0:
                QMessageBox.information(
                    self,
                    "Success",
                    f"✅ {size_gb} GB swap file created and hibernation enabled!\n"
                    "Please reboot to apply changes."
                )
            else:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to create swap file:\n{result.stderr}"
                )
        except subprocess.TimeoutExpired:
            QMessageBox.critical(self, "Timeout", "Swap file creation took too long.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Unexpected error:\n{str(e)}")                            

app = QApplication(sys.argv)
window = HibernationHelper()
window.show()
app.exec()