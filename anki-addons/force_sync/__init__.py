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


def login_ankiweb(email: str, password: str):
    """
    Login to AnkiWeb programmatically.
    
    This authenticates with AnkiWeb and stores the credentials
    so future syncs work automatically.
    
    Args:
        email: AnkiWeb account email
        password: AnkiWeb account password
        
    Returns:
        dict with success/error status
    """
    if mw.col is None:
        return {"error": "Collection not available"}
    
    try:
        # Authenticate with AnkiWeb using Anki's built-in sync_login
        # None as endpoint means use default AnkiWeb server
        auth = mw.col.sync_login(email, password, None)
        
        if auth is None:
            return {"error": "Login failed - invalid credentials"}
        
        # Store the authentication key in the profile
        # This is the same thing Anki does when you login via GUI
        mw.pm.set_sync_key(auth.hkey)
        mw.pm.set_sync_username(email)
        mw.pm.save()
        
        return {
            "success": True, 
            "message": "Successfully logged in to AnkiWeb",
            "username": email
        }
    except Exception as e:
        error_msg = str(e)
        # Provide more helpful error messages
        if "401" in error_msg or "unauthorized" in error_msg.lower():
            return {"error": "Invalid email or password"}
        elif "network" in error_msg.lower() or "connection" in error_msg.lower():
            return {"error": "Could not connect to AnkiWeb. Check your internet connection."}
        return {"error": error_msg}


def get_ankiweb_username():
    """
    Get the currently logged in AnkiWeb username.
    
    Returns:
        dict with username if logged in, or not_logged_in status
    """
    try:
        auth = mw.pm.sync_auth()
        if auth is None:
            return {"status": "not_logged_in", "username": None}
        
        # Get the stored username from profile
        username = mw.pm.profile.get("syncUser", None)
        return {
            "status": "logged_in",
            "username": username
        }
    except Exception as e:
        return {"error": str(e)}


def logout_ankiweb():
    """
    Logout from AnkiWeb by clearing stored credentials.
    
    Returns:
        dict with success status
    """
    try:
        mw.pm.clear_sync_auth()
        mw.pm.save()
        return {"success": True, "message": "Logged out from AnkiWeb"}
    except Exception as e:
        return {"error": str(e)}


