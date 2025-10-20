import os
import sys
import subprocess
import platform
import urllib.request
import zipfile
import json
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re
import hashlib
import ssl
import time
import requests

# Define constants for directories and URLs
CTLAUNCHER_DIR = os.path.expanduser("~/.ctlauncher")
VERSIONS_DIR = os.path.join(CTLAUNCHER_DIR, "versions")
JAVA_DIR = os.path.join(CTLAUNCHER_DIR, "java")
ASSETS_DIR = os.path.join(CTLAUNCHER_DIR, "assets")
LIBRARIES_DIR = os.path.join(CTLAUNCHER_DIR, "libraries")
VERSION_MANIFEST_URL = "https://launchermeta.mojang.com/mc/game/version_manifest.json"

# Download settings
MAX_RETRIES = 5
RETRY_DELAY = 2
DOWNLOAD_TIMEOUT = 60
RATE_LIMIT_DELAY = 0.1

# CTLauncher theme colors
THEME = {
    'bg': '#121212',
    'sidebar': '#1f1f1f',
    'accent': '#2196f3',
    'accent_light': '#64b5f6',
    'text': '#ffffff',
    'text_secondary': '#bbbbbb',
    'button': '#2196f3',
    'button_hover': '#64b5f6',
    'input_bg': '#2f2f2f',
    'header_bg': '#0d0d0d',
    'tab_active': '#2196f3',
    'tab_inactive': '#121212'
}

