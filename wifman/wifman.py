#!/usr/bin/env python3
"""
WiFMan - WiFi Network Manager for WiFi Pineapple Pager
Easily switch between saved WiFi profiles with a graphical interface.

Author: LOCOSP
Version: 1.0
"""

import os
import sys
import json
import subprocess
import time

# Add lib directory to path for pagerctl import
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

from pagerctl import Pager

# ============================================================
# CONSTANTS
# ============================================================

PAYLOAD_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_FILE = os.path.join(PAYLOAD_DIR, "profiles.json")

# WiFi Pineapple Pager Client Mode Architecture:
# - GUI uses ONLY wireless.wlan0cli (single STA profile)
# - wireless.wlan0cli.disabled = 0/1 controls GUI toggle ON/OFF
# - We NEVER create new STA interfaces - only modify wlan0cli
# - This keeps full compatibility with Pineapple GUI
UCI_INTERFACE = "wlan0cli"      # UCI config section name
RUNTIME_INTERFACE = "phy0-sta0"  # Runtime interface for status check
NETWORK_INTERFACE = "cli"        # Network interface name

# Colors
COLOR_BG = 0x0821           # Dark blue background
COLOR_HEADER_BG = 0x2104    # Darker header
COLOR_MENU_BG = 0x1082      # Menu item background
COLOR_MENU_SEL = 0x03E0     # Selected item (green)
COLOR_TEXT = 0xFFFF         # White text
COLOR_TEXT_DIM = 0x8410     # Gray text
COLOR_CONNECTED = 0x07E0    # Green for connected
COLOR_DISCONNECTED = 0xF800 # Red for disconnected
COLOR_ACCENT = 0x07FF       # Cyan accent

# Security types
SECURITY_TYPES = ["open", "wep", "wpa", "wpa2", "wpa3"]

# Full keyboard layouts (grid)
# Row 0: numbers, Row 1-3: letters, Row 4: space/special
KEYBOARD_LOWER = [
    "1234567890",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm.-_",
]
KEYBOARD_UPPER = [
    "!@#$%^&*()",
    "QWERTYUIOP",
    "ASDFGHJKL",
    "ZXCVBNM.-_",
]

# ============================================================
# WIFI UTILITIES
# ============================================================

def get_current_wifi_status():
    """
    Get REAL runtime WiFi connection status.
    Uses 'iw dev' to check actual connection, not UCI config.
    This shows what network we're ACTUALLY connected to.
    """
    try:
        # Check runtime connection using iw (not iwinfo which may show config)
        result = subprocess.run(
            ["iw", "dev", RUNTIME_INTERFACE, "link"],
            capture_output=True,
            text=True,
            timeout=5
        )

        if result.returncode != 0 or "Not connected" in result.stdout:
            return None, None

        output = result.stdout
        ssid = None
        signal = None

        for line in output.split('\n'):
            line = line.strip()
            if line.startswith('SSID:'):
                ssid = line.split(':', 1)[1].strip()
            elif line.startswith('signal:'):
                signal = line.split(':', 1)[1].strip()

        return ssid, signal
    except Exception:
        return None, None