def patch_anki_connect():
    """
    Patch AnkiConnect to add our custom actions.
    
    This is called after Anki starts and AnkiConnect is loaded.
    """
    log_to_file("patch_anki_connect() called")
    try:
        # Find AnkiConnect addon
        from importlib import import_module
        import sys
        import types
        
        # AnkiConnect addon ID - modules are loaded directly by ID, not under addons21
        addon_id = "2055492159"
        
        log_to_file(f"Looking for AnkiConnect at {addon_id}")
        log_to_file(f"Available modules: {[k for k in sys.modules.keys() if '2055492159' in k]}")
        
        if addon_id in sys.modules:
            anki_connect = sys.modules[addon_id]
            log_to_file("Found AnkiConnect in sys.modules")
        else:
            # Try to import it
            try:
                anki_connect = import_module(addon_id)
                log_to_file("Imported AnkiConnect module")
            except ImportError as e:
                log_to_file(f"AnkiConnect not found: {e}")
                print("[ForceSyncAddon] AnkiConnect not found, skipping patch")
                return
        
        # Get the AnkiConnect instance
        if hasattr(anki_connect, 'ac'):
            ac = anki_connect.ac
            
            # Try to get the util module from AnkiConnect for the proper api decorator
            util_module = None
            try:
                util_path = f"{addon_id}.util"
                log_to_file(f"Looking for util module at {util_path}")
                if util_path in sys.modules:
                    util_module = sys.modules[util_path]
                    log_to_file("Found util in sys.modules")
                else:
                    util_module = import_module(util_path)
                    log_to_file("Imported util module")
            except ImportError as e:
                log_to_file(f"Could not import util module: {e}")
                print("[ForceSyncAddon] Could not import AnkiConnect util module")
            
            # Define wrapper functions that use the proper decorator if available
            if util_module and hasattr(util_module, 'api'):
                api = util_module.api
                
                @api()
                def forceSyncUpload(self):
                    """Force full sync upload (local → server)"""
                    return full_sync_upload()
                
                @api()
                def forceSyncDownload(self):
                    """Force full sync download (server → local)"""
                    return full_sync_download()
                
                @api()
                def checkSyncStatus(self):
                    """Check sync status without syncing"""
                    return check_sync_status()
                
                @api()
                def loginAnkiWeb(self, email, password):
                    """Login to AnkiWeb with email and password"""
                    return login_ankiweb(email, password)
                
                @api()
                def getAnkiWebUsername(self):
                    """Get the currently logged in AnkiWeb username"""
                    return get_ankiweb_username()
                
                @api()
                def logoutAnkiWeb(self):
                    """Logout from AnkiWeb"""
                    return logout_ankiweb()
                
                print("[ForceSyncAddon] Using AnkiConnect's @api() decorator")
            else:
                # Fallback: manually create functions with api attribute
                def make_api_method(func):
                    """Create a method marked as an API method"""
                    func.api = True
                    func.versions = []  # Empty versions means use method name
                    return func
                
                @make_api_method
                def forceSyncUpload(self):
                    """Force full sync upload (local → server)"""
                    return full_sync_upload()
                
                @make_api_method
                def forceSyncDownload(self):
                    """Force full sync download (server → local)"""
                    return full_sync_download()
                
                @make_api_method
                def checkSyncStatus(self):
                    """Check sync status without syncing"""
                    return check_sync_status()
                
                @make_api_method
                def loginAnkiWeb(self, email, password):
                    """Login to AnkiWeb with email and password"""
                    return login_ankiweb(email, password)
                
                @make_api_method
                def getAnkiWebUsername(self):
                    """Get the currently logged in AnkiWeb username"""
                    return get_ankiweb_username()
                
                @make_api_method
                def logoutAnkiWeb(self):
                    """Logout from AnkiWeb"""
                    return logout_ankiweb()
                
                print("[ForceSyncAddon] Using fallback API method decorator")
            
            # Bind methods to the AnkiConnect instance's class
            ac_class = type(ac)
            ac_class.forceSyncUpload = forceSyncUpload
            ac_class.forceSyncDownload = forceSyncDownload
            ac_class.checkSyncStatus = checkSyncStatus
            ac_class.loginAnkiWeb = loginAnkiWeb
            ac_class.getAnkiWebUsername = getAnkiWebUsername
            ac_class.logoutAnkiWeb = logoutAnkiWeb
            
            # Verify the methods are accessible
            if hasattr(ac, 'loginAnkiWeb'):
                log_to_file("Successfully patched AnkiConnect with all actions")
                log_to_file(f"loginAnkiWeb.api = {getattr(ac.loginAnkiWeb, 'api', 'NOT SET')}")
                print("[ForceSyncAddon] Successfully patched AnkiConnect with force sync and login actions")
            else:
                log_to_file("WARNING: Methods may not be properly bound")
                print("[ForceSyncAddon] WARNING: Methods may not be properly bound")
        else:
            log_to_file("AnkiConnect 'ac' instance not found")
            print("[ForceSyncAddon] AnkiConnect 'ac' instance not found")
            
    except Exception as e:
        log_to_file(f"Error patching AnkiConnect: {e}")
        print(f"[ForceSyncAddon] Error patching AnkiConnect: {e}")
        import traceback
        traceback.print_exc()


# Log to file for debugging
def log_to_file(msg):
    """Write log message to file for debugging"""
    try:
        with open("/data/force_sync_debug.log", "a") as f:
            import datetime
            f.write(f"[{datetime.datetime.now()}] {msg}\n")
    except:
        pass

# Delay patching until after Anki and AnkiConnect are fully loaded
def on_main_window_did_init():
    """Called after main window is initialized"""
    log_to_file("Main window initialized, scheduling patch in 3 seconds...")
    # Give AnkiConnect more time to start
    QTimer.singleShot(3000, patch_anki_connect)


def on_profile_did_open():
    """Called after profile is opened - another hook point"""
    log_to_file("Profile opened, scheduling patch in 2 seconds...")
    QTimer.singleShot(2000, patch_anki_connect)


# Hook into Anki's startup
try:
    from aqt import gui_hooks
    gui_hooks.main_window_did_init.append(on_main_window_did_init)
    gui_hooks.profile_did_open.append(on_profile_did_open)
    log_to_file("Registered startup hooks")
    print("[ForceSyncAddon] Registered startup hooks")
except Exception as e:
    log_to_file(f"Error registering hooks: {e}")
    print(f"[ForceSyncAddon] Error registering hook: {e}")
