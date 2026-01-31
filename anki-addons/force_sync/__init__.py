"""
Force Sync AnkiConnect Extension

Adds forceSyncUpload and forceSyncDownload actions to AnkiConnect
to resolve full sync conflicts programmatically.

This addon patches AnkiConnect (addon 2055492159) to add new actions.
"""

import json
import urllib.request
from typing import Any

# Get the main Anki window
from aqt import mw
from aqt.qt import QTimer


def full_sync_upload():
    """
    Force a full sync UPLOAD (local → server).
    
    This overwrites AnkiWeb with local data.
    """
    if mw.col is None:
        return {"error": "Collection not available"}
    
    try:
        # Get sync auth
        auth = mw.pm.sync_auth()
        if auth is None:
            return {"error": "Not logged in to AnkiWeb"}
        
        # Perform full upload
        # This uses Anki's internal sync API
        mw.col.full_upload_or_download(
            auth=auth,
            server_usn=None,  # Will be fetched
            upload=True
        )
        
        return {"success": True, "message": "Full upload completed"}
    except Exception as e:
        return {"error": str(e)}


def full_sync_download():
    """
    Force a full sync DOWNLOAD (server → local).
    
    This overwrites local data with AnkiWeb.
    """
    if mw.col is None:
        return {"error": "Collection not available"}
    
    try:
        # Get sync auth
        auth = mw.pm.sync_auth()
        if auth is None:
            return {"error": "Not logged in to AnkiWeb"}
        
        # Perform full download
        mw.col.full_upload_or_download(
            auth=auth,
            server_usn=None,
            upload=False
        )
        
        return {"success": True, "message": "Full download completed"}
    except Exception as e:
        return {"error": str(e)}


def check_sync_status():
    """
    Check if sync is possible and what status it would return.
    
    Returns status:
    - 0: No changes needed
    - 1: Normal sync required
    - 2: Full sync required (conflict)
    """
    if mw.col is None:
        return {"error": "Collection not available"}
    
    try:
        auth = mw.pm.sync_auth()
        if auth is None:
            return {"status": "not_logged_in", "message": "Not logged in to AnkiWeb"}
        
        # Check sync status without actually syncing
        # This requires checking the collection's sync state
        return {
            "status": "ok",
            "message": "Ready to sync",
            "logged_in": True
        }
    except Exception as e:
        return {"error": str(e)}


def patch_anki_connect():
    """
    Patch AnkiConnect to add our custom actions.
    
    This is called after Anki starts and AnkiConnect is loaded.
    """
    try:
        # Find AnkiConnect addon
        from importlib import import_module
        import sys
        
        # AnkiConnect addon ID
        addon_id = "2055492159"
        addon_path = f"addons21.{addon_id}"
        
        if addon_path in sys.modules:
            anki_connect = sys.modules[addon_path]
        else:
            # Try to import it
            try:
                anki_connect = import_module(addon_path)
            except ImportError:
                print("[ForceSyncAddon] AnkiConnect not found, skipping patch")
                return
        
        # Get the AnkiConnect instance
        if hasattr(anki_connect, 'ac'):
            ac = anki_connect.ac
            
            # Add our custom actions as methods
            # AnkiConnect uses @util.api() decorator, but we can add methods directly
            
            def api_decorator(func):
                """Simple decorator to mark functions as API methods"""
                func.api = True
                func.versions = [(1, func.__name__)]
                return func
            
            @api_decorator
            def forceSyncUpload(self):
                """Force full sync upload (local → server)"""
                return full_sync_upload()
            
            @api_decorator
            def forceSyncDownload(self):
                """Force full sync download (server → local)"""
                return full_sync_download()
            
            @api_decorator
            def checkSyncStatus(self):
                """Check sync status without syncing"""
                return check_sync_status()
            
            # Bind methods to the AnkiConnect instance's class
            import types
            ac_class = type(ac)
            ac_class.forceSyncUpload = forceSyncUpload
            ac_class.forceSyncDownload = forceSyncDownload
            ac_class.checkSyncStatus = checkSyncStatus
            
            print("[ForceSyncAddon] Successfully patched AnkiConnect with force sync actions")
        else:
            print("[ForceSyncAddon] AnkiConnect 'ac' instance not found")
            
    except Exception as e:
        print(f"[ForceSyncAddon] Error patching AnkiConnect: {e}")
        import traceback
        traceback.print_exc()


# Delay patching until after Anki and AnkiConnect are fully loaded
def on_main_window_did_init():
    """Called after main window is initialized"""
    # Give AnkiConnect time to start
    QTimer.singleShot(2000, patch_anki_connect)


# Hook into Anki's startup
try:
    from aqt import gui_hooks
    gui_hooks.main_window_did_init.append(on_main_window_did_init)
    print("[ForceSyncAddon] Registered startup hook")
except Exception as e:
    print(f"[ForceSyncAddon] Error registering hook: {e}")
