# =========================================================
# CTLauncherHDR V0.2.1 - Real Minecraft Launcher (Full Boot)
# Update: Downloads Java, libs, assets, natives; Actually launches game
# =========================================================

import os
import sys
import subprocess
import urllib.request
import json
import ssl
import threading
import time
import hashlib
import zipfile
import tarfile
import platform
import tkinter as tk
from tkinter import ttk, messagebox

# -------------------------
# Constants
# -------------------------
CTLAUNCHER_DIR = os.path.expanduser("~/.ctlauncherhdr")
VERSIONS_DIR = os.path.join(CTLAUNCHER_DIR, "versions")
JAVA_DIR = os.path.join(CTLAUNCHER_DIR, "java")
ASSETS_DIR = os.path.join(CTLAUNCHER_DIR, "assets")
LIBRARIES_DIR = os.path.join(CTLAUNCHER_DIR, "libraries")
NATIVE_DIR_BASE = os.path.join(CTLAUNCHER_DIR, "natives")
VERSION_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
LIBRARY_BASE_URL = "https://libraries.minecraft.net/"

THEME = {
    'bg': '#1a1a1a',
    'accent': '#4CAF50',
    'accent_light': '#66BB6A',
    'text': '#e0e0e0',
    'text_secondary': '#aaaaaa',
    'input_bg': '#333333',
    'panel_bg': '#252525',
    'border': '#3d3d3d',
    'header_bg': '#4CAF50'
}