def get_gui_config_ssid():
    """
    Get SSID from GUI config (wireless.wlan0cli).
    This is what Pineapple GUI shows, not necessarily what's connected.
    """
    try:
        result = subprocess.run(
            ["uci", "get", f"wireless.{UCI_INTERFACE}.ssid"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def is_client_mode_enabled():
    """Check if Client Mode is enabled in GUI (disabled=0)."""
    try:
        result = subprocess.run(
            ["uci", "get", f"wireless.{UCI_INTERFACE}.disabled"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip() == '0'
    except Exception:
        pass
    return False


def connect_to_wifi(ssid, password, security):
    """
    Connect to a WiFi network by injecting into wireless.wlan0cli.
    This is GUI-compatible - Pineapple GUI will show correct state.

    Flow:
    1. ifdown cli (clean disconnect)
    2. Set SSID, key, encryption in wlan0cli
    3. Set disabled=0 (enables Client Mode in GUI)
    4. Commit and reload wireless (not full network restart)
    """
    try:
        # Step 1: Clean disconnect first
        subprocess.run(["ifdown", NETWORK_INTERFACE], capture_output=True, timeout=10)
        time.sleep(1)

        # Step 2: Configure wireless.wlan0cli using UCI
        subprocess.run(
            ["uci", "set", f"wireless.{UCI_INTERFACE}.ssid={ssid}"],
            check=True, timeout=5
        )

        # Step 3: Set encryption and key
        if security == "open":
            subprocess.run(
                ["uci", "set", f"wireless.{UCI_INTERFACE}.encryption=none"],
                check=True, timeout=5
            )
            # Remove key if exists
            subprocess.run(
                ["uci", "delete", f"wireless.{UCI_INTERFACE}.key"],
                capture_output=True, timeout=5
            )
        else:
            # Map security type to UCI encryption value
            enc_map = {
                "wep": "wep",
                "wpa": "psk",
                "wpa2": "psk2",
                "wpa3": "sae"
            }
            enc_type = enc_map.get(security, "psk2")

            subprocess.run(
                ["uci", "set", f"wireless.{UCI_INTERFACE}.encryption={enc_type}"],
                check=True, timeout=5
            )
            subprocess.run(
                ["uci", "set", f"wireless.{UCI_INTERFACE}.key={password}"],
                check=True, timeout=5
            )

        # Step 4: Enable Client Mode (GUI toggle ON)
        subprocess.run(
            ["uci", "set", f"wireless.{UCI_INTERFACE}.disabled=0"],
            check=True, timeout=5
        )

        # Step 5: Commit changes
        subprocess.run(["uci", "commit", "wireless"], check=True, timeout=5)

        # Step 6: Reload wireless only (less disruptive than full network restart)
        # Use wifi reload instead of service network restart to avoid killing pineapd
        subprocess.run(["wifi", "reload"], capture_output=True, timeout=60)
        time.sleep(2)

        # Step 7: Bring up the client interface
        subprocess.run(["ifup", NETWORK_INTERFACE], capture_output=True, timeout=30)

        return True

    except Exception as e:
        return False


def disconnect_wifi():
    """
    Disconnect WiFi by setting disabled=1.
    This turns Client Mode OFF in Pineapple GUI.
    """
    try:
        # Bring down client interface first
        subprocess.run(["ifdown", NETWORK_INTERFACE], capture_output=True, timeout=10)

        # Set disabled=1 (GUI toggle OFF)
        subprocess.run(
            ["uci", "set", f"wireless.{UCI_INTERFACE}.disabled=1"],
            check=True, timeout=5
        )
        subprocess.run(["uci", "commit", "wireless"], check=True, timeout=5)

        # Reload wireless (less disruptive than full network restart)
        subprocess.run(["wifi", "reload"], capture_output=True, timeout=60)

        return True
    except Exception:
        return False


def scan_wifi_networks():
    """Scan for available WiFi networks using iwinfo."""
    networks = []
    try:
        # Use iwinfo wlan0 scan (not wlan0cli)
        result = subprocess.run(
            ["iwinfo", "wlan0", "scan"],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return networks

        current_network = {}
        for line in result.stdout.split('\n'):
            line = line.strip()

            if line.startswith('Cell'):
                if current_network.get('ssid'):
                    networks.append(current_network)
                current_network = {}

            elif 'ESSID:' in line:
                start = line.find('"') + 1
                end = line.rfind('"')
                if start > 0 and end > start:
                    current_network['ssid'] = line[start:end]

            elif 'Signal:' in line:
                parts = line.split()
                for i, p in enumerate(parts):
                    if p == 'Signal:' and i + 1 < len(parts):
                        current_network['signal'] = parts[i + 1]
                        break

            elif 'Encryption:' in line:
                if 'none' in line.lower():
                    current_network['security'] = 'open'
                elif 'wpa3' in line.lower() or 'sae' in line.lower():
                    current_network['security'] = 'wpa3'
                elif 'wpa2' in line.lower():
                    current_network['security'] = 'wpa2'
                elif 'wpa' in line.lower():
                    current_network['security'] = 'wpa'
                elif 'wep' in line.lower():
                    current_network['security'] = 'wep'
                else:
                    current_network['security'] = 'wpa2'

        # Add last network
        if current_network.get('ssid'):
            networks.append(current_network)

    except Exception:
        pass

    return networks


def verify_connection(expected_ssid, timeout=15):
    """
    Verify that we actually connected to the expected network.
    Returns True if connected to expected_ssid within timeout.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        ssid, _ = get_current_wifi_status()
        if ssid == expected_ssid:
            return True
        time.sleep(2)
    return False


# ============================================================
# PROFILE MANAGEMENT
# ============================================================

def load_profiles():
    """Load profiles from JSON file."""
    try:
        if os.path.exists(PROFILES_FILE):
            with open(PROFILES_FILE, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {"profiles": [], "last_connected": None}


def save_profiles(data):
    """Save profiles to JSON file."""
    try:
        with open(PROFILES_FILE, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


# ============================================================
# UI COMPONENTS
# ============================================================

class WiFManUI:
    """WiFMan User Interface."""

    def __init__(self, pager):
        self.p = pager
        self.width = pager.width
        self.height = pager.height

    def draw_header(self, title, connected_ssid=None, signal=None):
        """Draw the header with REAL connection status (runtime, not config)."""
        # Header background
        self.p.fill_rect(0, 0, self.width, 40, COLOR_HEADER_BG)

        # Title
        self.p.draw_text_centered(5, title, COLOR_TEXT, 2)

        # Connection status bar - shows REAL connected network
        if connected_ssid:
            status_text = f"{connected_ssid}"
            if signal:
                status_text += f" {signal}"
            self.p.draw_text_centered(28, status_text, COLOR_CONNECTED, 1)
        else:
            # Check if Client Mode is enabled but not connected
            if is_client_mode_enabled():
                gui_ssid = get_gui_config_ssid()
                if gui_ssid:
                    self.p.draw_text_centered(28, f"Connecting: {gui_ssid}...", COLOR_ACCENT, 1)
                else:
                    self.p.draw_text_centered(28, "Client Mode ON (no network)", COLOR_ACCENT, 1)
            else:
                self.p.draw_text_centered(28, "Client Mode OFF", COLOR_DISCONNECTED, 1)

        # Separator line
        self.p.hline(0, 40, self.width, COLOR_ACCENT)

    def draw_legend(self):
        """Draw the control legend at the bottom."""
        y = self.height - 18
        self.p.fill_rect(0, y - 2, self.width, 20, COLOR_HEADER_BG)
        self.p.hline(0, y - 2, self.width, COLOR_ACCENT)

        legend = "UP/DOWN=Move  GREEN=Select  RED=Back"
        self.p.draw_text_centered(y, legend, COLOR_TEXT_DIM, 1)

    def draw_menu(self, items, selected_index, start_y=45, item_height=28):
        """Draw a menu with selectable items."""
        visible_items = (self.height - start_y - 25) // item_height

        # Calculate scroll offset
        scroll_offset = 0
        if selected_index >= visible_items:
            scroll_offset = selected_index - visible_items + 1

        for i, item in enumerate(items):
            if i < scroll_offset:
                continue

            display_idx = i - scroll_offset
            if display_idx >= visible_items:
                break

            y = start_y + display_idx * item_height

            # Background for selected item
            if i == selected_index:
                self.p.fill_rect(5, y, self.width - 10, item_height - 2, COLOR_MENU_SEL)
                text_color = COLOR_BG
            else:
                self.p.fill_rect(5, y, self.width - 10, item_height - 2, COLOR_MENU_BG)
                text_color = COLOR_TEXT

            # Item text
            if isinstance(item, dict):
                text = item.get('text', str(item))
                disabled = item.get('disabled', False)
                if disabled:
                    text_color = COLOR_TEXT_DIM
            else:
                text = str(item)

            # Center text vertically in item
            text_y = y + (item_height - 10) // 2
            self.p.draw_text(15, text_y, text, text_color, 1)

        # Scroll indicators
        if scroll_offset > 0:
            self.p.draw_text(self.width - 20, start_y, "^", COLOR_ACCENT, 1)
        if scroll_offset + visible_items < len(items):
            self.p.draw_text(self.width - 20, start_y + (visible_items - 1) * item_height, "v", COLOR_ACCENT, 1)

    def draw_keyboard(self, title, text, keyboard, row, col, is_upper=False):
        """Draw full on-screen keyboard grid."""
        self.p.clear(COLOR_BG)

        # Title
        self.p.draw_text_centered(2, title, COLOR_ACCENT, 1)

        # Text input field
        field_y = 18
        self.p.fill_rect(5, field_y, self.width - 10, 28, COLOR_MENU_BG)
        self.p.rect(5, field_y, self.width - 10, 28, COLOR_ACCENT)

        # Display text with cursor (scroll if too long)
        max_chars = (self.width - 40) // 6
        display_start = max(0, len(text) - max_chars + 2)
        display_text = text[display_start:]

        self.p.draw_text(12, field_y + 8, display_text, COLOR_TEXT, 1)

        # Cursor
        cursor_x = 12 + len(display_text) * 6
        self.p.fill_rect(cursor_x, field_y + 6, 2, 16, COLOR_ACCENT)

        # Mode and char count
        mode_text = "ABC" if is_upper else "abc"
        self.p.draw_text(self.width - 60, field_y + 8, mode_text, COLOR_TEXT_DIM, 1)

        # Keyboard grid
        key_w = 44
        key_h = 32
        start_y = 52

        for r_idx, r in enumerate(keyboard):
            row_width = len(r) * key_w
            start_x = (self.width - row_width) // 2

            for c_idx, ch in enumerate(r):
                x = start_x + c_idx * key_w
                y = start_y + r_idx * key_h

                # Highlight selected key
                if r_idx == row and c_idx == col:
                    self.p.fill_rect(x + 1, y + 1, key_w - 2, key_h - 2, COLOR_MENU_SEL)
                    self.p.rect(x, y, key_w, key_h, COLOR_TEXT)
                    ch_color = COLOR_BG
                else:
                    self.p.fill_rect(x + 1, y + 1, key_w - 2, key_h - 2, COLOR_MENU_BG)
                    ch_color = COLOR_TEXT

                # Draw character centered
                ch_x = x + (key_w - 6) // 2
                ch_y = y + (key_h - 8) // 2
                self.p.draw_text(ch_x, ch_y, ch, ch_color, 1)

        # Action row at bottom of keyboard
        action_y = start_y + len(keyboard) * key_h + 5
        actions = [("SPC", 80), ("DEL", 60), ("aA", 50), ("OK", 60)]
        total_w = sum(w for _, w in actions) + 30  # 30 = gaps
        action_x = (self.width - total_w) // 2

        for i, (label, w) in enumerate(actions):
            # Highlight if on action row
            is_action_row = row == len(keyboard)
            is_selected = is_action_row and col == i

            if is_selected:
                self.p.fill_rect(action_x, action_y, w, 28, COLOR_MENU_SEL)
                self.p.rect(action_x - 1, action_y - 1, w + 2, 30, COLOR_TEXT)
                lbl_color = COLOR_BG
            else:
                # Color code action buttons
                if label == "OK":
                    bg = Pager.rgb(0, 60, 0)
                elif label == "DEL":
                    bg = Pager.rgb(60, 0, 0)
                else:
                    bg = COLOR_MENU_BG
                self.p.fill_rect(action_x, action_y, w, 28, bg)
                lbl_color = COLOR_TEXT

            # Center label
            lbl_x = action_x + (w - len(label) * 6) // 2
            self.p.draw_text(lbl_x, action_y + 9, label, lbl_color, 1)
            action_x += w + 10

        # Legend
        self.p.hline(0, self.height - 16, self.width, COLOR_ACCENT)
        self.p.draw_text_centered(self.height - 12, "D-pad=Move  GREEN=Select  RED=Cancel", COLOR_TEXT_DIM, 1)

    def draw_dialog(self, title, message, options):
        """Draw a dialog box with options."""
        # Dialog background
        dialog_w = self.width - 40
        dialog_h = 100
        dialog_x = 20
        dialog_y = (self.height - dialog_h) // 2

        self.p.fill_rect(dialog_x, dialog_y, dialog_w, dialog_h, COLOR_MENU_BG)
        self.p.rect(dialog_x, dialog_y, dialog_w, dialog_h, COLOR_ACCENT)

        # Title
        self.p.draw_text_centered(dialog_y + 10, title, COLOR_ACCENT, 1)

        # Message
        self.p.draw_text_centered(dialog_y + 35, message, COLOR_TEXT, 1)

        # Options
        option_y = dialog_y + 65
        option_x = dialog_x + 20
        for opt in options:
            self.p.draw_text(option_x, option_y, opt, COLOR_TEXT_DIM, 1)
            option_x += len(opt) * 6 + 30

    def show_message(self, title, message, wait=True):
        """Show a message and optionally wait for button press."""
        self.p.clear(COLOR_BG)
        self.draw_header(title)

        # Message
        lines = message.split('\n')
        y = 80
        for line in lines:
            self.p.draw_text_centered(y, line, COLOR_TEXT, 1)
            y += 20

        if wait:
            self.p.draw_text_centered(self.height - 30, "Press any button...", COLOR_TEXT_DIM, 1)

        self.p.flip()

        if wait:
            self.p.wait_button()


# ============================================================
# KEYBOARD INPUT
# ============================================================

def keyboard_input(ui, pager, title="Enter text", initial_text=""):
    """Get text input using full on-screen keyboard grid."""
    text = initial_text
    row = 1  # Start on first letter row
    col = 0
    is_upper = False
    keyboard = KEYBOARD_UPPER if is_upper else KEYBOARD_LOWER

    # Total rows = keyboard rows + 1 action row
    num_kb_rows = len(keyboard)
    action_cols = 4  # SPC, DEL, aA, OK

    while True:
        ui.draw_keyboard(title, text, keyboard, row, col, is_upper)
        pager.flip()

        button = pager.wait_button()

        if button & Pager.BTN_UP:
            if row > 0:
                row -= 1
                # Adjust column for new row
                if row < num_kb_rows:
                    col = min(col, len(keyboard[row]) - 1)
            pager.beep(600, 20)

        elif button & Pager.BTN_DOWN:
            if row < num_kb_rows:  # Can go to action row
                row += 1
                if row == num_kb_rows:
                    col = min(col // 3, action_cols - 1)  # Map to action buttons
                else:
                    col = min(col, len(keyboard[row]) - 1)
            pager.beep(600, 20)

        elif button & Pager.BTN_LEFT:
            if row < num_kb_rows:
                col = (col - 1) % len(keyboard[row])
            else:
                col = (col - 1) % action_cols
            pager.beep(600, 20)

        elif button & Pager.BTN_RIGHT:
            if row < num_kb_rows:
                col = (col + 1) % len(keyboard[row])
            else:
                col = (col + 1) % action_cols
            pager.beep(600, 20)

        elif button & Pager.BTN_A:  # GREEN - select
            if row < num_kb_rows:
                # Type character from keyboard
                ch = keyboard[row][col]
                if len(text) < 64:
                    text += ch
                    pager.beep(700, 20)
                else:
                    pager.beep(300, 50)
            else:
                # Action row: SPC=0, DEL=1, aA=2, OK=3
                if col == 0:  # SPC - space
                    if len(text) < 64:
                        text += ' '
                        pager.beep(700, 20)
                elif col == 1:  # DEL - backspace
                    if text:
                        text = text[:-1]
                        pager.beep(400, 30)
                    else:
                        pager.beep(300, 50)
                elif col == 2:  # aA - toggle case
                    is_upper = not is_upper
                    keyboard = KEYBOARD_UPPER if is_upper else KEYBOARD_LOWER
                    pager.beep(500, 30)
                elif col == 3:  # OK - confirm
                    pager.beep(800, 50)
                    return text

        elif button & Pager.BTN_B:  # RED - cancel
            pager.beep(400, 50)
            return None


# ============================================================
# SECURITY SELECTOR
# ============================================================

def select_security(ui, pager, current_security="wpa2"):
    """Select WiFi security type."""
    items = [
        {"text": "Open (No Password)", "value": "open"},
        {"text": "WEP", "value": "wep"},
        {"text": "WPA", "value": "wpa"},
        {"text": "WPA2 (Recommended)", "value": "wpa2"},
        {"text": "WPA3", "value": "wpa3"},
    ]

    selected = 3  # Default to WPA2
    for i, item in enumerate(items):
        if item["value"] == current_security:
            selected = i
            break

    while True:
        pager.clear(COLOR_BG)
        ui.draw_header("Security Type")
        ui.draw_menu([item["text"] for item in items], selected)
        ui.draw_legend()
        pager.flip()

        button = pager.wait_button()

        if button & Pager.BTN_UP:
            selected = max(0, selected - 1)
            pager.beep(600, 30)

        elif button & Pager.BTN_DOWN:
            selected = min(len(items) - 1, selected + 1)
            pager.beep(600, 30)

        elif button & Pager.BTN_A:  # GREEN - select
            pager.beep(800, 50)
            return items[selected]["value"]

        elif button & Pager.BTN_B:  # RED - cancel
            pager.beep(400, 50)
            return None


# ============================================================
# ADD PROFILE SCREEN
# ============================================================

def add_profile_screen(ui, pager):
    """Screen for adding a new WiFi profile."""
    # Get SSID
    ssid = keyboard_input(ui, pager, "Enter SSID (Network Name)")
    if ssid is None or ssid == "":
        return None

    # Select security type
    security = select_security(ui, pager)
    if security is None:
        return None

    # Get password if needed
    password = ""
    if security != "open":
        password = keyboard_input(ui, pager, "Enter Password")
        if password is None:
            return None

    return {
        "ssid": ssid,
        "security": security,
        "password": password
    }


# ============================================================
# PROFILE LIST SCREEN
# ============================================================

def scan_screen(ui, pager, data):
    """Screen for scanning and selecting WiFi networks."""
    ui.show_message("Scanning", "Scanning for WiFi networks...", wait=False)
    networks = scan_wifi_networks()

    if not networks:
        ui.show_message("Scan Complete", "No networks found")
        return None

    selected = 0

    while True:
        # Build menu items
        items = []
        for n in networks:
            signal = n.get('signal', '')
            security = n.get('security', 'wpa2').upper()
            items.append(f"{n['ssid']} [{security}] {signal}")

        pager.clear(COLOR_BG)
        ui.draw_header(f"Found {len(networks)} Networks")
        ui.draw_menu(items, selected)
        ui.draw_legend()
        pager.flip()

        button = pager.wait_button()

        if button & Pager.BTN_UP:
            selected = max(0, selected - 1)
            pager.beep(600, 30)

        elif button & Pager.BTN_DOWN:
            selected = min(len(items) - 1, selected + 1)
            pager.beep(600, 30)

        elif button & Pager.BTN_A:  # GREEN - select network
            pager.beep(800, 50)
            network = networks[selected]

            # Get password if needed
            password = ""
            if network.get('security', 'wpa2') != 'open':
                password = keyboard_input(ui, pager, f"Password for {network['ssid']}")
                if password is None:
                    continue

            # Create and save profile
            profile = {
                "ssid": network['ssid'],
                "security": network.get('security', 'wpa2'),
                "password": password
            }

            # Check if profile already exists
            existing = False
            for i, p in enumerate(data.get("profiles", [])):
                if p["ssid"] == network["ssid"]:
                    data["profiles"][i] = profile
                    existing = True
                    break

            if not existing:
                data["profiles"].append(profile)

            save_profiles(data)

            # Connect
            ui.show_message("Connecting", f"Connecting to {network['ssid']}...\nPlease wait...", wait=False)
            if connect_to_wifi(profile["ssid"], profile["password"], profile["security"]):
                # Verify actual connection
                ui.show_message("Connecting", f"Verifying connection...", wait=False)
                if verify_connection(profile["ssid"], timeout=10):
                    data["last_connected"] = profile["ssid"]
                    save_profiles(data)
                    ui.show_message("Success", f"Connected to {network['ssid']}")
                else:
                    data["last_connected"] = profile["ssid"]
                    save_profiles(data)
                    ui.show_message("Info", f"Config saved for {network['ssid']}\nConnection established. ")
            else:
                ui.show_message("Error", "Failed to set config")

            return profile

        elif button & Pager.BTN_B:  # RED - back
            pager.beep(400, 50)
            return None


def profiles_screen(ui, pager, data):
    """Screen for managing WiFi profiles."""
    while True:
        profiles = data.get("profiles", [])

        # Build menu items
        items = []
        for p in profiles:
            security_badge = f"[{p.get('security', 'open').upper()}]"
            items.append(f"{p['ssid']} {security_badge}")
        items.append("+ Scan Networks")
        items.append("+ Add Manually")

        selected = 0

        while True:
            ssid, signal = get_current_wifi_status()

            pager.clear(COLOR_BG)
            ui.draw_header("WiFi Profiles", ssid, signal)

            if items:
                ui.draw_menu(items, selected)
            else:
                pager.draw_text_centered(100, "No profiles saved", COLOR_TEXT_DIM, 1)

            ui.draw_legend()
            pager.flip()

            button = pager.wait_button()

            if button & Pager.BTN_UP:
                selected = max(0, selected - 1)
                pager.beep(600, 30)

            elif button & Pager.BTN_DOWN:
                selected = min(len(items) - 1, selected + 1)
                pager.beep(600, 30)

            elif button & Pager.BTN_A:  # GREEN - select/connect
                pager.beep(800, 50)

                if selected == len(items) - 2:
                    # Scan for networks
                    scan_screen(ui, pager, data)
                    break  # Refresh list
                elif selected == len(items) - 1:
                    # Add new profile manually
                    new_profile = add_profile_screen(ui, pager)
                    if new_profile:
                        data["profiles"].append(new_profile)
                        save_profiles(data)
                    break  # Refresh list
                else:
                    # Connect to selected profile
                    profile = profiles[selected]
                    ui.show_message("Connecting", f"Connecting to {profile['ssid']}...\nPlease wait...", wait=False)

                    if connect_to_wifi(profile["ssid"], profile.get("password", ""), profile.get("security", "open")):
                        # Verify actual connection
                        ui.show_message("Connecting", f"Verifying connection...", wait=False)
                        if verify_connection(profile["ssid"], timeout=10):
                            data["last_connected"] = profile["ssid"]
                            save_profiles(data)
                            ui.show_message("Success", f"Connected to {profile['ssid']}")
                        else:
                            # Config set but not connected yet - still save as it may connect
                            data["last_connected"] = profile["ssid"]
                            save_profiles(data)
                            ui.show_message("Info", f"Config saved for {profile['ssid']}\nConnection pending...")
                    else:
                        ui.show_message("Error", "Failed to set config")

            elif button & Pager.BTN_B:  # RED - back
                pager.beep(400, 50)
                return

            elif button & Pager.BTN_RIGHT:  # Edit/Delete menu
                if selected < len(profiles):
                    profile = profiles[selected]
                    action = profile_action_menu(ui, pager, profile)

                    if action == "delete":
                        profiles.pop(selected)
                        save_profiles(data)
                        break  # Refresh list
                    elif action == "edit":
                        # Edit profile
                        new_profile = edit_profile_screen(ui, pager, profile)
                        if new_profile:
                            profiles[selected] = new_profile
                            save_profiles(data)
                        break  # Refresh list


def profile_action_menu(ui, pager, profile):
    """Show action menu for a profile (edit/delete)."""
    items = ["Connect", "Edit", "Delete", "Cancel"]
    selected = 0

    while True:
        pager.clear(COLOR_BG)
        ui.draw_header(profile["ssid"])
        ui.draw_menu(items, selected)
        ui.draw_legend()
        pager.flip()

        button = pager.wait_button()

        if button & Pager.BTN_UP:
            selected = max(0, selected - 1)
            pager.beep(600, 30)

        elif button & Pager.BTN_DOWN:
            selected = min(len(items) - 1, selected + 1)
            pager.beep(600, 30)

        elif button & Pager.BTN_A:
            pager.beep(800, 50)
            if items[selected] == "Connect":
                return "connect"
            elif items[selected] == "Edit":
                return "edit"
            elif items[selected] == "Delete":
                # Confirm deletion
                pager.clear(COLOR_BG)
                ui.draw_dialog("Confirm Delete", f"Delete {profile['ssid']}?", ["GREEN=Yes", "RED=No"])
                pager.flip()

                while True:
                    btn = pager.wait_button()
                    if btn & Pager.BTN_A:
                        return "delete"
                    elif btn & Pager.BTN_B:
                        break
                return None
            else:
                return None

        elif button & Pager.BTN_B:
            pager.beep(400, 50)
            return None


def edit_profile_screen(ui, pager, profile):
    """Screen for editing an existing profile."""
    # Edit SSID
    ssid = keyboard_input(ui, pager, "Edit SSID", profile.get("ssid", ""))
    if ssid is None:
        return None
    if ssid == "":
        ssid = profile.get("ssid", "")  # Keep original if empty

    # Edit security type
    security = select_security(ui, pager, profile.get("security", "wpa2"))
    if security is None:
        return None

    # Edit password if needed
    password = ""
    if security != "open":
        password = keyboard_input(ui, pager, "Edit Password", profile.get("password", ""))
        if password is None:
            return None

    return {
        "ssid": ssid,
        "security": security,
        "password": password
    }


# ============================================================
# MAIN MENU
# ============================================================

def main_menu(ui, pager, data):
    """Main menu of WiFMan."""
    selected = 0

    while True:
        ssid, signal = get_current_wifi_status()
        is_connected = ssid is not None
        last_profile = data.get("last_connected")

        # Build menu items
        items = [
            {"text": "1. Profiles", "disabled": False},
            {"text": f"2. Connect Last ({last_profile})" if last_profile else "2. Connect Last (none)",
             "disabled": not last_profile},
            {"text": "3. Disconnect", "disabled": not is_connected},
            {"text": "4. Exit", "disabled": False},
        ]

        pager.clear(COLOR_BG)
        ui.draw_header("WiFMan", ssid, signal)
        ui.draw_menu([item["text"] for item in items], selected, item_height=32)
        ui.draw_legend()
        pager.flip()

        button = pager.wait_button()

        if button & Pager.BTN_UP:
            selected = max(0, selected - 1)
            pager.beep(600, 30)

        elif button & Pager.BTN_DOWN:
            selected = min(len(items) - 1, selected + 1)
            pager.beep(600, 30)

        elif button & Pager.BTN_A:  # GREEN - select
            item = items[selected]

            if item["disabled"]:
                pager.beep(300, 100)
                continue

            pager.beep(800, 50)

            if selected == 0:  # Profiles
                profiles_screen(ui, pager, data)

            elif selected == 1:  # Connect Last
                if last_profile:
                    # Find the profile
                    profile = None
                    for p in data.get("profiles", []):
                        if p["ssid"] == last_profile:
                            profile = p
                            break

                    if profile:
                        ui.show_message("Connecting", f"Connecting to {profile['ssid']}...\nPlease wait...", wait=False)
                        if connect_to_wifi(profile["ssid"], profile.get("password", ""), profile.get("security", "open")):
                            ui.show_message("Connecting", f"Verifying connection...", wait=False)
                            if verify_connection(profile["ssid"], timeout=10):
                                ui.show_message("Success", f"Connected to {profile['ssid']}")
                            else:
                                ui.show_message("Info", f"Config saved\nConnection pending...")
                        else:
                            ui.show_message("Error", "Failed to set config")
                    else:
                        ui.show_message("Error", "Profile not found")

            elif selected == 2:  # Disconnect
                ui.show_message("Disconnecting", "Disconnecting from WiFi...", wait=False)
                if disconnect_wifi():
                    pager.delay(2000)
                    ui.show_message("Success", "Disconnected from WiFi")
                else:
                    ui.show_message("Error", "Failed to disconnect")

            elif selected == 3:  # Exit
                return

        elif button & Pager.BTN_B:  # RED - exit
            pager.beep(400, 50)
            return


# ============================================================
# MAIN
# ============================================================

def show_error_screen(pager, error_msg):
    """Show error message on screen and wait for button."""
    try:
        pager.clear(Pager.BLACK)
        pager.draw_text_centered(30, "ERROR", Pager.RED, 2)

        # Split error message into lines
        lines = str(error_msg)[:200].split('\n')
        y = 70
        for line in lines[:5]:
            # Truncate long lines
            if len(line) > 50:
                line = line[:47] + "..."
            pager.draw_text_centered(y, line, Pager.WHITE, 1)
            y += 20

        pager.draw_text_centered(200, "Press any button to exit", Pager.GRAY, 1)
        pager.flip()
        pager.wait_button()
    except:
        pass


def main():
    """Main entry point for WiFMan.

    Uses explicit Pager lifecycle (like pagergotchi) to ensure proper
    cleanup and prevent GUI reset issues.
    """
    pager = None

    try:
        # Initialize Pager explicitly (not via context manager)
        pager = Pager()
        pager.init()
        pager.set_rotation(270)  # Landscape mode

        # Initialize UI
        ui = WiFManUI(pager)

        # Load profiles (with error handling)
        try:
            data = load_profiles()
        except Exception as e:
            # If profiles.json is corrupt, reset it
            data = {"profiles": [], "last_connected": None}
            save_profiles(data)

        # Show splash screen
        pager.clear(COLOR_BG)
        pager.draw_text_centered(60, "WiFMan by LAB5", Pager.CYAN, 3)
        pager.draw_text_centered(110, "WiFi Network Manager", Pager.WHITE, 1)
        pager.draw_text_centered(140, "v1.0", Pager.GRAY, 1)
        pager.flip()
        pager.beep(800, 100)
        pager.delay(50)
        pager.beep(1000, 100)
        pager.delay(1500)

        # Run main menu
        main_menu(ui, pager, data)

        # Exit screen
        pager.clear(Pager.BLACK)
        pager.draw_text_centered(100, "Goodbye!", Pager.GREEN, 2)
        pager.flip()
        pager.beep(500, 100)
        pager.delay(1000)
        pager.clear(Pager.BLACK)
        pager.flip()

    except Exception as e:
        # Show error on screen if possible
        if pager:
            show_error_screen(pager, str(e))
        # Also print to stderr for logs
        import traceback
        traceback.print_exc()

    finally:
        # Explicit cleanup (like pagergotchi) - critical for proper FB release
        if pager:
            pager.cleanup()


if __name__ == "__main__":
    main()
