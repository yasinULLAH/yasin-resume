import os
import json
import re
import hashlib
from PIL import Image
from bs4 import BeautifulSoup

SOURCE_LOGO_PATH = r"C:\Users\Yasin\Downloads\Yasin Soft\logo.png"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
APP_NAME = "My Web App"
SHORT_NAME = "WebApp"
APP_DESCRIPTION = "A description of the web application."
BACKGROUND_COLOR = "#ffffff"
THEME_COLOR = "#007bff"
VERSION = "1.0.9"

def get_file_hash(path):
    hasher = hashlib.md5()
    try:
        with open(path, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()
    except Exception as e:
        print(f"   ❌ Could not hash file {os.path.basename(path)}: {e}")
        return None

def generate_favicon(source_path, output_dir):
    print("--- 1A. Generating favicon.ico ---")
    favicon_path = os.path.join(output_dir, "favicon.ico")
    try:
        with Image.open(source_path) as logo:
            logo = logo.convert("RGBA")
            logo.thumbnail((64, 64))  # Standard favicon size
            logo.save(favicon_path, format="ICO", sizes=[(16, 16), (32, 32), (48, 48), (64, 64)])
        print(f"✅ Created: favicon.ico")
        file_hash = get_file_hash(favicon_path)
        return {"url": "favicon.ico", "revision": file_hash} if file_hash else None
    except Exception as e:
        print(f"❌ Error generating favicon.ico: {e}")
        return None

def generate_pwa_icons(source_path, output_dir):
    print("--- 1. Generating PWA Icons ---")
    if not os.path.exists(source_path):
        print(f"❌ Error: Source logo not found at '{source_path}'.")
        return [], []
    icon_sizes = [72, 96, 128, 144, 152, 192, 384, 512]
    generated_icons = []
    icon_metadata = []
    try:
        with Image.open(source_path) as logo:
            logo = logo.convert("RGBA")
            for size in icon_sizes:
                filename = f"icon-{size}.png"
                output_path = os.path.join(output_dir, filename)
                canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
                logo_copy = logo.copy()
                logo_copy.thumbnail((size, size))
                left = (size - logo_copy.width) // 2
                top = (size - logo_copy.height) // 2
                canvas.paste(logo_copy, (left, top))
                canvas.save(output_path, "PNG")
                print(f"✅ Created: {filename}")
                file_hash = get_file_hash(output_path)
                if file_hash:
                    generated_icons.append({"url": filename, "revision": file_hash})
                icon_metadata.append({"src": filename, "sizes": f"{size}x{size}", "type": "image/png"})
        return generated_icons, icon_metadata
    except Exception as e:
        print(f"❌ Error generating icons: {e}")
        return [], []

def discover_assets(project_dir, generated_icons):
    print(f"\n--- 2. Discovering App Files and Generating Hashes ---")
    precache_list = generated_icons[:]
    existing_urls = {entry['url'] for entry in precache_list}
    html_files = []
    
    for root, _, files in os.walk(project_dir):
        if any(part.startswith('.') for part in root.split(os.sep)):
            continue
        for file in files:
            file_path = os.path.join(root, file)
            relative_path = os.path.relpath(file_path, project_dir).replace("\\", "/")
            if relative_path in existing_urls:
                continue
            if file.endswith(".html"):
                html_files.append(file_path)
            file_hash = get_file_hash(file_path)
            if file_hash:
                precache_list.append({"url": relative_path, "revision": file_hash})
                existing_urls.add(relative_path)
    if not html_files:
        print("❌ Error: No HTML files found.")
        return [], []
    print(f"✅ Discovered and hashed {len(precache_list)} local files.")
    return precache_list, html_files

def create_manifest(output_dir, icon_metadata, html_files):
    print("\n--- 3. Creating manifest.json ---")
    start_url, app_title_from_html = "index.html", None
    potential_mains = [f for f in html_files if "index.html" in f.lower()] or html_files
    if not potential_mains:
        print("❌ Error: No suitable start file (like index.html) found.")
        return
    start_file_path = potential_mains[0]
    start_url = os.path.relpath(start_file_path, output_dir).replace("\\", "/")
    try:
        with open(start_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            soup = BeautifulSoup(f.read(), 'html.parser')
            if soup.title and soup.title.string:
                app_title_from_html = soup.title.string.strip()
                print(f"✅ Detected App Title: '{app_title_from_html}'")
    except Exception as e:
        print(f"⚠️ Could not read title from HTML: {e}")
    manifest = {
        "name": app_title_from_html or APP_NAME,
        "short_name": app_title_from_html or SHORT_NAME,
        "description": APP_DESCRIPTION,
        "start_url": start_url,
        "display": "standalone",
        "background_color": BACKGROUND_COLOR,
        "theme_color": THEME_COLOR,
        "orientation": "portrait-primary",
        "icons": icon_metadata
    }
    with open(os.path.join(output_dir, "manifest.json"), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    print(f"✅ Created: manifest.json")

def create_service_worker(output_dir, precache_list):
    print("\n--- 4. Creating sw.js (Service Worker) ---")
    sw_template = f"""
// Auto-generated by PWA builder script.
importScripts('https://storage.googleapis.com/workbox-cdn/releases/7.0.0/workbox-sw.js');

if (workbox) {{
    console.log(`Workbox is loaded.`);
    
    self.addEventListener('message', (event) => {{
      if (event.data && event.data.type === 'SKIP_WAITING') {{
        console.log('Service Worker received SKIP_WAITING message, activating now.');
        self.skipWaiting();
      }}
    }});

    workbox.precaching.precacheAndRoute({json.dumps(precache_list, indent=4)});

    workbox.routing.registerRoute(
        ({{request}}) => request.destination === 'style' || request.destination === 'script',
        new workbox.strategies.StaleWhileRevalidate({{ cacheName: 'asset-cache' }})
    );

    workbox.routing.registerRoute(
        ({{request}}) => request.destination === 'image',
        new workbox.strategies.CacheFirst({{
            cacheName: 'image-cache',
            plugins: [ new workbox.expiration.ExpirationPlugin({{ maxEntries: 60, maxAgeSeconds: 30 * 24 * 60 * 60 }}) ],
        }})
    );

    workbox.routing.setCatchHandler(async ({{event}}) => {{
        if (event.request.destination === 'document') {{
            return await caches.match('offline.html') || Response.error();
        }}
        return Response.error();
    }});

}} else {{
    console.log(`Workbox failed to load.`);
}}
"""
    with open(os.path.join(output_dir, "sw.js"), 'w', encoding='utf-8') as f:
        f.write(sw_template.strip())
    print("✅ Created: sw.js")

def update_html_files(html_files):
    print("\n--- 5. Updating HTML Files ---")
    manifest_link_str = '<link rel="manifest" href="manifest.json">'
    favicon_link_str = '<link rel="icon" type="image/x-icon" href="favicon.ico">'
    sw_script_str = f"""<script type="module">
  import {{ Workbox }} from 'https://storage.googleapis.com/workbox-cdn/releases/7.0.0/workbox-window.prod.mjs';

  const swUrl = './sw.js';
  const wb = new Workbox(swUrl);

  wb.addEventListener('waiting', () => {{
    console.log('A new service worker is waiting to activate.');
    wb.messageSW({{ type: 'SKIP_WAITING' }});
  }});

  wb.addEventListener('controlling', () => {{
    console.log('The new service worker is now in control. Reloading page for updates...');
    window.location.reload();
  }});

  wb.register();
</script>"""
    for html_path in html_files:
        try:
            with open(html_path, 'r+', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                soup = BeautifulSoup(content, 'html.parser')

                for s in soup.find_all("script"):
                    if "workbox-window" in s.text or "navigator.serviceWorker" in s.text:
                        s.decompose()

                soup.body.append(BeautifulSoup(sw_script_str, 'html.parser'))

                if not soup.head.find('link', {'rel': 'manifest'}):
                    soup.head.append(BeautifulSoup(manifest_link_str, 'html.parser'))
                if not soup.head.find('link', {'rel': 'icon'}):
                    soup.head.append(BeautifulSoup(favicon_link_str, 'html.parser'))

                f.seek(0)
                f.write(str(soup))
                f.truncate()
                print(f"   - Injected scripts & links into {os.path.basename(html_path)}")
        except Exception as e:
            print(f"   ❌ Could not update {os.path.basename(html_path)}: {e}")
    print("✅ HTML files updated.")

if __name__ == "__main__":
    print(f"🚀 Starting PWA Build Script [v{VERSION}]...")
    offline_page_path = os.path.join(PROJECT_DIR, 'offline.html')
    if not os.path.exists(offline_page_path):
        with open(offline_page_path, 'w', encoding='utf-8') as f:
            f.write("<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\"><title>Offline</title></head><body><h1>You are offline.</h1></body></html>")
        print("✅ Created 'offline.html'.")

    favicon_entry = generate_favicon(SOURCE_LOGO_PATH, PROJECT_DIR)
    generated_icons, icon_metadata = generate_pwa_icons(SOURCE_LOGO_PATH, PROJECT_DIR)

    precache_list, html_files = discover_assets(PROJECT_DIR, generated_icons + ([favicon_entry] if favicon_entry else []))
    
    if html_files:
        create_manifest(PROJECT_DIR, icon_metadata, html_files)
        create_service_worker(PROJECT_DIR, precache_list)
        update_html_files(html_files)
        print(f"\n🎉 PWA setup is complete!")
    else:
        print("\n❌ Script stopped: No HTML files were found.")