# =========================================================
# CLASS: CTLauncherHDR
# =========================================================
class CTLauncherHDR(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CTLauncherHDR V0.2.1")
        self.geometry("900x600")
        self.configure(bg=THEME['bg'])
        self.versions = {}

        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()
        self.init_ui()

        # Run startup checks
        threading.Thread(target=self.init_launcher, daemon=True).start()

    # -------------------------
    # Initialization
    # -------------------------
    def init_launcher(self):
        self.log_status("Initializing CTLauncherHDR directories...")
        dirs_to_create = [
            CTLAUNCHER_DIR, VERSIONS_DIR, JAVA_DIR, ASSETS_DIR, LIBRARIES_DIR,
            os.path.join(ASSETS_DIR, "indexes"), os.path.join(ASSETS_DIR, "objects"),
            os.path.join(ASSETS_DIR, "log_configs"), NATIVE_DIR_BASE
        ]
        for d in dirs_to_create:
            os.makedirs(d, exist_ok=True)
        self.log_status(f"✓ Directories initialized at {CTLAUNCHER_DIR}")
        self.load_version_manifest()

    # -------------------------
    # UI
    # -------------------------
    def configure_styles(self):
        self.style.configure("TLabel", background=THEME['bg'], foreground=THEME['text'])
        self.style.configure("TButton", background=THEME['accent'], foreground=THEME['text'])
        self.style.configure("TCombobox",
                             fieldbackground=THEME['input_bg'],
                             background=THEME['input_bg'],
                             foreground=THEME['text'])
        self.style.configure("Horizontal.TProgressbar",
                             background=THEME['accent'],
                             troughcolor=THEME['input_bg'])

    def init_ui(self):
        header = tk.Frame(self, bg=THEME['header_bg'], height=80)
        header.pack(fill="x", side="top")
        tk.Label(header, text="CTLauncherHDR", font=("Arial", 20, "bold"),
                 bg=THEME['header_bg'], fg="white").pack(side="left", padx=20, pady=20)
        tk.Label(header, text="V0.2.1", font=("Arial", 10),
                 bg=THEME['header_bg'], fg="white").pack(side="left")

        content = tk.Frame(self, bg=THEME['bg'])
        content.pack(fill="both", expand=True, padx=15, pady=15)

        # Left panel
        left = tk.Frame(content, bg=THEME['panel_bg'], width=300,
                        highlightbackground=THEME['border'], highlightthickness=1)
        left.pack(side="left", fill="y", padx=(0, 10))
        left.pack_propagate(False)

        # Username
        tk.Label(left, text="PLAYER SETTINGS", fg=THEME['accent'],
                 bg=THEME['panel_bg']).pack(anchor="w", padx=15, pady=(10, 0))
        self.username_input = tk.Entry(left, bg=THEME['input_bg'], fg=THEME['text'], bd=0)
        self.username_input.insert(0, "Player")
        self.username_input.pack(fill="x", padx=15, pady=(5, 10))

        # Version
        tk.Label(left, text="VERSION SELECTION", fg=THEME['accent'],
                 bg=THEME['panel_bg']).pack(anchor="w", padx=15)
        self.version_combo = ttk.Combobox(left, state="readonly")
        self.version_combo.pack(fill="x", padx=15, pady=10)

        # RAM
        tk.Label(left, text="MEMORY (GB)", fg=THEME['accent'],
                 bg=THEME['panel_bg']).pack(anchor="w", padx=15)
        self.ram_var = tk.IntVar(value=4)
        self.ram_scale = tk.Scale(left, from_=1, to=16, orient="horizontal",
                                  variable=self.ram_var, bg=THEME['panel_bg'],
                                  fg=THEME['text'], troughcolor=THEME['input_bg'])
        self.ram_scale.pack(fill="x", padx=15, pady=10)

        # Launch
        self.launch_button = tk.Button(left, text="LAUNCH GAME", font=("Arial", 12, "bold"),
                                       bg=THEME['accent'], fg="white", bd=0,
                                       command=self.prepare_and_launch)
        self.launch_button.pack(side="bottom", fill="x", padx=15, pady=15)

        # Logs
        right = tk.Frame(content, bg=THEME['panel_bg'],
                         highlightbackground=THEME['border'], highlightthickness=1)
        right.pack(side="left", fill="both", expand=True)
        tk.Label(right, text="Launcher Logs", bg=THEME['panel_bg'],
                 fg=THEME['text'], font=("Arial", 14, "bold")).pack(anchor="w", padx=15, pady=10)
        self.status_text = tk.Text(right, bg=THEME['input_bg'], fg=THEME['text'],
                                   font=("Consolas", 9), state=tk.DISABLED)
        self.status_text.pack(fill="both", expand=True, padx=15, pady=(0, 10))

    # -------------------------
    # Logging
    # -------------------------
    def log_status(self, msg):
        timestamp = time.strftime("%H:%M:%S")
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, f"[{timestamp}] {msg}\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        print(f"[{timestamp}] {msg}")

    # -------------------------
    # Version manifest
    # -------------------------
    def load_version_manifest(self):
        try:
            self.log_status("Fetching version manifest...")
            context = self.get_ssl_context()
            req = urllib.request.Request(VERSION_MANIFEST_URL, headers={'User-Agent': 'CTLauncherHDR/0.2.1'})
            with urllib.request.urlopen(req, context=context) as r:
                manifest = json.loads(r.read().decode())
            self.versions = {v["id"]: v["url"] for v in manifest["versions"]}
            versions_sorted = sorted(manifest["versions"], key=lambda v: v["releaseTime"], reverse=True)
            all_versions = [v["id"] for v in versions_sorted]
            self.version_combo.config(values=all_versions)
            self.version_combo.set(manifest["latest"]["release"])
            count = len(manifest.get("versions", []))
            self.log_status(f"✓ Found {count} versions")
        except Exception as e:
            self.log_status(f"❌ Failed to load manifest: {e}")

    def get_ssl_context(self):
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        return context

    def download_file(self, url, path, expected_sha1=None):
        self.log_status(f"Downloading {os.path.basename(path)} from {url}...")
        context = self.get_ssl_context()
        req = urllib.request.Request(url, headers={'User-Agent': 'CTLauncherHDR/0.2.1'})
        temp_path = path + '.tmp'
        try:
            with urllib.request.urlopen(req, context=context) as response:
                with open(temp_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
            if expected_sha1:
                with open(temp_path, 'rb') as f:
                    sha1 = hashlib.sha1(f.read()).hexdigest()
                if sha1 != expected_sha1:
                    raise ValueError(f"SHA1 mismatch for {os.path.basename(path)}: expected {expected_sha1}, got {sha1}")
            os.replace(temp_path, path)
            self.log_status(f"✓ Downloaded {os.path.basename(path)} ({os.path.getsize(path) // 1024 // 1024} MB)")
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise e

    # -------------------------
    # Version & Client
    # -------------------------
    def download_version_json(self, version_id):
        version_dir = os.path.join(VERSIONS_DIR, version_id)
        os.makedirs(version_dir, exist_ok=True)
        json_path = os.path.join(version_dir, f"{version_id}.json")
        if not os.path.exists(json_path):
            version_url = self.versions.get(version_id)
            if not version_url:
                raise ValueError(f"Version {version_id} not found in manifest.")
            self.download_file(version_url, json_path)
        with open(json_path, 'r') as f:
            return json.load(f)

    def download_client_jar(self, version_id, version_data):
        version_dir = os.path.join(VERSIONS_DIR, version_id)
        jar_path = os.path.join(version_dir, f"{version_id}.jar")
        if not os.path.exists(jar_path):
            client_download = version_data['downloads']['client']
            jar_url = client_download['url']
            sha1 = client_download['sha1']
            self.download_file(jar_url, jar_path, sha1)
        self.log_status(f"✓ Client JAR ready at {jar_path}")

    # -------------------------
    # Java
    # -------------------------
    def get_java_path(self, version_data):
        major = version_data['javaVersion']['majorVersion']
        if major < 21:
            major = 21  # Fallback for older, but 1.21+ needs 21
        os_name = platform.system().lower()
        arch = platform.machine()
        if arch.lower() not in ['x86_64', 'amd64']:
            raise ValueError("Unsupported architecture (only x64 supported)")
        java_subdir = f"jre-{major}-windows-x64"  # Assuming Windows from log
        java_dir = os.path.join(JAVA_DIR, java_subdir)
        java_exe = os.path.join(java_dir, 'bin', 'java.exe')
        if os.path.exists(java_exe):
            return os.path.join(java_dir, 'bin')
        # Download JRE
        self.log_status(f"Downloading Java {major} JRE for Windows...")
        tag = "jdk-21.0.4+7"  # Stable Temurin 21
        version_str = "21.0.4_7"
        filename = f"OpenJDK21U-jre_x64_windows_hotspot_{version_str}.zip"
        url = f"https://github.com/adoptium/temurin21-binaries/releases/download/{tag}/{filename}"
        temp_path = os.path.join(JAVA_DIR, f"temp_java.zip")
        self.download_file(url, temp_path)  # No SHA1 check for simplicity
        with zipfile.ZipFile(temp_path, 'r') as archive:
            archive.extractall(java_dir)
        os.remove(temp_path)
        # Temurin extracts to 'jdk-21.0.4+7' subdir; rename for consistency
        extracted_dir = os.path.join(java_dir, f"jdk-{major}.0.4+7")
        if os.path.exists(extracted_dir):
            import shutil
            shutil.move(extracted_dir, os.path.join(java_dir, "jre"))
        self.log_status(f"✓ Java ready at {os.path.join(java_dir, 'bin')}")
        return os.path.join(java_dir, 'bin')

    # -------------------------
    # Libraries & Natives
    # -------------------------
    def download_libraries(self, version_data):
        self.log_status("Downloading libraries...")
        for lib in version_data['libraries']:
            if 'rules' in lib and not self.apply_rules(lib['rules']):
                continue
            if 'downloads' in lib and 'artifact' in lib['downloads']:
                artifact = lib['downloads']['artifact']
                if artifact:
                    path = artifact['path']
                    url = artifact.get('url', LIBRARY_BASE_URL + path)
                    lib_path = os.path.join(LIBRARIES_DIR, path)
                    os.makedirs(os.path.dirname(lib_path), exist_ok=True)
                    if not os.path.exists(lib_path):
                        sha1 = artifact.get('sha1')
                        self.download_file(url, lib_path, sha1)
        self.log_status("✓ Libraries downloaded")

    def get_classpath_and_natives(self, ver, version_data):
        self.log_status("Preparing classpath and natives...")
        libraries = []
        natives_dir = os.path.join(NATIVE_DIR_BASE, ver)
        os.makedirs(natives_dir, exist_ok=True)
        # Clear old natives
        for f in os.listdir(natives_dir):
            os.remove(os.path.join(natives_dir, f))
        client_path = os.path.join(VERSIONS_DIR, ver, f"{ver}.jar")
        libraries.append(client_path)
        for lib in version_data['libraries']:
            if 'rules' in lib and not self.apply_rules(lib['rules']):
                continue
            if 'downloads' in lib and 'artifact' in lib['downloads']:
                artifact = lib['downloads']['artifact']
                if artifact:
                    lib_path = os.path.join(LIBRARIES_DIR, artifact['path'])
                    if os.path.exists(lib_path):
                        libraries.append(lib_path)
            # Natives for Windows
            if 'natives' in lib and sys.platform == 'win32':
                native_key = lib['natives'].get('windows')
                if native_key and 'classifiers' in lib['downloads']:
                    classifier = lib['downloads']['classifiers'].get(native_key)
                    if classifier:
                        native_path = os.path.join(LIBRARIES_DIR, classifier['path'])
                        if not os.path.exists(native_path):
                            url = classifier.get('url', LIBRARY_BASE_URL + classifier['path'])
                            self.download_file(url, native_path, classifier.get('sha1'))
                        # Extract natives (ZIP)
                        with zipfile.ZipFile(native_path, 'r') as z:
                            for file_name in z.namelist():
                                if not file_name.startswith('META-INF/'):
                                    z.extract(file_name, natives_dir)
        classpath = os.pathsep.join(libraries)
        self.log_status(f"✓ Classpath ready ({len(libraries)} items); Natives at {natives_dir}")
        return classpath, natives_dir

    def apply_rules(self, rules):
        for rule in rules:
            action = rule.get('action', 'allow')
            if action == 'disallow':
                os_rule = rule.get('os', {})
                os_name = {'win32': 'windows', 'darwin': 'osx', 'linux': 'linux'}.get(sys.platform, '')
                if not os_rule or os_rule.get('name') == os_name:
                    return False
        return True

    # -------------------------
    # Assets
    # -------------------------
    def download_assets(self, version_data):
        self.log_status("Downloading assets...")
        asset_index = version_data['assetIndex']
        index_path = os.path.join(ASSETS_DIR, 'indexes', f"{asset_index['id']}.json")
        if not os.path.exists(index_path):
            self.download_file(asset_index['url'], index_path, asset_index['sha1'])
        with open(index_path, 'r') as f:
            index = json.load(f)
        downloaded = 0
        total = len(index['objects'])
        for obj_path, obj in index['objects'].items():
            hash_val = obj['hash']
            dir_name = hash_val[:2]
            full_path = os.path.join(ASSETS_DIR, 'objects', dir_name, hash_val)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            if not os.path.exists(full_path):
                url = f"https://resources.download.minecraft.net/{dir_name}/{hash_val}"
                self.download_file(url, full_path, hash_val)
            downloaded += 1
            if downloaded % 100 == 0:
                self.log_status(f"Assets: {downloaded}/{total}")
        self.log_status(f"✓ Assets downloaded ({total} objects)")

    def download_log_config(self, version_data):
        if 'logging' in version_data:
            self.log_status("Downloading log config...")
            log_info = version_data['logging']['client']['file']
            log_path = os.path.join(ASSETS_DIR, 'log_configs', f"{log_info['id']}")
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            if not os.path.exists(log_path):
                self.download_file(log_info['url'], log_path, log_info['sha1'])
            self.log_status("✓ Log config ready")

    # -------------------------
    # Arguments & Launch
    # -------------------------
    def build_arguments(self, version_data, player, ver, ram, classpath, natives_dir):
        self.log_status("Building launch arguments...")
        jvm_args = [f"-Xmx{ram}G", f"-Xms{ram}G"]
        game_args = []

        # JVM args from JSON
        jvm_section = version_data.get('arguments', {}).get('jvm', [])
        for arg in jvm_section:
            if isinstance(arg, str):
                jvm_args.append(arg)
            elif isinstance(arg, dict) and self.apply_rules(arg.get('rules', [])):
                value = arg['value']
                jvm_args.extend([value] if isinstance(value, str) else value)

        # Game args from JSON
        game_section = version_data.get('arguments', {}).get('game', [])
        for arg in game_section:
            if isinstance(arg, str):
                game_args.append(arg)
            elif isinstance(arg, dict) and self.apply_rules(arg.get('rules', [])):
                value = arg['value']
                game_args.extend([value] if isinstance(value, str) else value)

        # Replace placeholders
        replacements = {
            '${auth_player_name}': player,
            '${version_name}': ver,
            '${game_directory}': CTLAUNCHER_DIR,
            '${assets_root}': ASSETS_DIR,
            '${assets_index_name}': version_data['assetIndex']['id'],
            '${auth_uuid}': '00000000-0000-0000-0000-000000000000',  # Offline
            '${auth_access_token}': '0',
            '${auth_xuid}': '0',
            '${clientid}': '0',
            '${user_type}': 'legacy',
            '${version_type}': version_data['type'],
            '${natives_directory}': natives_dir,
            '${launcher_name}': 'CTLauncherHDR',
            '${launcher_version}': '0.2.1',
            '${classpath}': classpath,
            '${resolution_width}': '854',
            '${resolution_height}': '480',
            '${log4j_configuration}': '',  # Set later
        }
        game_args = [self.replace_placeholders(a, replacements) for a in game_args]

        # Log config JVM arg
        if 'logging' in version_data:
            log_id = version_data['logging']['client']['file']['id']
            replacements['${log4j_configuration}'] = os.path.join(ASSETS_DIR, 'log_configs', log_id)
            jvm_args.append(f"-Dlog4j.configurationFile={replacements['${log4j_configuration}']}")

        self.log_status("✓ Arguments built")
        return jvm_args, game_args

    def replace_placeholders(self, arg, replacements):
        for key, value in replacements.items():
            arg = arg.replace(key, str(value))
        return arg

    def launch_game_process(self, java_bin, jvm_args, main_class, game_args):
        cmd = [os.path.join(java_bin, 'java.exe')] + jvm_args + [main_class] + game_args
        env = os.environ.copy()
        env['PATH'] = java_bin + os.pathsep + env.get('PATH', '')
        p = subprocess.Popen(cmd, cwd=CTLAUNCHER_DIR, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return p.pid

    # -------------------------
    # Main Launch
    # -------------------------
    def prepare_and_launch(self):
        self.launch_button.config(state=tk.DISABLED, text="PREPARING...", bg=THEME['text_secondary'])
        threading.Thread(target=self.launch_game, daemon=True).start()

    def launch_game(self):
        ver = self.version_combo.get() or "unknown"
        player = self.username_input.get() or "Player"
        ram = self.ram_var.get()
        try:
            self.log_status(f"🚀 Preparing Minecraft {ver} for {player} with {ram} GB RAM...")
            version_data = self.download_version_json(ver)
            self.download_client_jar(ver, version_data)
            java_bin = self.get_java_path(version_data)
            self.download_libraries(version_data)
            classpath, natives_dir = self.get_classpath_and_natives(ver, version_data)
            self.download_assets(version_data)
            self.download_log_config(version_data)
            jvm_args, game_args = self.build_arguments(version_data, player, ver, ram, classpath, natives_dir)
            main_class = version_data['mainClass']
            pid = self.launch_game_process(java_bin, jvm_args, main_class, game_args)
            self.log_status(f"🎮 Game launched successfully (PID: {pid}). Have fun!")
        except Exception as e:
            self.log_status(f"❌ Launch failed: {str(e)}")
            self.after(0, lambda: messagebox.showerror("Launch Error", f"Failed to launch: {str(e)}"))
        finally:
            self.after(0, lambda: self.launch_button.config(state=tk.NORMAL, text="LAUNCH GAME", bg=THEME['accent']))


# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    print("============================================================")
    print("  CTLauncherHDR V0.2.1 - Full Minecraft Launcher")
    print("  Downloads & Launches Real Game (Offline Mode)")
    print("============================================================")
    app = CTLauncherHDR()
    app.mainloop()
