import os
import sys
import subprocess
import platform
import urllib.request
import zipfile
import json
import shutil
import re
import hashlib
import ssl
import time
import requests
import threading
import tarfile  # For Linux/macOS extraction
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext, simpledialog
from concurrent.futures import ThreadPoolExecutor, as_completed

# -------------------------
# Constants / Directories
# -------------------------
CTLAUNCHER_DIR = os.path.expanduser("~/.ctlauncher")
VERSIONS_DIR = os.path.join(CTLAUNCHER_DIR, "versions")
JAVA_DIR = os.path.join(CTLAUNCHER_DIR, "java")
ASSETS_DIR = os.path.join(CTLAUNCHER_DIR, "assets")
LIBRARIES_DIR = os.path.join(CTLAUNCHER_DIR, "libraries")
PROFILES_DIR = os.path.join(CTLAUNCHER_DIR, "profiles")
VERSION_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
ASSETS_BASE_URL = "https://resources.download.minecraft.net"

# Modloader URLs (dynamic fetch in code)
FORGE_MAVEN = "https://files.minecraftforge.net/maven/net/minecraftforge/forge/"
FABRIC_INSTALLER_URL = "https://maven.fabricmc.net/net/fabricmc/fabric-installer/1.0.1/fabric-installer-1.0.1.jar"  # Universal

# -------------------------
# Meta
# -------------------------
LAUNCHER_VERSION = "V0.5.1 Enhanced TLauncher-Like Cracked Edition (2025 Optimized - No Malware)"
MAX_RETRIES = 3
RETRY_DELAY = 1
DOWNLOAD_TIMEOUT = 30
MAX_WORKERS = 4
CACHE_SIZE = 100  # From optimized version

THEME = {
    'bg': '#ffffff',          # White background
    'sidebar': '#f8f9fa',     # Light gray sidebar
    'accent': '#007bff',      # Blue accent (TLauncher style)
    'accent_light': '#0056b3',# Darker blue for hover/variations
    'fg': '#212529',          # Dark gray text
    'log_bg': '#ffffff',      # White log background
    'log_fg': '#495057'       # Medium gray log text
}

# ==============================================================
# Backend: MinecraftLauncher
# ==============================================================