class CTLauncher(tk.Tk):
    def __init__(self):
        """Initialize the CTLauncher window and UI."""
        super().__init__()
        self.title("CTLauncher v1.0")
        self.geometry("600x400")
        self.minsize(600, 400)
        self.configure(bg=THEME['bg'])
        self.versions = {}
        self.version_categories = {
            "Latest Release": [],
            "Latest Snapshot": [],
            "Release": [],
            "Snapshot": [],
            "Old Beta": [],
            "Old Alpha": []
        }
        
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.configure_styles()
        
        self.init_ui()

    def configure_styles(self):
        """Configure ttk styles for CTLauncher."""
        self.style.configure("TFrame", background=THEME['bg'])
        self.style.configure("TLabel", background=THEME['bg'], foreground=THEME['text'])
        self.style.configure("TButton",
                           background=THEME['button'],
                           foreground=THEME['text'],
                           borderwidth=0,
                           focuscolor='none')
        self.style.map("TButton",
                     background=[('active', THEME['button_hover']),
                                 ('pressed', THEME['accent'])])
        
        self.style.configure("TCombobox",
                           fieldbackground=THEME['input_bg'],
                           background=THEME['input_bg'],
                           foreground=THEME['text'],
                           borderwidth=0)

    def init_ui(self):
        """Set up the graphical user interface."""
        header = tk.Frame(self, bg=THEME['header_bg'], height=40)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)
        
        title = tk.Label(header, text="CTLauncher", font=("Arial", 14, "bold"),
                        bg=THEME['header_bg'], fg=THEME['accent'])
        title.pack(side="left", padx=15, pady=10)
        
        main_container = tk.Frame(self, bg=THEME['bg'])
        main_container.pack(fill="both", expand=True, padx=10, pady=10)
        
        left_panel = tk.Frame(main_container, bg=THEME['sidebar'], width=250)
        left_panel.pack(side="left", fill="y", padx=(0, 10))
        left_panel.pack_propagate(False)
        
        version_frame = tk.Frame(left_panel, bg=THEME['sidebar'])
        version_frame.pack(fill="x", padx=15, pady=15)
        
        tk.Label(version_frame, text="VERSION", font=("Arial", 9, "bold"),
                bg=THEME['sidebar'], fg=THEME['text_secondary']).pack(anchor="w")
        
        self.category_combo = ttk.Combobox(version_frame, values=list(self.version_categories.keys()),
                                          state="readonly", font=("Arial", 10))
        self.category_combo.pack(fill="x", pady=(5, 0))
        self.category_combo.set("Latest Release")
        self.category_combo.bind("<<ComboboxSelected>>", self.update_version_list)
        
        self.version_combo = ttk.Combobox(version_frame, state="readonly", font=("Arial", 10))
        self.version_combo.pack(fill="x", pady=5)
        
        account_frame = tk.Frame(left_panel, bg=THEME['sidebar'])
        account_frame.pack(fill="x", padx=15, pady=10)
        
        tk.Label(account_frame, text="USERNAME", font=("Arial", 9, "bold"),
                bg=THEME['sidebar'], fg=THEME['text_secondary']).pack(anchor="w")
        
        self.username_input = tk.Entry(account_frame, font=("Arial", 10), bg=THEME['input_bg'],
                                      fg=THEME['text'], insertbackground=THEME['text'], bd=0)
        self.username_input.pack(fill="x", pady=(5, 0))
        self.username_input.insert(0, "Player")
        
        ram_frame = tk.Frame(left_panel, bg=THEME['sidebar'])
        ram_frame.pack(fill="x", padx=15, pady=10)
        
        ram_header = tk.Frame(ram_frame, bg=THEME['sidebar'])
        ram_header.pack(fill="x")
        
        tk.Label(ram_header, text="RAM (GB)", font=("Arial", 9, "bold"),
                bg=THEME['sidebar'], fg=THEME['text_secondary']).pack(side="left")
        
        self.ram_value_label = tk.Label(ram_header, text="4 GB", font=("Arial", 9),
                                       bg=THEME['sidebar'], fg=THEME['text'])
        self.ram_value_label.pack(side="right")
        
        self.ram_scale = tk.Scale(ram_frame, from_=1, to=16, orient="horizontal",
                                 bg=THEME['sidebar'], fg=THEME['text'],
                                 activebackground=THEME['accent'],
                                 highlightthickness=0, bd=0,
                                 troughcolor=THEME['input_bg'],
                                 command=lambda v: self.ram_value_label.config(text=f"{int(float(v))} GB"))
        self.ram_scale.set(4)
        self.ram_scale.pack(fill="x")
        
        launch_button = tk.Button(left_panel, text="PLAY NOW", font=("Arial", 12, "bold"),
                                 bg=THEME['accent'], fg=THEME['text'],
                                 bd=0, pady=12, command=self.prepare_and_launch)
        launch_button.pack(side="bottom", padx=15, pady=15, fill="x")
        
        right_panel = tk.Frame(main_container, bg=THEME['bg'])
        right_panel.pack(side="left", fill="both", expand=True)
        
        status_frame = tk.Frame(right_panel, bg=THEME['bg'])
        status_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        tk.Label(status_frame, text="STATUS", font=("Arial", 12, "bold"),
                bg=THEME['bg'], fg=THEME['text']).pack(anchor="w")
        
        self.status_text = tk.Text(status_frame, bg=THEME['input_bg'], fg=THEME['text'],
                                  wrap=tk.WORD, width=50, height=15, bd=0)
        self.status_text.pack(fill="both", expand=True, pady=(10, 0))
        self.status_text.config(state=tk.DISABLED)
        
        self.load_version_manifest()

    def log_status(self, message):
        """Add message to status text area."""
        self.status_text.config(state=tk.NORMAL)
        self.status_text.insert(tk.END, message + "\n")
        self.status_text.see(tk.END)
        self.status_text.config(state=tk.DISABLED)
        self.update_idletasks()

    def update_version_list(self, event=None):
        """Update the version list based on selected category."""
        category = self.category_combo.get()
        if self.version_categories[category]:
            self.version_combo['values'] = self.version_categories[category]
            self.version_combo.current(0)

    def download_with_retry(self, url, output_path, description="file", expected_sha1=None):
        """Download a file with retry logic and checksum verification."""
        for attempt in range(MAX_RETRIES):
            try:
                self.log_status(f"📥 Downloading {description} (attempt {attempt + 1}/{MAX_RETRIES})...")
                
                ssl_context = ssl.create_default_context()
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
                
                req = urllib.request.Request(url, headers={'User-Agent': 'CTLauncher/1.0'})
                
                with urllib.request.urlopen(req, context=ssl_context, timeout=DOWNLOAD_TIMEOUT) as response:
                    with open(output_path, 'wb') as out_file:
                        out_file.write(response.read())
                
                if expected_sha1 and not self.verify_file(output_path, expected_sha1):
                    self.log_status(f"⚠️ Checksum mismatch for {description}, retrying...")
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    if attempt < MAX_RETRIES - 1:
                        time.sleep(RETRY_DELAY * (2 ** attempt))
                        continue
                    else:
                        return False
                
                self.log_status(f"✅ Downloaded {description} successfully!")
                return True
                
            except Exception as e:
                self.log_status(f"⚠️ Error downloading {description}: {e}")
                if os.path.exists(output_path):
                    os.remove(output_path)
                
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY * (2 ** attempt)
                    self.log_status(f"🔄 Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    self.log_status(f"❌ Failed to download {description} after {MAX_RETRIES} attempts")
                    return False
        
        return False

    def load_version_manifest(self):
        """Load the list of available Minecraft versions."""
        try:
            self.log_status("📡 Loading version manifest...")
            
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            req = urllib.request.Request(
                VERSION_MANIFEST_URL,
                headers={'User-Agent': 'CTLauncher/1.0'}
            )
            
            with urllib.request.urlopen(req, context=ssl_context, timeout=10) as url:
                manifest = json.loads(url.read().decode())
                
                for category in self.version_categories:
                    self.version_categories[category] = []
                
                latest_release = manifest["latest"]["release"]
                latest_snapshot = manifest["latest"]["snapshot"]
                
                for v in manifest["versions"]:
                    self.versions[v["id"]] = v["url"]
                    
                    if v["id"] == latest_release:
                        self.version_categories["Latest Release"].append(v["id"])
                    elif v["id"] == latest_snapshot:
                        self.version_categories["Latest Snapshot"].append(v["id"])
                    
                    if v["type"] == "release" and v["id"] != latest_release:
                        self.version_categories["Release"].append(v["id"])
                    elif v["type"] == "snapshot" and v["id"] != latest_snapshot:
                        self.version_categories["Snapshot"].append(v["id"])
                    elif v["type"] == "old_beta":
                        self.version_categories["Old Beta"].append(v["id"])
                    elif v["type"] == "old_alpha":
                        self.version_categories["Old Alpha"].append(v["id"])
                
                self.update_version_list()
                self.log_status("✅ Version manifest loaded successfully!")
                
        except Exception as e:
            self.log_status(f"❌ Error loading version manifest: {e}")
            messagebox.showerror("CTLauncher Error", f"Failed to load version manifest: {str(e)}")

    def is_java_installed(self, required_version="21"):
        """Check if a compatible Java version is installed."""
        def check_java(java_bin):
            try:
                result = subprocess.run([java_bin, "-version"], capture_output=True, text=True, timeout=10)
                output = result.stderr + result.stdout
                match = re.search(r'version\s+"?(\d+)(?:\.(\d+))?', output)
                if match:
                    major_version = int(match.group(1))
                    return major_version >= int(required_version)
                return False
            except (subprocess.SubprocessError, FileNotFoundError):
                return False
        
        # Check local Java first
        local_java_dir = self.get_local_java_dir()
        if local_java_dir:
            java_bin = os.path.join(JAVA_DIR, local_java_dir, "bin", "java.exe" if platform.system() == "Windows" else "java")
            if os.path.exists(java_bin) and check_java(java_bin):
                return True
        
        # Fall back to system Java
        return check_java("java")

    def get_local_java_dir(self):
        """Find the extracted Java directory dynamically."""
        if not os.path.exists(JAVA_DIR):
            return None
        for dir_name in os.listdir(JAVA_DIR):
            if dir_name.startswith("jdk-") and os.path.isdir(os.path.join(JAVA_DIR, dir_name)):
                return dir_name
        return None

    def install_java_if_needed(self):
        """Install the latest OpenJDK 21 if needed."""
        if self.is_java_installed():
            self.log_status("✅ Java is already installed!")
            return True
        
        self.log_status("⬇️ Installing OpenJDK 21...")
        java_url, java_version = self.get_latest_java_url()
        if not java_url:
            messagebox.showerror("CTLauncher Error", "Unsupported OS or failed to fetch Java URL!")
            return False
        
        archive_ext = "zip" if platform.system() == "Windows" else "tar.gz"
        archive_path = os.path.join(JAVA_DIR, f"openjdk.{archive_ext}")
        os.makedirs(JAVA_DIR, exist_ok=True)
        
        if not self.download_with_retry(java_url, archive_path, "Java 21"):
            messagebox.showerror("CTLauncher Error", "Failed to download Java 21.")
            return False
        
        try:
            if platform.system() == "Windows":
                with zipfile.ZipFile(archive_path, "r") as zip_ref:
                    zip_ref.extractall(JAVA_DIR)
            else:
                import tarfile
                with tarfile.open(archive_path, "r:gz") as tar_ref:
                    tar_ref.extractall(JAVA_DIR)
                # Set executable permissions on macOS/Linux
                java_bin = os.path.join(JAVA_DIR, self.get_local_java_dir() or "jdk-21", "bin", "java")
                if os.path.exists(java_bin):
                    os.chmod(java_bin, 0o755)
        except Exception as e:
            self.log_status(f"❌ Failed to extract Java: {e}")
            messagebox.showerror("CTLauncher Error", f"Failed to extract Java 21: {str(e)}")
            return False
        finally:
            if os.path.exists(archive_path):
                os.remove(archive_path)
        
        self.log_status("✅ Java 21 installed locally!")
        return True

    def get_latest_java_url(self):
        """Fetch the latest OpenJDK 21 release URL."""
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
            self.log_status(f"❌ Failed to fetch latest Java version: {e}")
            return None, None

    @staticmethod
    def verify_file(file_path, expected_sha1):
        """Verify the SHA1 checksum of a file."""
        try:
            with open(file_path, "rb") as f:
                file_hash = hashlib.sha1(f.read()).hexdigest()
            return file_hash.lower() == expected_sha1.lower()
        except Exception:
            return False

    def download_assets(self, version_data):
        """Download assets for the version."""
        if "assetIndex" not in version_data:
            self.log_status("ℹ️ No assets required for this version")
            return True

        asset_index = version_data["assetIndex"]
        asset_index_id = asset_index["id"]
        asset_index_url = asset_index["url"]
        
        self.log_status(f"⬇️ Downloading asset index: {asset_index_id}")
        
        indexes_dir = os.path.join(ASSETS_DIR, "indexes")
        objects_dir = os.path.join(ASSETS_DIR, "objects")
        os.makedirs(indexes_dir, exist_ok=True)
        os.makedirs(objects_dir, exist_ok=True)
        
        asset_index_path = os.path.join(indexes_dir, f"{asset_index_id}.json")
        
        if not self.download_with_retry(asset_index_url, asset_index_path, f"asset index {asset_index_id}"):
            messagebox.showerror("CTLauncher Error", f"Failed to download asset index {asset_index_id}.")
            return False
        
        try:
            with open(asset_index_path, "r") as f:
                asset_data = json.load(f)
        except Exception as e:
            self.log_status(f"❌ Failed to read asset index: {e}")
            messagebox.showerror("CTLauncher Error", f"Cannot read asset index {asset_index_id}: {str(e)}")
            return False
        
        objects = asset_data.get("objects", {})
        total_objects = len(objects)
        self.log_status(f"⬇️ Downloading {total_objects} assets...")
        
        downloaded = 0
        failed = 0
        for asset_name, asset_info in objects.items():
            hash_ = asset_info["hash"]
            hash_prefix = hash_[:2]
            object_url = f"https://resources.download.minecraft.net/{hash_prefix}/{hash_}"
            object_path = os.path.join(objects_dir, hash_prefix, hash_)
            
            if os.path.exists(object_path) and self.verify_file(object_path, hash_):
                downloaded += 1
                continue
            
            os.makedirs(os.path.dirname(object_path), exist_ok=True)
            if self.download_with_retry(object_url, object_path, f"asset {asset_name}", hash_):
                downloaded += 1
            else:
                failed += 1
            
            if (downloaded + failed) % 10 == 0:
                self.log_status(f"📦 Downloaded {downloaded}/{total_objects} assets, {failed} failed...")
                self.update_idletasks()
        
        self.log_status(f"✅ Downloaded {downloaded}/{total_objects} assets, {failed} failed")
        if failed > 0:
            messagebox.showwarning("CTLauncher Warning", f"Failed to download {failed} assets. The game may not run correctly.")
            return False
        return True

    def get_natives_classifier(self, current_os):
        """Return the classifier key for native libraries based on the OS."""
        if current_os == "windows":
            return "natives-windows"
        elif current_os == "osx":
            return "natives-osx" if self.is_macos_modern() else "natives-macos"
        elif current_os == "linux":
            return "natives-linux"
        return None

    def is_macos_modern(self):
        """Check if macOS version is modern (post-1.13.2 compatibility)."""
        if platform.system() == "Darwin":
            try:
                version = platform.mac_ver()[0]
                major_version = int(version.split('.')[0])
                return major_version >= 10
            except Exception:
                return True
        return False

    def download_version_files(self, version_id, version_url):
        """Download the version JSON, JAR, libraries, and assets."""
        self.log_status(f"⬇️ Downloading version files for {version_id}...")
        version_dir = os.path.join(VERSIONS_DIR, version_id)
        os.makedirs(version_dir, exist_ok=True)
        
        version_json_path = os.path.join(version_dir, f"{version_id}.json")
        if not self.download_with_retry(version_url, version_json_path, f"{version_id} JSON"):
            messagebox.showerror("CTLauncher Error", f"Failed to download version {version_id} JSON.")
            return False
        
        try:
            with open(version_json_path, "r") as f:
                data = json.load(f)
        except Exception as e:
            self.log_status(f"❌ Failed to read version JSON: {e}")
            messagebox.showerror("CTLauncher Error", f"Cannot read version {version_id} JSON: {str(e)}")
            return False
        
        # Download client JAR
        try:
            jar_url = data["downloads"]["client"]["url"]
            jar_path = os.path.join(version_dir, f"{version_id}.jar")
            expected_sha1 = data["downloads"]["client"]["sha1"]
            
            if not os.path.exists(jar_path) or not self.verify_file(jar_path, expected_sha1):
                if not self.download_with_retry(jar_url, jar_path, f"{version_id} JAR", expected_sha1):
                    messagebox.showerror("CTLauncher Error", f"Failed to download version {version_id} JAR.")
                    return False
        except KeyError as e:
            self.log_status(f"❌ Missing client JAR info: {e}")
            messagebox.showerror("CTLauncher Error", f"Version {version_id} is missing client JAR information.")
            return False
        
        # Download assets
        if not self.download_assets(data):
            return False
        
        # Download libraries and natives
        current_os = platform.system().lower()
        if current_os == "darwin":
            current_os = "osx"
        
        natives_dir = os.path.join(version_dir, "natives")
        os.makedirs(natives_dir, exist_ok=True)
        os.makedirs(LIBRARIES_DIR, exist_ok=True)
        
        for lib in data.get("libraries", []):
            if not self.is_library_allowed(lib, current_os):
                continue
                
            # Download main artifact
            if "downloads" in lib and "artifact" in lib["downloads"]:
                lib_url = lib["downloads"]["artifact"]["url"]
                lib_path = os.path.join(LIBRARIES_DIR, lib["downloads"]["artifact"]["path"])
                os.makedirs(os.path.dirname(lib_path), exist_ok=True)
                expected_sha1 = lib["downloads"]["artifact"]["sha1"]
                
                if not os.path.exists(lib_path) or not self.verify_file(lib_path, expected_sha1):
                    lib_name = lib.get('name', 'unknown')
                    if not self.download_with_retry(lib_url, lib_path, f"library {lib_name}", expected_sha1):
                        self.log_status(f"⚠️ Failed to download library {lib_name}, continuing...")
            
            # Download native libraries
            if "downloads" in lib and "classifiers" in lib["downloads"]:
                natives_key = self.get_natives_classifier(current_os)
                if natives_key and natives_key in lib["downloads"]["classifiers"]:
                    native_info = lib["downloads"]["classifiers"][natives_key]
                    native_url = native_info["url"]
                    native_path = os.path.join(natives_dir, os.path.basename(native_info["path"]))
                    expected_sha1 = native_info["sha1"]
                    
                    if not os.path.exists(native_path) or not self.verify_file(native_path, expected_sha1):
                        lib_name = lib.get('name', 'unknown')
                        if self.download_with_retry(native_url, native_path, f"native {lib_name}", expected_sha1):
                            try:
                                if native_path.endswith('.jar'):
                                    with zipfile.ZipFile(native_path, 'r') as zip_ref:
                                        zip_ref.extractall(natives_dir)
                            except Exception as e:
                                self.log_status(f"⚠️ Failed to extract native {lib_name}: {e}")
        
        self.log_status("✅ Download complete! Ready to play!")
        return True

    def is_library_allowed(self, lib, current_os):
        """Check if a library is allowed on the current OS."""
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

    def generate_offline_uuid(self, username):
        """Generate a UUID for offline mode."""
        offline_prefix = "OfflinePlayer:"
        hash_value = hashlib.md5((offline_prefix + username).encode('utf-8')).hexdigest()
        uuid_str = f"{hash_value[:8]}-{hash_value[8:12]}-{hash_value[12:16]}-{hash_value[16:20]}-{hash_value[20:32]}"
        return uuid_str

    def build_launch_command(self, version, username, ram):
        """Construct the command to launch Minecraft."""
        version_dir = os.path.join(VERSIONS_DIR, version)
        json_path = os.path.join(version_dir, f"{version}.json")
        
        try:
            with open(json_path, "r") as f:
                version_data = json.load(f)
        except Exception as e:
            self.log_status(f"❌ Failed to read version JSON: {e}")
            messagebox.showerror("CTLauncher Error", f"Cannot read version {version} JSON: {str(e)}")
            return []
        
        current_os = platform.system().lower()
        if current_os == "darwin":
            current_os = "osx"
        
        main_class = version_data.get("mainClass", "net.minecraft.client.main.Main")
        natives_dir = os.path.join(version_dir, "natives")
        jar_path = os.path.join(version_dir, f"{version}.jar")
        
        classpath = [jar_path]
        for lib in version_data.get("libraries", []):
            if self.is_library_allowed(lib, current_os) and "downloads" in lib and "artifact" in lib["downloads"]:
                lib_path = os.path.join(LIBRARIES_DIR, lib["downloads"]["artifact"]["path"])
                if os.path.exists(lib_path):
                    classpath.append(lib_path)
        
        classpath_str = ";".join(classpath) if platform.system() == "Windows" else ":".join(classpath)
        
        java_bin = "java"
        local_java_dir = self.get_local_java_dir()
        if local_java_dir:
            local_java_bin = os.path.join(JAVA_DIR, local_java_dir, "bin", "java.exe" if platform.system() == "Windows" else "java")
            if os.path.exists(local_java_bin) and self.is_java_installed():
                java_bin = local_java_bin
        
        command = [java_bin, f"-Xmx{ram}G"]
        
        if platform.system() == "Darwin":
            command.append("-XstartOnFirstThread")
        
        command.append(f"-Djava.library.path={natives_dir}")
        command.extend(["-cp", classpath_str, main_class])
        
        uuid = self.generate_offline_uuid(username)
        asset_index = version_data.get("assetIndex", {}).get("id", "legacy")
        
        game_args = [
            "--username", username,
            "--version", version,
            "--gameDir", CTLAUNCHER_DIR,
            "--assetsDir", ASSETS_DIR,
            "--assetIndex", asset_index,
            "--uuid", uuid,
            "--accessToken", "0",
            "--userType", "legacy",
            "--versionType", "release"
        ]
        
        command.extend(game_args)
        return command

    def prepare_and_launch(self):
        """Wrapper function to handle setup before launching."""
        if not self.install_java_if_needed():
            return
        self.download_and_launch()

    def download_and_launch(self):
        """Handle the download and launch process."""
        version = self.version_combo.get()
        if not version:
            messagebox.showerror("CTLauncher Error", "No version selected.")
            return
        
        username = self.username_input.get() or "Player"
        ram = int(self.ram_scale.get())
        version_url = self.versions.get(version)
        
        if not version_url:
            messagebox.showerror("CTLauncher Error", f"Version {version} URL not found.")
            return
        
        if not self.download_version_files(version, version_url):
            return
        
        launch_cmd = self.build_launch_command(version, username, ram)
        if not launch_cmd:
            return
        
        self.log_status("🚀 Launching Minecraft...")
        self.log_status("Have fun gaming!")
        
        try:
            # Use subprocess.DEVNULL instead of PIPE to avoid potential blocking
            subprocess.Popen(launch_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            self.log_status(f"❌ Failed to launch Minecraft: {e}")
            messagebox.showerror("CTLauncher Error", f"Failed to launch Minecraft: {str(e)}")

if __name__ == "__main__":
    print("CTLauncher v1.0 - Initializing...")
    app = CTLauncher()
    app.mainloop()