class MinecraftLauncher:
    def __init__(self, log_callback=None):
        self.setup_directories()
        self.version_manifest = None
        self.selected_version = None
        self.profiles = self.load_profiles()
        self.log_callback = log_callback or print
        self.version_cache = {}  # Cache for version data
        self.asset_cache = {}    # Cache for assets
        self.thread_pool = ThreadPoolExecutor(max_workers=MAX_WORKERS)

    def log(self, msg):
        self.log_callback(msg)

    def setup_directories(self):
        for directory in [CTLAUNCHER_DIR, VERSIONS_DIR, JAVA_DIR, ASSETS_DIR, LIBRARIES_DIR, PROFILES_DIR]:
            os.makedirs(directory, exist_ok=True)

    def get_java_path(self):
        system = platform.system()
        local_java_dir = self.get_local_java_dir()
        if local_java_dir:
            if system == 'Windows':
                java_bin = os.path.join(JAVA_DIR, local_java_dir, "bin", "java.exe")
            else:
                java_bin = os.path.join(JAVA_DIR, local_java_dir, "bin", "java")
            if os.path.exists(java_bin):
                return java_bin
        # Fallback to system java
        return 'java'

    def get_local_java_dir(self):
        """Find extracted Java directory."""
        if not os.path.exists(JAVA_DIR):
            return None
        for dir_name in os.listdir(JAVA_DIR):
            if dir_name.startswith("jdk-") and os.path.isdir(os.path.join(JAVA_DIR, dir_name)):
                return dir_name
        return None

    def get_latest_java_url(self):
        """Fetch latest OpenJDK URL dynamically."""
        try:
            response = requests.get("https://api.adoptium.net/v3/assets/latest/21/hotspot", timeout=10)
            response.raise_for_status()
            releases = response.json()
            system = platform.system()
            arch = "x64"
            os_map = {"Windows": "windows", "Linux": "linux", "Darwin": "mac"}
            os_name = os_map.get(system)
            if not os_name:
                return None, None
            for release in releases:
                if release["binary"]["os"] == os_name and release["binary"]["architecture"] == arch:
                    return release["binary"]["package"]["link"], release["version"]["openjdk_version"]
            return None, None
        except Exception as e:
            self.log(f"✗ Failed to fetch Java: {e}")
            return None, None

    def download_java(self):
        system = platform.system()
        if system not in ['Windows', 'Linux', 'Darwin']:
            self.log(f"✗ Unsupported OS: {system}")
            return False

        java_url, java_version = self.get_latest_java_url()
        if not java_url:
            self.log("✗ Failed to fetch Java URL")
            return False

        self.log(f"Downloading Java {java_version} for {system}...")
        archive_ext = 'zip' if system == 'Windows' else 'tar.gz'
        archive_path = os.path.join(JAVA_DIR, f"java_{java_version}_{system.lower()}.{archive_ext}")

        if not self.download_file(java_url, archive_path, f"Java {java_version}"):
            return False

        try:
            if system == 'Windows':
                with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                    zip_ref.extractall(JAVA_DIR)
            else:
                with tarfile.open(archive_path, 'r:gz') as tar_ref:
                    tar_ref.extractall(JAVA_DIR)
            os.remove(archive_path)
            self.log(f"✓ Java {java_version} downloaded and extracted")
            return True
        except Exception as e:
            self.log(f"✗ Failed to extract Java: {e}")
            return False

    def check_java(self):
        java_path = self.get_java_path()
        try:
            result = subprocess.run([java_path, '-version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and '21.' in result.stderr:
                self.log("✓ Compatible Java 21 is available")
                return True
            else:
                self.log("⚠ System Java is not version 21; attempting to use bundled or download")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Download if bundled not present
        local_java_dir = self.get_local_java_dir()
        if not local_java_dir:
            if not self.download_java():
                self.log("✗ Failed to download Java 21. Please install manually from https://adoptium.net/")
                return False

        # Recheck
        java_path = self.get_java_path()
        try:
            result = subprocess.run([java_path, '-version'], capture_output=True, text=True, timeout=10)
            if result.returncode == 0 and '21.' in result.stderr:
                self.log("✓ Bundled Java 21 is ready")
                return True
        except Exception as e:
            self.log(f"✗ Java check failed: {e}")
            return False
        return False

    def fetch_version_manifest(self):
        try:
            self.log("Fetching version manifest...")
            response = requests.get(VERSION_MANIFEST_URL, timeout=DOWNLOAD_TIMEOUT)
            response.raise_for_status()
            self.version_manifest = response.json()
            self.log(f"✓ Found {len(self.version_manifest['versions'])} versions")
            return True
        except Exception as e:
            self.log(f"✗ Failed to fetch version manifest: {e}")
            return False

    def download_file(self, url, destination, description="file", expected_hash=None):
        for attempt in range(MAX_RETRIES):
            try:
                self.log(f"Downloading {description}... (attempt {attempt + 1}/{MAX_RETRIES})")
                response = requests.get(url, timeout=DOWNLOAD_TIMEOUT, stream=True)
                response.raise_for_status()

                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                with open(destination, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0 and downloaded % (1024 * 1024) == 0:  # Update every MB
                                progress = (downloaded / total_size) * 100
                                self.log(f"  Progress: {progress:.1f}%")
                # Verify hash if provided
                if expected_hash:
                    file_hash = hashlib.sha1(open(destination, 'rb').read()).hexdigest()
                    if file_hash != expected_hash:
                        self.log(f"✗ Hash mismatch for {description}: expected {expected_hash}, got {file_hash}")
                        os.remove(destination)
                        continue
                self.log(f"✓ Downloaded {description}")
                return True
            except Exception as e:
                self.log(f"✗ Download failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if os.path.exists(destination):
                    os.remove(destination)
                if attempt < MAX_RETRIES - 1:
                    time.sleep(RETRY_DELAY * (2 ** attempt))  # Exponential backoff
        return False

    def download_version(self, version_id):
        self.log(f"\n=== Downloading Minecraft {version_id} ===")

        version_info = next((v for v in self.version_manifest['versions'] if v['id'] == version_id), None)
        if not version_info:
            self.log(f"✗ Version {version_id} not found in manifest")
            return False

        version_dir = os.path.join(VERSIONS_DIR, version_id)
        os.makedirs(version_dir, exist_ok=True)

        version_json_path = os.path.join(version_dir, f"{version_id}.json")
        if version_id in self.version_cache:
            with open(version_json_path, 'w') as f:
                json.dump(self.version_cache[version_id], f)
        else:
            if not self.download_file(version_info['url'], version_json_path, f"{version_id}.json"):
                return False
            with open(version_json_path, 'r') as f:
                version_data = json.load(f)
            self.version_cache[version_id] = version_data
            if len(self.version_cache) > CACHE_SIZE:
                self.version_cache.pop(next(iter(self.version_cache)))

        version_data = self.version_cache[version_id]

        client_jar_path = os.path.join(version_dir, f"{version_id}.jar")
        if not self.download_file(version_data['downloads']['client']['url'], client_jar_path, f"minecraft.jar ({version_id})", version_data['downloads']['client']['sha1']):
            return False

        self.download_libraries(version_data['libraries'])
        self.download_assets(version_data['assetIndex'])

        self.selected_version = version_id
        self.log(f"✓ Minecraft {version_id} ready to launch! (Cracked Mode)")
        return True

    def download_libraries(self, libraries):
        self.log("Downloading libraries...")
        current_os = platform.system().lower()
        if current_os == 'darwin':
            current_os = 'osx'
        for lib in libraries:
            if not self.is_library_allowed(lib, current_os):
                continue
            if 'downloads' in lib and 'artifact' in lib['downloads']:
                artifact = lib['downloads']['artifact']
                lib_path = os.path.join(LIBRARIES_DIR, artifact['path'])
                os.makedirs(os.path.dirname(lib_path), exist_ok=True)
                if not os.path.exists(lib_path):
                    self.download_file(artifact['url'], lib_path, f"library: {artifact['path']}", artifact['sha1'])

    def is_library_allowed(self, lib, current_os):
        """Check if library is allowed on current OS."""
        if "rules" not in lib:
            return True
        allowed = False
        for rule in lib["rules"]:
            if rule["action"] == "allow":
                if "os" not in rule or (isinstance(rule.get("os"), dict) and rule["os"].get("name") == current_os):
                    allowed = True
            elif rule["action"] == "disallow":
                if "os" in rule and isinstance(rule.get("os"), dict) and rule["os"].get("name") == current_os:
                    allowed = False
        return allowed

    def download_assets(self, asset_index_info):
        asset_index_path = os.path.join(ASSETS_DIR, "indexes", f"{asset_index_info['id']}.json")
        os.makedirs(os.path.dirname(asset_index_path), exist_ok=True)
        if not self.download_file(asset_index_info['url'], asset_index_path, "asset index", asset_index_info['sha1']):
            return
        with open(asset_index_path, 'r') as f:
            asset_data = json.load(f)
        self.log(f"Downloading assets ({len(asset_data['objects'])} objects)...")
        objects_dir = os.path.join(ASSETS_DIR, "objects")
        os.makedirs(objects_dir, exist_ok=True)
        objects = asset_data['objects']
        total_objects = len(objects)
        downloaded = 0
        futures = []
        for obj_name, obj_info in objects.items():
            hash_val = obj_info['hash']
            obj_path = os.path.join(objects_dir, hash_val[:2], hash_val)
            os.makedirs(os.path.dirname(obj_path), exist_ok=True)
            if not os.path.exists(obj_path):
                url = f"{ASSETS_BASE_URL}/{hash_val[:2]}/{hash_val}"
                future = self.thread_pool.submit(self.download_file, url, obj_path, f"asset: {obj_name}", hash_val)
                futures.append(future)
            else:
                downloaded += 1
        for future in as_completed(futures):
            if future.result():
                downloaded += 1
            progress = (downloaded / total_objects) * 100
            self.log(f"  Assets Progress: {progress:.1f}%")
        self.log(f"✓ All assets downloaded for {asset_index_info['id']}")

    def fetch_forge_version(self, version_id):
        """Dynamically fetch latest Forge version for a MC version (TLauncher-like)."""
        try:
            response = requests.get(f"{FORGE_MAVEN}index_{version_id}.html", timeout=10)
            # Parse HTML for latest recommended version using regex
            match = re.search(rf'href="net/minecraftforge/forge/({re.escape(version_id)}-[^/]+)/"[^>]*>Recommended</a>', response.text)
            if match:
                full = match.group(1)
                forge_version = full.split('-')[-1]
                return forge_version
            # Fallback to placeholder
            self.log("⚠ Could not parse latest Forge; using placeholder")
            return "52.0.3"
        except Exception as e:
            self.log(f"✗ Error fetching Forge version: {e}")
            return "52.0.3"

    def install_forge(self, version_id):
        if not version_id:
            self.log("✗ Select a version first")
            return False
        # Dynamically fetch latest Forge (enhanced for TLauncher-like behavior)
        forge_version = self.fetch_forge_version(version_id)
        try:
            installer_url = f"https://files.minecraftforge.net/maven/net/minecraftforge/forge/{version_id}-{forge_version}/forge-{version_id}-{forge_version}-installer.jar"
            installer_path = os.path.join(VERSIONS_DIR, f"forge-installer-{version_id}.jar")
            if self.download_file(installer_url, installer_path, f"Forge installer for {version_id}"):
                version_dir = os.path.join(VERSIONS_DIR, version_id)
                java_path = self.get_java_path()
                cmd = [java_path, '-jar', installer_path, '--installClient', version_dir]
                self.log(f"Installing Forge {forge_version} for {version_id}...")
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    self.log("✓ Forge installed successfully")
                    os.remove(installer_path)
                    return True
                else:
                    self.log(f"✗ Forge install failed: {result.stderr}")
            return False
        except Exception as e:
            self.log(f"✗ Error installing Forge: {e}")
            return False

    def install_fabric(self, version_id):
        if not version_id:
            self.log("✗ Select a version first")
            return False
        installer_path = os.path.join(VERSIONS_DIR, "fabric-installer.jar")
        if self.download_file(FABRIC_INSTALLER_URL, installer_path, "Fabric installer"):
            version_dir = os.path.join(VERSIONS_DIR, version_id)
            java_path = self.get_java_path()
            cmd = [java_path, '-jar', installer_path, 'client', version_dir, '--mcversion', version_id, '--loader-version', '0.16.9']
            self.log(f"Installing Fabric for {version_id}...")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                self.log("✓ Fabric installed successfully")
                os.remove(installer_path)
                return True
            else:
                self.log(f"✗ Fabric install failed: {result.stderr}")
        return False

    def set_skin(self, username, skin_path):
        skin_dir = os.path.join(ASSETS_DIR, "skins")
        os.makedirs(skin_dir, exist_ok=True)
        skin_file = os.path.join(skin_dir, f"{username}.png")
        shutil.copy(skin_path, skin_file)
        self.log(f"✓ Skin set for {username} at {skin_file}")

    def load_profiles(self):
        profiles_path = os.path.join(PROFILES_DIR, "profiles.json")
        if os.path.exists(profiles_path):
            with open(profiles_path, 'r') as f:
                return json.load(f)
        return {"default": {"version": "1.21", "username": "Player"}}

    def save_profiles(self):
        profiles_path = os.path.join(PROFILES_DIR, "profiles.json")
        with open(profiles_path, 'w') as f:
            json.dump(self.profiles, f)

    def add_profile(self, name, version, username):
        self.profiles[name] = {"version": version, "username": username}
        self.save_profiles()
        self.log(f"✓ Profile '{name}' added")

    def build_classpath(self, version_id, ram_gb):
        version_dir = os.path.join(VERSIONS_DIR, version_id)
        with open(os.path.join(version_dir, f"{version_id}.json"), 'r') as f:
            version_data = json.load(f)

        classpath_entries = []
        current_os = platform.system().lower()
        if current_os == 'darwin':
            current_os = 'osx'
        for lib in version_data['libraries']:
            if self.is_library_allowed(lib, current_os) and 'downloads' in lib and 'artifact' in lib['downloads']:
                artifact = lib['downloads']['artifact']
                lib_path = os.path.join(LIBRARIES_DIR, artifact['path'])
                if os.path.exists(lib_path):
                    classpath_entries.append(lib_path)

        # Add Forge/Fabric if installed
        forge_jar = os.path.join(version_dir, f"forge-{version_id}.jar")
        if os.path.exists(forge_jar):
            classpath_entries.append(forge_jar)

        fabric_loader = os.path.join(version_dir, "fabric-loader.jar")
        if os.path.exists(fabric_loader):
            classpath_entries.append(fabric_loader)

        classpath_entries.append(os.path.join(version_dir, f"{version_id}.jar"))
        separator = ';' if platform.system() == 'Windows' else ':'
        return separator.join(classpath_entries)

    def generate_offline_uuid(self, username):
        """Generate offline UUID."""
        offline_prefix = "OfflinePlayer:"
        hash_value = hashlib.md5((offline_prefix + username).encode('utf-8')).hexdigest()
        return f"{hash_value[:8]}-{hash_value[8:12]}-{hash_value[12:16]}-{hash_value[16:20]}-{hash_value[20:32]}"

    def launch_minecraft(self, version_id, username, ram_gb=2):
        version_dir = os.path.join(VERSIONS_DIR, version_id)
        minecraft_jar = os.path.join(version_dir, f"{version_id}.jar")

        if not os.path.exists(minecraft_jar):
            self.log(f"minecraft.jar missing, downloading {version_id}...")
            if not self.download_version(version_id):
                self.log("✗ Failed to download Minecraft.")
                return False

        if not self.check_java():
            return False

        self.log("Building classpath...")
        classpath = self.build_classpath(version_id, ram_gb)
        with open(os.path.join(version_dir, f"{version_id}.json"), 'r') as f:
            version_data = json.load(f)

        java_path = self.get_java_path()
        cmd = [
            java_path,
            f'-Xmx{ram_gb}G',
            f'-Xms{max(1, ram_gb//2)}G',
            '-XX:+UseG1GC',
            '-XX:MaxGCPauseMillis=20',
            '-XX:G1HeapRegionSize=32M',
            '-XX:-OmitStackTraceInFastThrow',
            '-XX:+AlwaysPreTouch'
        ]
        if platform.system() == 'Darwin':
            cmd.append('-XstartOnFirstThread')

        natives_dir = os.path.join(version_dir, "natives")
        cmd.extend([
            f'-Djava.library.path={natives_dir}',
            '-cp', classpath,
            version_data['mainClass'],
            '--username', username,
            '--version', version_id,
            '--gameDir', CTLAUNCHER_DIR,
            '--assetsDir', ASSETS_DIR,
            '--assetIndex', version_data['assetIndex']['id'],
            '--uuid', self.generate_offline_uuid(username),
            '--accessToken', '0',
            '--userType', 'legacy',
            '--versionType', 'release'
        ])
        self.log(f"🔥 Launching Cracked Minecraft {version_id} as {username} with {ram_gb}GB RAM (Optimized)...")
        try:
            subprocess.Popen(cmd, cwd=CTLAUNCHER_DIR)
            self.log("✓ Minecraft launched successfully! (Offline/Cracked Mode)")
            return True
        except Exception as e:
            self.log(f"✗ Failed to launch: {e}")
            return False

    def check_tlauncher_source_safety(self):
        """Placeholder for checking TLauncher source safety - logs warning as no official safe source exists."""
        self.log("⚠ Note: TLauncher is closed-source. No official codebase available. Avoiding unofficial/malware sources (e.g., YouTube). Enhanced features added instead.")
        # No actual download; enhances existing code with TLauncher-like dynamic Forge fetching

# ==============================================================
# GUI: CTLauncher
# ==============================================================

class CTLauncherGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(f"CTLauncher {LAUNCHER_VERSION}")
        self.root.geometry("900x600")
        self.root.configure(bg=THEME['bg'])

        self.launcher = MinecraftLauncher(log_callback=self.append_log)
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.ram_var = tk.IntVar(value=2)

        # Configure ttk styles for light theme
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure('TCombobox', fieldbackground=THEME['log_bg'], foreground=THEME['fg'])
        self.style.configure('TEntry', fieldbackground=THEME['log_bg'], foreground=THEME['fg'])
        self.style.configure('TButton', background=THEME['accent'], foreground='white')

        self.create_widgets()
        # Initial safety check for TLauncher integration
        threading.Thread(target=self.launcher.check_tlauncher_source_safety, daemon=True).start()

    def create_widgets(self):
        # Sidebar
        sidebar = tk.Frame(self.root, bg=THEME['sidebar'], width=250)
        sidebar.pack(side='left', fill='y')

        title = tk.Label(sidebar, text=f"CTLauncher {LAUNCHER_VERSION}", fg=THEME['accent'], bg=THEME['sidebar'],
                         font=("Segoe UI", 12, "bold"))
        title.pack(pady=10)

        java_status = tk.Label(sidebar, text="Java: Checking...", bg=THEME['sidebar'], fg=THEME['fg'])
        java_status.pack(pady=(0, 5))
        self.java_label = java_status

        # Profiles
        profile_label = tk.Label(sidebar, text="Profiles:", bg=THEME['sidebar'], fg=THEME['fg'])
        profile_label.pack(pady=(10, 0))
        self.profile_list = tk.Listbox(sidebar, height=4, bg=THEME['log_bg'], fg=THEME['fg'])
        self.profile_list.pack(pady=5)
        self.update_profile_list()
        tk.Button(sidebar, text="Add Profile", command=self.add_profile_dialog, bg=THEME['accent'], fg='white').pack(pady=2)

        version_label = tk.Label(sidebar, text="Version:", bg=THEME['sidebar'], fg=THEME['fg'])
        version_label.pack(pady=(10, 0))

        self.version_combo = ttk.Combobox(sidebar, width=25)
        self.version_combo.pack(pady=5)

        username_label = tk.Label(sidebar, text="Username:", bg=THEME['sidebar'], fg=THEME['fg'])
        username_label.pack(pady=(15, 0))

        self.username_entry = ttk.Entry(sidebar, width=25)
        self.username_entry.insert(0, "Player")
        self.username_entry.pack(pady=5)

        # RAM settings from optimized
        ram_frame = tk.Frame(sidebar, bg=THEME['sidebar'])
        ram_frame.pack(fill="x", padx=10, pady=5)
        tk.Label(ram_frame, text="RAM (GB):", bg=THEME['sidebar'], fg=THEME['fg']).pack(anchor="w")
        self.ram_scale = tk.Scale(ram_frame, from_=1, to=16, orient="horizontal", variable=self.ram_var,
                                  bg=THEME['sidebar'], fg=THEME['fg'], highlightthickness=0,
                                  command=self.on_ram_change)
        self.ram_scale.pack(fill="x")
        self.ram_value_label = tk.Label(ram_frame, text="2 GB", bg=THEME['sidebar'], fg=THEME['fg'])
        self.ram_value_label.pack()

        self.fetch_button = ttk.Button(sidebar, text="Fetch Versions", command=self.fetch_versions)
        self.fetch_button.pack(pady=(10, 5))

        # Download Version Button
        self.download_button = ttk.Button(sidebar, text="Download Version", command=self.download_version_gui)
        self.download_button.pack(pady=(5, 5))

        # Modloaders
        tk.Button(sidebar, text="Install Forge", command=self.install_forge, bg=THEME['accent'], fg='white').pack(pady=2)
        tk.Button(sidebar, text="Install Fabric", command=self.install_fabric, bg=THEME['accent'], fg='white').pack(pady=2)

        # Skin
        tk.Button(sidebar, text="Set Skin (PNG)", command=self.set_skin_dialog, bg=THEME['accent_light'], fg='white').pack(pady=(10, 2))

        self.play_button = ttk.Button(sidebar, text="Play (Cracked)", command=self.play_game)
        self.play_button.pack(pady=10)

        # Log area
        self.log_box = scrolledtext.ScrolledText(self.root, bg=THEME['log_bg'], fg=THEME['log_fg'],
                                                 state='disabled', wrap='word')
        self.log_box.pack(fill='both', expand=True, padx=10, pady=10)

        # Initial Java check
        threading.Thread(target=self.check_initial_java, daemon=True).start()

    def download_version_gui(self):
        version = self.version_combo.get().strip()
        if not version:
            messagebox.showerror("Error", "Please select a version first.")
            return
        self.append_log(f"Starting download for {version}...")
        threading.Thread(target=lambda: self.launcher.download_version(version), daemon=True).start()

    def on_ram_change(self, value):
        ram_gb = int(float(value))
        self.ram_value_label.config(text=f"{ram_gb} GB")

    def update_profile_list(self):
        self.profile_list.delete(0, tk.END)
        for name in self.launcher.profiles:
            self.profile_list.insert(tk.END, name)

    def add_profile_dialog(self):
        name = simpledialog.askstring("New Profile", "Profile Name:")
        if name:
            version = self.version_combo.get() or "1.21"
            username = self.username_entry.get() or "Player"
            self.launcher.add_profile(name, version, username)
            self.update_profile_list()
            self.profile_list.selection_set(tk.END)

    def install_forge(self):
        version = self.version_combo.get()
        if version:
            threading.Thread(target=lambda: self.launcher.install_forge(version), daemon=True).start()

    def install_fabric(self):
        version = self.version_combo.get()
        if version:
            threading.Thread(target=lambda: self.launcher.install_fabric(version), daemon=True).start()

    def set_skin_dialog(self):
        skin_path = filedialog.askopenfilename(title="Select Skin PNG", filetypes=[("PNG files", "*.png")])
        if skin_path:
            username = self.username_entry.get() or "Player"
            threading.Thread(target=lambda: self.launcher.set_skin(username, skin_path), daemon=True).start()

    def check_initial_java(self):
        if self.launcher.check_java():
            self.java_label.config(text="Java: 21 (Bundled/Compatible)")
            self.java_label.config(fg=THEME['fg'])
        else:
            self.java_label.config(text="Java: Issue - Will download on launch")
            self.java_label.config(fg='red')

    def append_log(self, text):
        self.log_box.configure(state='normal')
        self.log_box.insert(tk.END, text + "\n")
        self.log_box.configure(state='disabled')
        self.log_box.see(tk.END)
        self.root.update_idletasks()

    def fetch_versions(self):
        def task():
            if self.launcher.fetch_version_manifest():
                versions = [v['id'] for v in self.launcher.version_manifest['versions'][:50]]
                self.root.after(0, lambda: self.version_combo.config(values=versions))
                if versions:
                    self.root.after(0, lambda: self.version_combo.set(versions[0]))
        threading.Thread(target=task, daemon=True).start()

    def play_game(self):
        version = self.version_combo.get().strip()
        username = self.username_entry.get().strip() or "Player"
        ram_gb = self.ram_var.get()
        if not version:
            messagebox.showerror("Error", "Please select a version first.")
            return
        # Save to current profile if selected
        selected = self.profile_list.curselection()
        if selected:
            name = self.profile_list.get(selected[0])
            self.launcher.profiles[name] = {"version": version, "username": username}
            self.launcher.save_profiles()
        threading.Thread(target=lambda: self.launcher.launch_minecraft(version, username, ram_gb), daemon=True).start()

    def run(self):
        self.root.mainloop()

# ==============================================================
# Entry Point
# ==============================================================

if __name__ == "__main__":
    gui = CTLauncherGUI()
    gui.run()
