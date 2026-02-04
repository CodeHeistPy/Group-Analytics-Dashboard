"""
================================================================================
GROUP SNAPSHOT NOTEBOOK - Version 1.2
================================================================================
Description: This notebook creates a single hosted table for ArcGIS Dashboard 
             reporting to analyze Groups in an ArcGIS Online or Enterprise 
             organization. This is a streamlined version that only creates the
             Group_Snapshot table for simplified dashboard configurations.
             
Table Created:
    1. Group_Snapshot - Overall group information and metrics (one record per group)

Source CSV Item (stored in user's content, NOT deleted):
    1. Group_Snapshot_source - Source CSV for Group_Snapshot table

NOTE: For a full version that also creates Group_Content and Group_Members tables,
      use the Group_Analytics_Notebook instead.

Author: Administrator
Version: 1.2 (based on Group_Analytics_Notebook v2.19)
    - NEW: Added has_external_members boolean field
      * True if group has any external members, False otherwise
      * Useful for Dashboard filtering on groups with/without external collaboration
    - FIXED: external_member_count now correctly identifies external users
      * Users not in organization's user list are counted as external
    - Streamlined version for Group_Snapshot table only
    - Faster execution - no content/member detail collection
    - All field length validations and truncation
    - edit_features fallback for reliability
    
Compatible: ArcGIS Online & ArcGIS Enterprise
Tested With: ArcGIS API for Python 2.3.0+

UPDATE STRATEGY:
    When existing table is found, the script uses this update process:
    1. Delete all existing features using delete_features(where="1=1")
    2. Update the source CSV item with new data
    3. Append new features using append() method
    4. If update fails, user is prompted to confirm before delete/recreate

================================================================================
HOW TO USE THIS NOTEBOOK
================================================================================

PREREQUISITES:
    - Must be run in an ArcGIS Notebook environment (ArcGIS Online or Enterprise)
    - User must have administrative privileges to view all groups and members
    - Built-in notebook authentication is used (no credentials needed)

CONFIGURATION OPTIONS (Cell 1):
    - TEST_MODE: Set to True to analyze only first 10 groups (for testing)
                 Set to False to analyze all groups in the organization
    - TEST_LIMIT: Number of groups to analyze in test mode (default: 10)
    - OUTPUT_FOLDER: Name of folder where table will be published (default: "Group Analytics")
    - RECENT_DAYS_THRESHOLD: Days threshold for "recent" activity calculations (default: 90)

RUNNING THE NOTEBOOK:
    1. Review and adjust configuration options in Cell 1 as needed
    2. Run all cells in sequence (Cell 1 through Cell 8)
    3. First run will create new hosted table
    4. Subsequent runs will truncate and reload existing table with fresh data

OUTPUT:
    - One hosted feature service table published to your content
    - Table is shared at the organization level
    - Table can be used in ArcGIS Dashboards for filtering and visualization

================================================================================
TABLE SCHEMA
================================================================================

GROUP_SNAPSHOT TABLE (one record per group):
    - group_id: Unique identifier for the group
    - group_title: Display name of the group (truncated to 256 chars)
    - group_summary: Short description/snippet (truncated to 256 chars)
    - group_description: Full description (truncated to 256 chars with "...")
    - group_tags: Comma-separated list of tags (truncated to 256 chars with "...")
    - group_owner: Username of group owner
    - group_owner_name: Full name of group owner
    - group_created: Date the group was created
    - group_type: Type including Standard, Shared Update, Partnered/Distributed Collaboration
    - group_sharing_level: Private, Organization, or Public (capitalized)
    - group_item_count: Number of items shared to the group
    - group_member_count: Number of members in the group
    - external_member_count: Number of members from other organizations
    - has_external_members: True if group has any external members
    - group_link: Direct URL to open the group
    - active_members: Members who logged in within threshold days
    - group_item_score: (active_members / total_items) * 100
    - group_member_score: (active_members / total_members) * 100
    - avg_views_per_item: Average views excluding Living Atlas content
    - days_since_content_update: Days since most recent content update
    - is_recent: True if content updated within threshold days
    - is_empty: True if group has no content
    - is_single_member: True if group has only one member
    - is_hub: True if group is part of ArcGIS Hub (Online only)
    - is_site: True if group is part of ArcGIS Enterprise Sites

================================================================================
"""

# CELL 1: IMPORTS AND CONFIGURATION
# =============================================================================
# This cell imports required libraries and sets configuration variables.
# Modify these variables to customize the notebook behavior.
# =============================================================================

import datetime
import pandas as pd
from arcgis.gis import GIS
from arcgis.features import FeatureLayerCollection
import time
import os

# ---- CONFIGURATION VARIABLES ----
# Modify these settings to customize the notebook behavior

# TEST_MODE: When True, only analyzes a limited number of groups for testing
# Set to False when ready to analyze all groups in the organization
TEST_MODE = True  # Change to False for full organization analysis

# TEST_LIMIT: Number of groups to analyze when TEST_MODE is True
# Useful for validating the script works before running on all groups
TEST_LIMIT = 10   # Number of groups to analyze in test mode

# OUTPUT_FOLDER: Name of the folder where hosted tables will be published
# If the folder doesn't exist, it will be created automatically
OUTPUT_FOLDER = "Group Analytics"

# Table name: Name for the hosted table
# Change this if you want a different table name
GROUP_SNAPSHOT_TABLE = "Group_Snapshot"

# RECENT_DAYS_THRESHOLD: Number of days to consider for "recent" activity
# Used to calculate is_recent, is_active, and active_members metrics
# Adjust based on your organization's activity patterns
RECENT_DAYS_THRESHOLD = 90

print("=" * 60)
print("GROUP SNAPSHOT NOTEBOOK v1.2")
print("=" * 60)
print(f"\nConfiguration:")
print(f"  - Test Mode: {TEST_MODE}")
if TEST_MODE:
    print(f"  - Test Limit: {TEST_LIMIT} groups")
else:
    print(f"  - Analyzing ALL groups in organization")
print(f"  - Output Folder: {OUTPUT_FOLDER}")
print(f"  - Recent Days Threshold: {RECENT_DAYS_THRESHOLD} days")

# =============================================================================
# CELL 2: AUTHENTICATION AND GIS CONNECTION
# =============================================================================

print("\n" + "=" * 60)
print("CONNECTING TO GIS")
print("=" * 60)

# Connect using built-in notebook authentication
gis = GIS("home")

# Get portal information for dynamic URL generation
portal_url = gis.url
org_id = gis.properties.get('id', '')
current_user = gis.users.me.username

# Determine if ArcGIS Online or Enterprise for group link generation
is_agol = "arcgis.com" in portal_url.lower()

if is_agol:
    base_group_url = "https://www.arcgis.com/home/group.html?id="
    print(f"\n✓ Connected to ArcGIS Online")
else:
    # For Enterprise, construct the group URL from portal URL
    base_group_url = f"{portal_url}/home/group.html?id="
    print(f"\n✓ Connected to ArcGIS Enterprise")

print(f"  - Portal URL: {portal_url}")
print(f"  - Organization ID: {org_id}")
print(f"  - User: {current_user}")
print(f"  - Base Group URL: {base_group_url}")

# =============================================================================
# CELL 3: HELPER FUNCTIONS
# =============================================================================
# This cell defines all helper functions used throughout the notebook.
# Functions are organized by purpose:
#   - Data conversion (timestamps, dates)
#   - Group analysis (type, sharing level, Hub/Site detection)
#   - Content analysis (Living Atlas detection)
#   - User information (full name lookup)
#   - Folder and table management
# =============================================================================

print("\n" + "=" * 60)
print("LOADING HELPER FUNCTIONS")
print("=" * 60)


def convert_timestamp_to_date(timestamp_ms):
    """Convert millisecond timestamp to date object (no time component)"""
    if timestamp_ms is None or timestamp_ms == -1:
        return None
    try:
        dt = datetime.datetime.fromtimestamp(timestamp_ms / 1000)
        return dt.date()  # Return date only, no timestamp
    except (ValueError, OSError, TypeError):
        return None


def days_since(timestamp_ms):
    """Calculate days since a given timestamp"""
    if timestamp_ms is None or timestamp_ms == -1:
        return None
    try:
        dt = datetime.datetime.fromtimestamp(timestamp_ms / 1000)
        delta = datetime.datetime.now() - dt
        return delta.days
    except (ValueError, OSError, TypeError):
        return None


def get_item_last_data_update(item):
    """
    Get the last data update date for an item.
    
    For Feature Services and Feature Layers, this retrieves the actual last edit
    date from the service's editingInfo property, which reflects when features
    were last added, updated, or deleted.
    
    For other item types, falls back to the item's modified timestamp.
    
    Args:
        item: ArcGIS Item object
        
    Returns:
        datetime.date: Date of last data update, or None if not available
    """
    try:
        item_type = safe_get(item, 'type', '')
        
        # For Feature Services/Layers, try to get the actual last edit date
        if item_type in ['Feature Service', 'Feature Layer', 'Feature Layer Collection', 'Table']:
            try:
                # Get the FeatureLayerCollection
                flc = FeatureLayerCollection.fromitem(item)
                
                # Check for editingInfo at the service level
                if flc.properties and hasattr(flc.properties, 'editingInfo'):
                    editing_info = flc.properties.editingInfo
                    last_edit_ts = None
                    
                    # Try lastEditDate first
                    if hasattr(editing_info, 'lastEditDate') and editing_info.lastEditDate:
                        last_edit_ts = editing_info.lastEditDate
                    elif isinstance(editing_info, dict) and editing_info.get('lastEditDate'):
                        last_edit_ts = editing_info.get('lastEditDate')
                    
                    if last_edit_ts:
                        return convert_timestamp_to_date(last_edit_ts)
                
                # Check individual layers/tables for edit dates
                all_edit_dates = []
                
                # Check layers
                if flc.layers:
                    for layer in flc.layers:
                        try:
                            if hasattr(layer.properties, 'editingInfo'):
                                layer_edit_info = layer.properties.editingInfo
                                if hasattr(layer_edit_info, 'lastEditDate') and layer_edit_info.lastEditDate:
                                    all_edit_dates.append(layer_edit_info.lastEditDate)
                                elif isinstance(layer_edit_info, dict) and layer_edit_info.get('lastEditDate'):
                                    all_edit_dates.append(layer_edit_info.get('lastEditDate'))
                        except:
                            pass
                
                # Check tables
                if flc.tables:
                    for table in flc.tables:
                        try:
                            if hasattr(table.properties, 'editingInfo'):
                                table_edit_info = table.properties.editingInfo
                                if hasattr(table_edit_info, 'lastEditDate') and table_edit_info.lastEditDate:
                                    all_edit_dates.append(table_edit_info.lastEditDate)
                                elif isinstance(table_edit_info, dict) and table_edit_info.get('lastEditDate'):
                                    all_edit_dates.append(table_edit_info.get('lastEditDate'))
                        except:
                            pass
                
                # Return the most recent edit date across all layers/tables
                if all_edit_dates:
                    return convert_timestamp_to_date(max(all_edit_dates))
                    
            except Exception as e:
                # If we can't access the service, fall back to modified date
                pass
        
        # Fall back to item's modified timestamp for non-feature services
        # or if editingInfo is not available
        modified_ts = safe_get(item, 'modified', None)
        if modified_ts:
            return convert_timestamp_to_date(modified_ts)
        
        return None
        
    except Exception:
        # Last resort: try to get modified date
        try:
            modified_ts = safe_get(item, 'modified', None)
            if modified_ts:
                return convert_timestamp_to_date(modified_ts)
        except:
            pass
        return None


def get_group_capabilities_string(group):
    """Get group capabilities as a comma-separated string"""
    try:
        capabilities = group.get('capabilities', [])
        if isinstance(capabilities, list):
            return ", ".join(capabilities)
        return str(capabilities) if capabilities else ""
    except Exception:
        return ""


def get_group_type(group):
    """Determine the type of group - combines capabilities and collaboration type"""
    try:
        type_keywords = group.get('typeKeywords', [])
        capabilities = group.get('capabilities', [])
        
        # Check for Shared Update capability
        is_shared_update = False
        if capabilities:
            cap_str = str(capabilities).lower()
            if 'updateitemcontrol' in cap_str or 'shared update' in cap_str:
                is_shared_update = True
        if 'Shared Update' in type_keywords:
            is_shared_update = True
        
        # Check for collaboration types
        is_partnered = False
        is_distributed = False
        
        if group.get('isPartnerCollab'):
            is_partnered = True
        if group.get('isDistributedCollab'):
            is_distributed = True
        
        # Additional checks in typeKeywords
        if 'Partner Collaboration' in type_keywords:
            is_partnered = True
        if 'Distributed Collaboration' in type_keywords:
            is_distributed = True
        
        # Build combined type string
        types = []
        
        if is_partnered:
            types.append("Partnered Collaboration")
        if is_distributed:
            types.append("Distributed Collaboration")
        if is_shared_update:
            types.append("Shared Update")
        
        # If no special types, it's Standard
        if not types:
            return "Standard"
        
        return ", ".join(types)
        
    except Exception:
        return "Standard"


def get_group_sharing_level(group):
    """Get the sharing level of the group (Private, Organization, Public)"""
    try:
        access = group.get('access', 'private')
        if access == 'public':
            return "Public"
        elif access == 'org':
            return "Organization"
        else:
            return "Private"
    except Exception:
        return "Private"


def is_hub_group(group):
    """
    Check if group is part of ArcGIS Hub (ArcGIS Online).
    
    Identifies Hub groups by checking for specific tags:
    - 'Hub Group'
    - 'Hub Content Group'
    - 'Hub Site Group'
    - 'Hub Initiative Group'
    
    Args:
        group: ArcGIS Group object
        
    Returns:
        bool: True if group is a Hub group, False otherwise
    """
    try:
        tags = safe_get(group, 'tags', []) or []
        # Convert to lowercase for case-insensitive matching
        tags_lower = [tag.lower() for tag in tags]
        
        hub_indicators = [
            'hub group',
            'hub content group',
            'hub site group',
            'hub initiative group'
        ]
        
        for indicator in hub_indicators:
            if indicator in tags_lower:
                return True
        
        return False
    except Exception:
        return False


def is_site_group(group):
    """
    Check if group is part of ArcGIS Enterprise Sites.
    
    Identifies Site groups by checking for specific tags:
    - 'Sites'
    - 'Sites Group'
    - 'Sites Content Group'
    - 'Sites Core Team Group'
    
    Args:
        group: ArcGIS Group object
        
    Returns:
        bool: True if group is a Site group, False otherwise
    """
    try:
        tags = safe_get(group, 'tags', []) or []
        # Convert to lowercase for case-insensitive matching
        tags_lower = [tag.lower() for tag in tags]
        
        site_indicators = [
            'sites',
            'sites group',
            'sites content group',
            'sites core team group'
        ]
        
        for indicator in site_indicators:
            if indicator in tags_lower:
                return True
        
        return False
    except Exception:
        return False


def is_living_atlas_item(item):
    """
    Check if an item is from the Living Atlas (owned by official Esri accounts).
    
    Living Atlas items are owned by specific Esri system accounts, NOT regular
    users who happen to have 'esri' in their email/username. We check for exact
    owner name matches or specific prefixes used by Esri's content accounts.
    
    Args:
        item: ArcGIS Item object
        
    Returns:
        bool: True if item is from Living Atlas/Esri system accounts, False otherwise
    """
    try:
        owner = safe_get(item, 'owner', '') or ''
        owner_lower = owner.lower()
        
        # Exact Esri Living Atlas/system account names
        # These are the actual account names that own Living Atlas content
        esri_exact_accounts = [
            'esri',
            'esri_livingatlas',
            'esri_demographics',
            'esri_boundaries',
            'esri_basemaps',
            'esri_landscape',
            'esri_imagery',
            'esri_elevation',
            'esri_vector',
            'esri_cartography',
            'esri_hydro',
            'esri_apps',
            'esri_media',
            'esri_3d',
            'esri_livefeeds',
            'esri_analytics',
        ]
        
        # Check for exact match (case-insensitive)
        if owner_lower in esri_exact_accounts:
            return True
        
        # Check for Esri system account patterns (accounts that start with esri_)
        # but NOT user accounts like 'username@esri.com_orgid'
        if owner_lower.startswith('esri_') and '@' not in owner_lower:
            return True
        
        return False
    except Exception:
        return False


def get_user_full_name(username, user_info_dict):
    """
    Get the full name (first and last) for a user.
    
    Args:
        username: Username to look up
        user_info_dict: Dictionary containing user information
        
    Returns:
        str: Full name if available, otherwise username
    """
    try:
        if username in user_info_dict:
            full_name = user_info_dict[username].get('full_name', '')
            if full_name and full_name != username:
                return full_name
        return username
    except Exception:
        return username


def get_folder_name(folder):
    """
    Safely extract folder name from various folder object types.
    
    Handles:
    - String folder names
    - Dictionary folder objects
    - Folder objects with title/name properties
    - Folder objects with title/name methods
    
    Args:
        folder: Folder object, dict, or string
        
    Returns:
        str: Folder name or None if not determinable
    """
    if folder is None:
        return None
    
    if isinstance(folder, str):
        return folder
    
    if isinstance(folder, dict):
        return folder.get('title', folder.get('name', ''))
    
    # Try to get title/name as property first, then as method
    try:
        if hasattr(folder, 'title'):
            val = folder.title
            return val() if callable(val) else val
        elif hasattr(folder, 'name'):
            val = folder.name
            return val() if callable(val) else val
        else:
            return str(folder)
    except:
        try:
            return str(folder)
        except:
            return None


def safe_get(obj, key, default=None):
    """Safely get a value from a dictionary or object"""
    try:
        if hasattr(obj, key):
            return getattr(obj, key)
        elif isinstance(obj, dict):
            return obj.get(key, default)
        return default
    except Exception:
        return default


def truncate_string(value, max_length, add_ellipsis=True):
    """
    Safely truncate a string to a maximum length.
    
    Args:
        value: Value to truncate (will be converted to string)
        max_length: Maximum allowed length
        add_ellipsis: If True, add "..." to indicate truncation (default True)
        
    Returns:
        str: Truncated string, or empty string if value is None/empty
    """
    if value is None:
        return ""
    
    str_value = str(value)
    
    if len(str_value) <= max_length:
        return str_value
    
    if add_ellipsis and max_length > 3:
        return str_value[:max_length - 3] + "..."
    else:
        return str_value[:max_length]


# Field length constants for hosted tables
# These should match the field lengths defined when tables were first created
# Default is 256 chars for string fields in ArcGIS hosted tables
FIELD_LENGTH_DEFAULT = 256

FIELD_LENGTHS = {
    # Group_Snapshot string fields
    'group_id': 256,
    'group_title': 256,
    'group_summary': 256,
    'group_description': 256,
    'group_tags': 256,
    'group_owner': 256,
    'group_owner_name': 256,
    'group_type': 256,
    'group_sharing_level': 256,
    'group_link': 256,
}


def get_or_create_folder(gis, folder_name):
    """
    Get existing folder or create new one if it doesn't exist.
    
    Uses gis.content.folders API (2.3.0+) with fallback to legacy methods.
    Returns folder name string which works with both Folder.add() and 
    gis.content.add(folder=) parameter.
    
    Args:
        gis: GIS connection object
        folder_name: Name of folder to get or create
        
    Returns:
        folder_name string (works universally across API versions)
    """
    try:
        # Method 1: Try gis.content.folders.get() (API 2.3.0+)
        try:
            existing_folder = gis.content.folders.get(folder=folder_name)
            if existing_folder:
                print(f"  ✓ Found existing folder: {folder_name}")
                return folder_name  # Return string for compatibility
        except Exception:
            pass  # Folder doesn't exist or method not available
        
        # Method 2: Check gis.users.me.folders list
        try:
            user_folders = gis.users.me.folders
            for folder in user_folders:
                # Use helper function to extract folder name
                check_name = get_folder_name(folder)
                
                if check_name == folder_name:
                    print(f"  ✓ Found existing folder: {folder_name}")
                    return folder_name  # Return string for compatibility
        except Exception:
            pass
        
        # Folder doesn't exist, create it
        print(f"  Creating new folder: {folder_name}")
        
        # Try new API first (gis.content.folders.create)
        try:
            new_folder = gis.content.folders.create(folder_name)
            print(f"  ✓ Created folder: {folder_name}")
            return folder_name  # Return string for compatibility
        except Exception as create_error:
            error_msg = str(create_error).lower()
            
            # Check if error is because folder already exists
            if "not available" in error_msg or "already exists" in error_msg:
                print(f"  Folder already exists: {folder_name}")
                return folder_name
            
            # Try legacy method
            try:
                gis.content.create_folder(folder_name)
                print(f"  ✓ Created folder (legacy): {folder_name}")
                return folder_name
            except Exception as legacy_error:
                if "not available" in str(legacy_error).lower():
                    print(f"  Folder already exists: {folder_name}")
                    return folder_name
                raise legacy_error
                
    except Exception as e:
        print(f"  ⚠ Folder operation warning: {str(e)}")
        # Return folder name as fallback
        return folder_name


def find_existing_table(gis, table_name):
    """Find an existing hosted table by name - Improved search"""
    try:
        # Method 1: Search by exact title and owner
        search_query = f'title:"{table_name}" AND owner:{current_user} AND type:"Feature Service"'
        results = gis.content.search(query=search_query, max_items=100)
        
        for item in results:
            if item.title == table_name and item.owner == current_user:
                print(f"  ✓ Found existing table: {table_name} (ID: {item.id})")
                return item
        
        # Method 2: Search without quotes (in case of search issues)
        search_query2 = f'title:{table_name} owner:{current_user} type:Feature Service'
        results2 = gis.content.search(query=search_query2, max_items=100)
        
        for item in results2:
            if item.title == table_name and item.owner == current_user:
                print(f"  ✓ Found existing table (method 2): {table_name} (ID: {item.id})")
                return item
        
        # Method 3: List user's items and search manually
        user_items = gis.users.me.items(max_items=1000)
        for item in user_items:
            if item.title == table_name and item.type == "Feature Service":
                print(f"  ✓ Found existing table (method 3): {table_name} (ID: {item.id})")
                return item
        
        print(f"  ℹ No existing table found: {table_name}")
        return None
        
    except Exception as e:
        print(f"  ⚠ Search warning: {str(e)}")
        return None


def find_source_csv_item(gis, table_name):
    """
    Find the source CSV item for a hosted table.
    
    The CSV item is stored in user's content with naming convention:
    {table_name}_source
    
    Args:
        gis: GIS connection object
        table_name: Name of the table
        
    Returns:
        Item object if found, None otherwise
    """
    try:
        csv_title = f"{table_name}_source"
        
        # Search for existing CSV item
        search_query = f'title:"{csv_title}" AND owner:{current_user} AND type:"CSV"'
        results = gis.content.search(query=search_query, max_items=50)
        
        for item in results:
            if item.title == csv_title and item.owner == current_user:
                print(f"    ✓ Found existing source CSV: {csv_title} (ID: {item.id})")
                return item
        
        # Try without quotes
        search_query2 = f'title:{csv_title} owner:{current_user} type:CSV'
        results2 = gis.content.search(query=search_query2, max_items=50)
        
        for item in results2:
            if item.title == csv_title and item.owner == current_user:
                print(f"    ✓ Found existing source CSV: {csv_title} (ID: {item.id})")
                return item
        
        return None
        
    except Exception as e:
        print(f"    ⚠ Error searching for source CSV: {str(e)[:50]}")
        return None


def update_source_csv_item(gis, csv_item, dataframe, folder=None):
    """
    Update an existing CSV item with new data.
    
    Args:
        gis: GIS connection object
        csv_item: Existing CSV Item to update
        dataframe: pandas DataFrame with new data
        folder: Optional folder to ensure item is in
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Prepare data
        df_copy = dataframe.copy()
        
        # Convert all date/datetime columns to date-only strings
        for col in df_copy.columns:
            # Check for pandas datetime columns
            if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
                df_copy[col] = df_copy[col].apply(
                    lambda x: x.strftime('%Y/%m/%d') if pd.notna(x) else ''
                )
            # Check for object columns that might contain date/datetime objects
            elif df_copy[col].dtype == 'object':
                # Check first non-null value to see if it's a date type
                non_null = df_copy[col].dropna()
                if len(non_null) > 0:
                    first_val = non_null.iloc[0]
                    if isinstance(first_val, (datetime.date, datetime.datetime)):
                        df_copy[col] = df_copy[col].apply(
                            lambda x: x.strftime('%Y/%m/%d') if x is not None and pd.notna(x) else ''
                        )
        
        df_copy = df_copy.fillna('')
        
        # Save to temporary local file
        temp_csv_path = f"/arcgis/home/{csv_item.title.replace(' ', '_')}_temp.csv"
        df_copy.to_csv(temp_csv_path, index=False)
        
        # Update the item with new data
        update_result = csv_item.update(data=temp_csv_path)
        
        # Clean up temp file
        try:
            if os.path.exists(temp_csv_path):
                os.remove(temp_csv_path)
        except:
            pass
        
        if update_result:
            print(f"    ✓ Updated source CSV item with new data")
            return True
        else:
            print(f"    ✗ Failed to update source CSV item")
            return False
            
    except Exception as e:
        print(f"    ✗ Error updating source CSV: {str(e)}")
        return False


def create_source_csv_item(gis, table_name, dataframe, folder=None):
    """
    Create a new CSV item in user's content to serve as source for hosted table.
    
    Uses Folder.add() method (API 2.3.0+) with .result() to get the Item.
    Falls back to gis.content.add() with folder parameter if needed.
    
    Args:
        gis: GIS connection object
        table_name: Name of the table
        dataframe: pandas DataFrame with data
        folder: Optional folder object or name to place the item in
        
    Returns:
        Item object if successful, None otherwise
    """
    try:
        # Prepare data
        df_copy = dataframe.copy()
        
        # Convert all date/datetime columns to date-only strings
        for col in df_copy.columns:
            # Check for pandas datetime columns
            if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
                df_copy[col] = df_copy[col].apply(
                    lambda x: x.strftime('%Y/%m/%d') if pd.notna(x) else ''
                )
            # Check for object columns that might contain date/datetime objects
            elif df_copy[col].dtype == 'object':
                # Check first non-null value to see if it's a date type
                non_null = df_copy[col].dropna()
                if len(non_null) > 0:
                    first_val = non_null.iloc[0]
                    if isinstance(first_val, (datetime.date, datetime.datetime)):
                        df_copy[col] = df_copy[col].apply(
                            lambda x: x.strftime('%Y/%m/%d') if x is not None and pd.notna(x) else ''
                        )
        
        df_copy = df_copy.fillna('')
        
        # Save to temporary local file
        csv_filename = f"{table_name.replace(' ', '_')}.csv"
        temp_csv_path = f"/arcgis/home/{csv_filename}"
        df_copy.to_csv(temp_csv_path, index=False)
        
        # Create item properties
        csv_title = f"{table_name}_source"
        item_props = {
            "title": csv_title,
            "type": "CSV",
            "description": f"Source CSV file for {table_name} hosted table. DO NOT DELETE - required for overwrite operations.",
            "tags": "source, group_analytics, do_not_delete"
        }
        
        # Get folder name using helper function
        folder_name = get_folder_name(folder)
        
        csv_item = None
        
        # Method 1: Try using Folder.add() (API 2.3.0+)
        try:
            if folder_name:
                target_folder = gis.content.folders.get(folder=folder_name)
                if target_folder:
                    # Folder.add() returns a Future, call .result() to get the Item
                    add_result = target_folder.add(item_properties=item_props, file=temp_csv_path)
                    csv_item = add_result.result() if hasattr(add_result, 'result') else add_result
                    print(f"    ✓ Created source CSV in folder: {csv_title}")
        except Exception as folder_add_error:
            print(f"    ⚠ Folder.add() not available: {str(folder_add_error)[:40]}")
        
        # Method 2: Fallback to gis.content.add() with folder parameter
        if csv_item is None:
            try:
                # gis.content.add has a folder parameter to add directly to folder
                csv_item = gis.content.add(
                    item_properties=item_props, 
                    data=temp_csv_path,
                    folder=folder_name  # Add directly to folder
                )
                if folder_name:
                    print(f"    ✓ Created source CSV in folder (legacy): {csv_title}")
                else:
                    print(f"    ✓ Created source CSV item: {csv_title}")
            except Exception as add_error:
                print(f"    ✗ Failed to add CSV item: {str(add_error)[:50]}")
                return None
        
        # Clean up temp file
        try:
            if os.path.exists(temp_csv_path):
                os.remove(temp_csv_path)
        except:
            pass
        
        return csv_item
        
    except Exception as e:
        print(f"    ✗ Error creating source CSV item: {str(e)}")
        return None


def update_existing_table(item, dataframe, folder=None):
    """
    Update existing hosted table by deleting all features and appending new data.
    
    This method:
    1. Deletes all existing features using delete_features()
    2. Waits briefly for deletion to propagate
    3. Updates the source CSV item with new data
    4. Appends new data using the append() method
    5. Falls back to edit_features() if append fails
    
    This preserves the item ID, URL, and service configuration.
    
    Note: Data should be validated for field lengths BEFORE calling this function
    to avoid append failures. The edit_features fallback includes truncation as
    a safety net.
    
    Args:
        item: Existing ArcGIS Item to update
        dataframe: pandas DataFrame with new data
        folder: Optional folder where source CSV should be stored
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        print(f"    Attempting to update table...")
        
        # Get the FeatureLayerCollection
        flc = FeatureLayerCollection.fromitem(item)
        
        # Determine if it's a table or layer
        if flc.tables and len(flc.tables) > 0:
            target_layer = flc.tables[0]
            print(f"    Found table in feature service")
        elif flc.layers and len(flc.layers) > 0:
            target_layer = flc.layers[0]
            print(f"    Found layer in feature service")
        else:
            print(f"    ✗ No tables or layers found in feature service")
            return False
        
        # Step 1: Delete all existing features
        try:
            delete_result = target_layer.delete_features(where="1=1")
            print(f"    ✓ Deleted existing features")
            
            # Brief wait for deletion to propagate
            time.sleep(2)
            
        except Exception as del_error:
            print(f"    ✗ Could not delete existing features: {str(del_error)[:50]}")
            return False
        
        # Step 2: Find or create source CSV item in user's content
        csv_item = find_source_csv_item(gis, item.title)
        
        if csv_item:
            # Update existing CSV item with new data
            if not update_source_csv_item(gis, csv_item, dataframe, folder):
                print(f"    ✗ Could not update source CSV item")
                return False
        else:
            # Create new source CSV item
            print(f"    Source CSV not found, creating new one...")
            csv_item = create_source_csv_item(gis, item.title, dataframe, folder)
            if not csv_item:
                print(f"    ✗ Could not create source CSV item")
                return False
        
        # Step 3: Append the data using the CSV item
        try:
            print(f"    Appending data from CSV...")
            
            append_result = target_layer.append(
                item_id=csv_item.id,
                upload_format="csv",
                source_info={"locationType": "none"}
            )
            
            if append_result is not None:
                print(f"    ✓ Appended new data to table")
                print(f"    ✓ Source CSV retained in content: {csv_item.title}")
                return True
            else:
                print(f"    ⚠ Append returned None, trying fallback...")
                
        except Exception as append_error:
            error_msg = str(append_error)
            print(f"    ⚠ Append failed: {error_msg[:80]}")
            print(f"    Trying edit_features fallback...")
        
        # Step 4: Append failed - try edit_features as fallback
        # This includes field length validation/truncation as a safety net
        try:
            success = add_features_in_batches(target_layer, dataframe)
            if success:
                print(f"    ✓ Added features using edit_features method")
                return True
            else:
                print(f"    ✗ edit_features fallback also failed")
                return False
        except Exception as edit_error:
            print(f"    ✗ edit_features fallback failed: {str(edit_error)[:80]}")
            return False
        
    except Exception as e:
        print(f"    ✗ Error updating table: {str(e)}")
        return False


def add_features_in_batches(layer, dataframe, batch_size=50):
    """
    Add features to a layer using edit_features in batches.
    
    This method is more robust than append() when there are schema mismatches,
    as it only sends the fields that exist in the target layer.
    
    Args:
        layer: Target FeatureLayer or Table
        dataframe: pandas DataFrame with data to add
        batch_size: Number of records per batch (default 50)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get the fields from the layer with their types AND lengths
        layer_field_info = {}
        for f in layer.properties.fields:
            field_name = f['name'].lower()
            if field_name not in ['objectid', 'fid', 'globalid']:
                layer_field_info[field_name] = {
                    'name': f['name'], 
                    'type': f.get('type', 'esriFieldTypeString'),
                    'length': f.get('length', 256)  # Default to 256 if not specified
                }
        
        print(f"    Target layer has {len(layer_field_info)} editable fields")
        
        # Show field lengths for string fields (debugging)
        string_fields = {k: v for k, v in layer_field_info.items() if v['type'] == 'esriFieldTypeString'}
        if string_fields:
            print(f"    String field lengths:")
            for fname, finfo in list(string_fields.items())[:5]:  # Show first 5
                print(f"      - {finfo['name']}: max {finfo['length']} chars")
        
        # Prepare records - only include fields that exist in the layer
        df_copy = dataframe.copy()
        
        # Convert all date/datetime columns to date-only strings
        for col in df_copy.columns:
            # Check for pandas datetime columns
            if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
                df_copy[col] = df_copy[col].apply(
                    lambda x: x.strftime('%Y/%m/%d') if pd.notna(x) else None
                )
            # Check for object columns that might contain date/datetime objects
            elif df_copy[col].dtype == 'object':
                non_null = df_copy[col].dropna()
                if len(non_null) > 0:
                    first_val = non_null.iloc[0]
                    if isinstance(first_val, (datetime.date, datetime.datetime)):
                        df_copy[col] = df_copy[col].apply(
                            lambda x: x.strftime('%Y/%m/%d') if x is not None and pd.notna(x) else None
                        )
        
        # Convert boolean columns to strings (ArcGIS often stores bools as strings)
        for col in df_copy.columns:
            if df_copy[col].dtype == 'bool':
                df_copy[col] = df_copy[col].apply(lambda x: str(x) if pd.notna(x) else None)
        
        # Replace NaN with None for JSON serialization
        df_copy = df_copy.where(pd.notnull(df_copy), None)
        
        # Build features list - only include matching fields
        all_features = []
        df_columns_lower = {col.lower(): col for col in df_copy.columns}
        truncation_warnings = []
        
        for row_idx, row in df_copy.iterrows():
            attributes = {}
            for layer_field_lower, field_info in layer_field_info.items():
                if layer_field_lower in df_columns_lower:
                    df_col = df_columns_lower[layer_field_lower]
                    value = row[df_col]
                    
                    # Convert numpy types to Python types
                    if hasattr(value, 'item'):
                        value = value.item()
                    
                    # Handle None/NaN
                    if pd.isna(value):
                        value = None
                    
                    # For string fields: convert to string and TRUNCATE to field length
                    if value is not None and field_info['type'] == 'esriFieldTypeString':
                        value = str(value)
                        max_len = field_info.get('length', 256)
                        if len(value) > max_len:
                            if len(truncation_warnings) < 5:
                                truncation_warnings.append(
                                    f"Row {row_idx}, {field_info['name']}: {len(value)} chars -> {max_len}"
                                )
                            value = value[:max_len]
                    
                    attributes[field_info['name']] = value
            
            if attributes:  # Only add if we have some attributes
                all_features.append({"attributes": attributes})
        
        if not all_features:
            print(f"    ✗ No matching fields found between DataFrame and layer")
            return False
        
        # Show truncation warnings if any
        if truncation_warnings:
            print(f"    ⚠ Truncated {len(truncation_warnings)}+ values to fit field lengths:")
            for warn in truncation_warnings[:3]:
                print(f"      - {warn}")
        
        print(f"    Adding {len(all_features)} features in batches of {batch_size}...")
        
        # Add features in batches
        total_added = 0
        failed_batches = 0
        all_errors = []
        
        for i in range(0, len(all_features), batch_size):
            batch = all_features[i:i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(all_features) + batch_size - 1) // batch_size
            
            try:
                result = layer.edit_features(adds=batch)
                
                # Check result
                if result and 'addResults' in result:
                    success_count = 0
                    batch_errors = []
                    
                    for idx, r in enumerate(result['addResults']):
                        if r.get('success', False):
                            success_count += 1
                        else:
                            # Capture error details
                            error_info = r.get('error', {})
                            error_code = error_info.get('code', 'Unknown')
                            error_desc = error_info.get('description', 'No description')
                            batch_errors.append(f"Record {i + idx}: Code {error_code} - {error_desc[:100]}")
                    
                    total_added += success_count
                    
                    if success_count < len(batch):
                        print(f"    ⚠ Batch {batch_num}/{total_batches}: {success_count}/{len(batch)} succeeded")
                        # Show first few errors for this batch
                        if batch_errors:
                            all_errors.extend(batch_errors[:3])  # Keep first 3 errors per batch
                            if len(batch_errors) > 0:
                                print(f"      First error: {batch_errors[0][:120]}")
                    elif batch_num % 5 == 0 or batch_num == total_batches:
                        print(f"    Batch {batch_num}/{total_batches}: {success_count} added")
                else:
                    failed_batches += 1
                    print(f"    ⚠ Batch {batch_num}/{total_batches}: No result returned")
                    
                # Small delay between batches to avoid rate limiting
                if i + batch_size < len(all_features):
                    time.sleep(0.5)
                    
            except Exception as batch_error:
                failed_batches += 1
                error_str = str(batch_error)
                print(f"    ⚠ Batch {batch_num}/{total_batches} failed: {error_str[:80]}")
                all_errors.append(f"Batch {batch_num} exception: {error_str[:100]}")
                
                # If batch fails completely, try one-by-one to find the bad record
                if batch_size > 1 and len(batch) > 1:
                    print(f"      Retrying batch {batch_num} one record at a time...")
                    for single_idx, single_feature in enumerate(batch):
                        try:
                            single_result = layer.edit_features(adds=[single_feature])
                            if single_result and 'addResults' in single_result:
                                if single_result['addResults'][0].get('success', False):
                                    total_added += 1
                                else:
                                    err = single_result['addResults'][0].get('error', {})
                                    print(f"      Record {i + single_idx} failed: {err.get('description', 'Unknown')[:60]}")
                        except Exception as single_err:
                            print(f"      Record {i + single_idx} exception: {str(single_err)[:60]}")
                        time.sleep(0.1)
                continue
        
        print(f"    Total features added: {total_added}/{len(all_features)}")
        
        # Show summary of errors if any
        if all_errors and total_added < len(all_features):
            print(f"    Error summary (first few):")
            for err in all_errors[:5]:
                print(f"      - {err[:150]}")
        
        if total_added == len(all_features):
            return True
        elif total_added > 0:
            print(f"    ⚠ Partial success - {len(all_features) - total_added} features failed")
            return True  # Consider partial success as success
        else:
            return False
            
    except Exception as e:
        print(f"    ✗ Error in batch add: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def create_new_table(gis, table_name, dataframe, folder, description=""):
    """
    Create a brand new hosted table from DataFrame.
    
    The source CSV is stored as an item in user's content (not deleted).
    This is required for future overwrite operations.
    Uses Folder.add() method (API 2.3.0+) with .result() when available.
    Falls back to gis.content.add() with folder parameter.
    
    Naming convention:
    - Hosted table: {table_name}
    - Source CSV: {table_name}_source
    
    Args:
        gis: GIS connection object
        table_name: Name for the new table
        dataframe: pandas DataFrame with data to publish
        folder: Folder to move the published items to
        description: Optional description for the item
        
    Returns:
        Published Item object or None if failed
    """
    try:
        print(f"    Creating new hosted table...")
        
        # Prepare DataFrame
        df_copy = dataframe.copy()
        
        # Convert all date/datetime columns to date-only strings
        for col in df_copy.columns:
            # Check for pandas datetime columns
            if pd.api.types.is_datetime64_any_dtype(df_copy[col]):
                df_copy[col] = df_copy[col].apply(
                    lambda x: x.strftime('%Y/%m/%d') if pd.notna(x) else ''
                )
            # Check for object columns that might contain date/datetime objects
            elif df_copy[col].dtype == 'object':
                # Check first non-null value to see if it's a date type
                non_null = df_copy[col].dropna()
                if len(non_null) > 0:
                    first_val = non_null.iloc[0]
                    if isinstance(first_val, (datetime.date, datetime.datetime)):
                        df_copy[col] = df_copy[col].apply(
                            lambda x: x.strftime('%Y/%m/%d') if x is not None and pd.notna(x) else ''
                        )
        
        # Replace NaN with empty string
        df_copy = df_copy.fillna('')
        
        # Save to temporary local file
        csv_filename = f"{table_name.replace(' ', '_')}.csv"
        temp_csv_path = f"/arcgis/home/{csv_filename}"
        df_copy.to_csv(temp_csv_path, index=False)
        print(f"    ✓ Saved temporary CSV: {csv_filename}")
        
        # Get folder name using helper function
        folder_name = get_folder_name(folder)
        target_folder = None
        
        if folder_name:
            # Try to get folder object for Folder.add()
            try:
                target_folder = gis.content.folders.get(folder=folder_name)
            except:
                target_folder = None
        
        # Create source CSV item in user's content
        csv_title = f"{table_name}_source"
        item_props = {
            "title": csv_title,
            "type": "CSV",
            "description": f"Source CSV file for {table_name} hosted table. DO NOT DELETE - required for overwrite operations.",
            "tags": "source, group_analytics, do_not_delete"
        }
        
        csv_item = None
        
        # Method 1: Try using Folder.add() (API 2.3.0+)
        try:
            if target_folder:
                add_result = target_folder.add(item_properties=item_props, file=temp_csv_path)
                csv_item = add_result.result() if hasattr(add_result, 'result') else add_result
                print(f"    ✓ Created source CSV in folder: {csv_title}")
        except Exception as folder_error:
            print(f"    ⚠ Folder.add() issue: {str(folder_error)[:40]}")
        
        # Method 2: Fallback to gis.content.add() with folder parameter
        if csv_item is None:
            csv_item = gis.content.add(
                item_properties=item_props, 
                data=temp_csv_path,
                folder=folder_name  # Add directly to folder
            )
            if folder_name:
                print(f"    ✓ Created source CSV in folder (legacy): {csv_title}")
            else:
                print(f"    ✓ Created source CSV item: {csv_title}")
        
        # Analyze the CSV
        analyze_result = gis.content.analyze(item=csv_item, file_type='csv')
        pub_params = analyze_result.get('publishParameters', {})
        
        # Set publish parameters - use consistent service name
        service_name = f"{table_name.replace(' ', '_').replace('-', '_')}"
        pub_params['name'] = service_name
        pub_params['locationType'] = 'none'  # Non-spatial table
        
        print(f"    Publishing with service name: {service_name}")
        
        # Publish as hosted table
        published_item = csv_item.publish(publish_parameters=pub_params)
        print(f"    ✓ Published hosted table")
        
        # Update title and description
        published_item.update(item_properties={
            "title": table_name,
            "description": description if description else f"Group Analytics - {table_name}"
        })
        
        # Move published table to folder if not already there
        # (Published items go to root by default, need to move them)
        if folder_name:
            move_success = False
            
            # Method 1: Try move with folder keyword argument
            try:
                result = published_item.move(folder=folder_name)
                if result:
                    move_success = True
                    print(f"    ✓ Moved table to folder: {folder_name}")
            except Exception as e1:
                pass
            
            # Method 2: Try move with positional argument
            if not move_success:
                try:
                    result = published_item.move(folder_name)
                    if result:
                        move_success = True
                        print(f"    ✓ Moved table to folder: {folder_name}")
                except Exception as e2:
                    pass
            
            # Method 3: Try using folder ID
            if not move_success:
                try:
                    folder_obj = gis.content.folders.get(folder=folder_name)
                    if folder_obj:
                        folder_id = getattr(folder_obj, 'id', None) or getattr(folder_obj, 'folderId', None)
                        if folder_id:
                            result = published_item.move(folder=folder_id)
                            if result:
                                move_success = True
                                print(f"    ✓ Moved table to folder: {folder_name}")
                except Exception as e3:
                    pass
            
            if not move_success:
                print(f"    ⚠ Note: Table published to root folder (manual move may be needed)")
                print(f"      You can move it to '{folder_name}' folder via the portal UI")
        
        # Clean up temporary local file
        try:
            if os.path.exists(temp_csv_path):
                os.remove(temp_csv_path)
        except Exception:
            pass
        
        print(f"    ✓ Source CSV retained in content: {csv_title}")
        
        return published_item
        
    except Exception as e:
        print(f"    ✗ Error creating table: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


def publish_or_update_table(gis, table_name, dataframe, folder, description=""):
    """
    Main function to publish new table or update existing one.
    
    Update Strategy (preserves item ID for Dashboard compatibility):
        1. Delete existing features using delete_features()
        2. Append new data using append() method
        3. If update fails, prompt user before delete and recreate
    
    Args:
        gis: GIS connection object
        table_name: Name of the table
        dataframe: pandas DataFrame with data
        folder: Folder to place the table in
        description: Optional description
        
    Returns:
        Item object if successful, None if failed
    """
    print(f"\n{'='*50}")
    print(f"Processing: {table_name}")
    print(f"{'='*50}")
    print(f"  Records to publish: {len(dataframe)}")
    
    if len(dataframe) == 0:
        print(f"  ⚠ No data to publish for {table_name}")
        return None
    
    # Step 1: Check for existing table
    existing_item = find_existing_table(gis, table_name)
    
    if existing_item:
        print(f"\n  Existing table found - attempting to update...")
        print(f"  Item ID: {existing_item.id} (will be preserved)")
        
        # Step 2: Try update method (delete features + append)
        success = update_existing_table(existing_item, dataframe, folder)
        
        if success:
            print(f"\n  ✓ Successfully updated: {table_name}")
            return existing_item
        
        # Step 3: Update failed - prompt user before destructive action
        print(f"\n" + "="*60)
        print("⚠️  WARNING: UPDATE METHOD FAILED")
        print("="*60)
        print(f"\nThe update method failed for: {table_name}")
        print(f"Current Item ID: {existing_item.id}")
        print(f"\n" + "-"*60)
        print("POSSIBLE REASONS FOR FAILURE:")
        print("-"*60)
        print("""
1. CSV SOURCE ITEM MISSING
   - Check if '{table_name}_source' CSV item exists in your content
   - Solution: Delete the hosted table and let the script recreate it

2. SCHEMA MISMATCH
   - Column names or data types may have changed since original publish
   - New columns added or columns removed
   - Solution: Delete the hosted table to publish with new schema

3. SERVICE NOT EDITABLE
   - The hosted feature service may not have editing enabled
   - Solution: Enable editing on the service via ArcGIS Online/Portal

4. INSUFFICIENT PERMISSIONS
   - You may not have edit/delete permissions on the service
   - Solution: Check your role and item permissions

5. SERVICE LOCKED OR IN USE
   - Another process may be using the service
   - Solution: Wait and try again later
""")
        print("-"*60)
        print(f"\nIf you proceed with DELETE + RECREATE:")
        print(f"  • The item ID WILL CHANGE")
        print(f"  • Any Dashboards using this table will need to be reconfigured")
        print(f"  • Any Web Maps or Apps referencing this table will break")
        print("-"*60)
        
        # Prompt user for confirmation
        while True:
            user_input = input(f"\nDo you want to DELETE and RECREATE '{table_name}'? (yes/no/skip): ").strip().lower()
            
            if user_input in ['yes', 'y']:
                print(f"\n  Proceeding with delete and recreate...")
                try:
                    item_id = existing_item.id
                    existing_item.delete(permanent=True)
                    print(f"  ✓ Deleted existing table (old ID: {item_id})")
                    time.sleep(2)  # Wait for deletion to propagate
                except Exception as del_error:
                    print(f"  ✗ Delete failed: {str(del_error)}")
                    print(f"  Cannot proceed. Please manually delete the item and re-run.")
                    return None
                break
                
            elif user_input in ['no', 'n']:
                print(f"\n  ✗ Aborted by user. Table '{table_name}' was NOT updated.")
                print(f"  The existing table remains unchanged (ID: {existing_item.id})")
                print(f"\n  Recommended actions:")
                print(f"    1. Review the failure reasons above")
                print(f"    2. Check your content for '{table_name}_source' CSV item")
                print(f"    3. Verify service settings (editing) in ArcGIS Online/Portal")
                print(f"    4. Re-run the notebook after making corrections")
                return existing_item  # Return existing item unchanged
                
            elif user_input in ['skip', 's']:
                print(f"\n  ⏭ Skipping '{table_name}' - will continue with other tables")
                return existing_item  # Return existing item, continue processing
                
            else:
                print(f"  Please enter 'yes', 'no', or 'skip'")
    
    # Step 4: Create new table
    print(f"\n  Creating new table...")
    new_item = create_new_table(gis, table_name, dataframe, folder, description)
    
    if new_item:
        # Share with organization
        try:
            new_item.sharing.sharing_level = 'org'
            print(f"  ✓ Shared with organization")
        except Exception as share_error:
            # Try legacy sharing method
            try:
                new_item.share(org=True)
                print(f"  ✓ Shared with organization (legacy method)")
            except Exception as share_error2:
                print(f"  ⚠ Sharing warning: {str(share_error2)[:50]}")
        
        print(f"\n  ✓ Successfully created: {table_name}")
        print(f"  New Item ID: {new_item.id}")
        return new_item
    
    print(f"\n  ✗ Failed to create: {table_name}")
    return None


print("✓ Helper functions loaded")

# =============================================================================
# CELL 4: GATHER ALL USER INFORMATION
# =============================================================================
# This cell retrieves all users in the organization and builds lookup
# dictionaries for user information and group memberships.
# 
# Data collected per user:
#   - Email, full name, last login, created date
#   - Organization ID (for internal/external classification)
#   - Member categories (from Member Category Schema)
#   - All groups the user belongs to (org-wide)
#
# This information is used in later cells for:
#   - Active member calculations
#   - Group owner name lookups
#   - Internal/external user classification
# =============================================================================

print("\n" + "=" * 60)
print("GATHERING USER INFORMATION")
print("=" * 60)

# Get all users in the organization for member categories and group memberships
print("\nFetching all organization users...")

all_users = gis.users.search(query="*", max_users=10000)
print(f"  ✓ Found {len(all_users)} users")

# Build user lookup dictionary with group memberships
user_info_dict = {}
user_groups_dict = {}  # Track all groups each user belongs to

print("\nBuilding user information dictionary...")
for idx, user in enumerate(all_users):
    try:
        username = user.username
        
        # Get user's groups
        try:
            user_groups = user.groups
            group_ids = [g.id for g in user_groups] if user_groups else []
        except Exception:
            group_ids = []
        
        user_groups_dict[username] = group_ids
        
        # Get member categories if available
        try:
            categories = user.get('categories', [])
            if not categories:
                categories = safe_get(user, 'memberCategories', [])
        except Exception:
            categories = []
        
        user_info_dict[username] = {
            'email': safe_get(user, 'email', ''),
            'last_login': safe_get(user, 'lastLogin', None),
            'org_id': safe_get(user, 'orgId', ''),
            'created': safe_get(user, 'created', None),
            'categories': categories if isinstance(categories, list) else [],
            'full_name': safe_get(user, 'fullName', username)
        }
        
        if (idx + 1) % 50 == 0:
            print(f"    Processed {idx + 1}/{len(all_users)} users...")
            
    except Exception as e:
        continue

print(f"  ✓ User information dictionary built for {len(user_info_dict)} users")

# =============================================================================
# CELL 5: GATHER ALL GROUP INFORMATION
# =============================================================================
# This cell retrieves all groups in the organization.
# If TEST_MODE is enabled, only the first TEST_LIMIT groups are analyzed.
#
# Groups are retrieved using gis.groups.search() which returns all groups
# visible to the authenticated user (typically all org groups for admins).
# =============================================================================

print("\n" + "=" * 60)
print("GATHERING GROUP INFORMATION")
print("=" * 60)

# Get all groups in the organization
print("\nFetching all organization groups...")

all_groups = gis.groups.search(query="*", max_groups=10000)
total_groups = len(all_groups)

# Apply test mode limit
if TEST_MODE:
    groups_to_analyze = all_groups[:TEST_LIMIT]
    print(f"  ✓ Found {total_groups} groups (analyzing first {TEST_LIMIT} in test mode)")
else:
    groups_to_analyze = all_groups
    print(f"  ✓ Found {total_groups} groups (analyzing all)")

# =============================================================================
# CELL 6: BUILD GROUP SNAPSHOT DATA
# =============================================================================
# This cell builds the Group_Snapshot table data.
# 
# For each group, the following is collected/calculated:
#   - Basic info: ID, title, summary, description, tags, owner
#   - Owner full name from user lookup
#   - Dates: Created
#   - Classification: Type (Standard, Shared Update, Collaboration), 
#                     Sharing level, Hub group, Site group
#   - Counts: Items, Members, Active members
#   - Scores: Item score, Member score, Average views (excl. Living Atlas)
#   - Flags: is_recent, is_empty, is_single_member, is_hub, is_site
#
# Note: Average views excludes Living Atlas/Esri content to avoid skewed metrics
# =============================================================================

print("\n" + "=" * 60)
print("BUILDING GROUP SNAPSHOT DATA")
print("=" * 60)

group_snapshot_data = []

for idx, group in enumerate(groups_to_analyze):
    try:
        group_id = group.id
        
        # Get group members
        try:
            members = group.get_members()
            member_count = len(members.get('users', [])) + len(members.get('admins', []))
            all_member_usernames = members.get('users', []) + members.get('admins', [])
        except Exception:
            member_count = 0
            all_member_usernames = []
        
        # Get group content
        try:
            content = group.content(max_items=1000)
            item_count = len(content) if content else 0
        except Exception:
            item_count = 0
            content = []
        
        # Calculate metrics
        # Active members (logged in within RECENT_DAYS_THRESHOLD days)
        # External members (org_id different from connected organization OR not in our org's user list)
        active_members = 0
        external_member_count = 0
        for username in all_member_usernames:
            user_info = user_info_dict.get(username, {})
            
            if user_info:
                # User is in our organization's user list
                # Check if active (logged in within threshold)
                last_login = user_info.get('last_login')
                if last_login:
                    days_inactive = days_since(last_login)
                    if days_inactive is not None and days_inactive <= RECENT_DAYS_THRESHOLD:
                        active_members += 1
                
                # Check if external (different org_id)
                user_org = user_info.get('org_id', '')
                if user_org and org_id and user_org != org_id:
                    external_member_count += 1
            else:
                # User is NOT in our organization's user list
                # This means they are external (from a different organization)
                external_member_count += 1
        
        # Calculate group scores
        # group_item_score = active_members / total_items * 100 (if items > 0)
        if item_count > 0:
            group_item_score = round((active_members / item_count) * 100, 2)
        else:
            group_item_score = 0.0
        
        # group_member_score = active_members / total_members * 100 (if members > 0)
        if member_count > 0:
            group_member_score = round((active_members / member_count) * 100, 2)
        else:
            group_member_score = 0.0
        
        # Check if recent activity (content updated or views within threshold)
        # Also calculate views excluding Living Atlas content
        recent_content_update = False
        recent_views = False
        total_views = 0
        non_esri_item_count = 0  # Count of items NOT from Living Atlas
        
        for item in content[:100]:  # Check first 100 items
            try:
                item_modified = safe_get(item, 'modified', None)
                if item_modified:
                    days_modified = days_since(item_modified)
                    if days_modified is not None and days_modified <= RECENT_DAYS_THRESHOLD:
                        recent_content_update = True
                
                # Only count views from non-Living Atlas items
                # Note: numViews = portal-level views (item opened), not service requests
                if not is_living_atlas_item(item):
                    item_views = safe_get(item, 'numViews', 0) or 0
                    total_views += item_views
                    non_esri_item_count += 1
            except Exception:
                continue
        
        # Calculate average views per item (excluding Living Atlas content)
        if non_esri_item_count > 0:
            avg_views = round(total_views / non_esri_item_count, 2)
        else:
            avg_views = 0.0
        
        # Determine if "recent" based on activity
        is_recent = recent_content_update  # True if content updated within threshold
        
        # Calculate days since last content update
        most_recent_update = None
        for item in content[:100]:
            try:
                item_modified = safe_get(item, 'modified', None)
                if item_modified:
                    if most_recent_update is None or item_modified > most_recent_update:
                        most_recent_update = item_modified
            except Exception:
                continue
        
        days_since_content_update = days_since(most_recent_update) if most_recent_update else None
        
        # Get group type (now includes capabilities like Shared Update)
        group_type = get_group_type(group)
        group_sharing = get_group_sharing_level(group)
        
        # Get group owner information
        group_owner = safe_get(group, 'owner', '')
        group_owner_name = get_user_full_name(group_owner, user_info_dict)
        
        # Check for Hub and Site group designations
        hub_group = is_hub_group(group)
        site_group = is_site_group(group)
        
        # Build group snapshot record
        snapshot_record = {
            'group_id': group_id,
            'group_title': truncate_string(safe_get(group, 'title', ''), FIELD_LENGTHS['group_title']),
            'group_summary': truncate_string(safe_get(group, 'snippet', ''), FIELD_LENGTHS['group_summary']),
            'group_description': truncate_string(safe_get(group, 'description', ''), FIELD_LENGTHS['group_description']),
            'group_tags': truncate_string(', '.join(safe_get(group, 'tags', []) or []), FIELD_LENGTHS['group_tags']),
            'group_owner': group_owner,
            'group_owner_name': group_owner_name,
            'group_created': convert_timestamp_to_date(safe_get(group, 'created', None)),
            'group_type': group_type,
            'group_sharing_level': group_sharing,
            'group_item_count': item_count,
            'group_member_count': member_count,
            'external_member_count': external_member_count,
            'has_external_members': external_member_count > 0,
            'group_link': f"{base_group_url}{group_id}",
            'active_members': active_members,
            'group_item_score': group_item_score,
            'group_member_score': group_member_score,
            'avg_views_per_item': avg_views,
            'days_since_content_update': days_since_content_update,
            'is_recent': is_recent,
            'is_empty': item_count == 0,
            'is_single_member': member_count == 1,
            'is_hub': hub_group,
            'is_site': site_group
        }
        
        group_snapshot_data.append(snapshot_record)
        
        if (idx + 1) % 10 == 0:
            print(f"  Processed {idx + 1}/{len(groups_to_analyze)} groups...")
            
    except Exception as e:
        print(f"  ⚠ Error processing group {idx}: {str(e)}")
        continue

print(f"\n✓ Completed Group Snapshot data: {len(group_snapshot_data)} records")

# Create DataFrame
df_group_snapshot = pd.DataFrame(group_snapshot_data)
print("\nGroup Snapshot Schema:")
print(df_group_snapshot.dtypes)

# =============================================================================

# =============================================================================
# CELL 7: CREATE OR UPDATE HOSTED TABLE
# =============================================================================
# This cell publishes the Group_Snapshot DataFrame as a hosted table.
#
# Publishing logic:
#   1. Check if table already exists (by name and owner)
#   2. If exists: Delete features and append new data
#   3. If update fails: Prompt to delete and recreate
#   4. If doesn't exist: Create new hosted table
#
# The table is:
#   - Published to the OUTPUT_FOLDER folder
#   - Shared at the organization level
#   - Suitable for use in ArcGIS Dashboards
# =============================================================================

print("\n" + "=" * 60)
print("PUBLISHING HOSTED TABLE")
print("=" * 60)

# Get or create the output folder
print("\nSetting up output folder...")
output_folder = get_or_create_folder(gis, OUTPUT_FOLDER)

# Publish/Update Group Snapshot Table
snapshot_item = publish_or_update_table(
    gis,
    GROUP_SNAPSHOT_TABLE,
    df_group_snapshot,
    output_folder,
    "Group Analytics - Snapshot table containing overall group information, metrics, and health scores for organization management."
)

# =============================================================================
# CELL 8: SUMMARY AND RESULTS
# =============================================================================
# This cell displays a summary of the analysis results and published table.
# =============================================================================

print("\n" + "=" * 60)
print("EXECUTION SUMMARY")
print("=" * 60)

print(f"\nAnalysis Configuration:")
print(f"  - Test Mode: {TEST_MODE}")
print(f"  - Groups Analyzed: {len(groups_to_analyze)}")
print(f"  - Total Organization Groups: {total_groups}")
print(f"  - Output Folder: {OUTPUT_FOLDER}")

print(f"\nData Statistics:")
print(f"  - Group Snapshot Records: {len(df_group_snapshot)}")

print(f"\nGroup Health Indicators:")
if len(df_group_snapshot) > 0:
    empty_groups = len(df_group_snapshot[df_group_snapshot['is_empty'] == True])
    single_member_groups = len(df_group_snapshot[df_group_snapshot['is_single_member'] == True])
    inactive_groups = len(df_group_snapshot[df_group_snapshot['is_recent'] == False])
    hub_groups = len(df_group_snapshot[df_group_snapshot['is_hub'] == True])
    site_groups = len(df_group_snapshot[df_group_snapshot['is_site'] == True])
    
    # External members
    total_external = df_group_snapshot['external_member_count'].sum()
    groups_with_external = len(df_group_snapshot[df_group_snapshot['external_member_count'] > 0])
    
    print(f"  - Empty Groups (no content): {empty_groups}")
    print(f"  - Single Member Groups: {single_member_groups}")
    print(f"  - Inactive Groups (no recent updates): {inactive_groups}")
    print(f"  - Hub Groups (ArcGIS Hub): {hub_groups}")
    print(f"  - Site Groups (Enterprise Sites): {site_groups}")
    print(f"  - Groups with External Members: {groups_with_external}")
    print(f"  - Total External Members: {int(total_external)}")
    
    # Average scores
    avg_item_score = df_group_snapshot['group_item_score'].mean()
    avg_member_score = df_group_snapshot['group_member_score'].mean()
    print(f"  - Average Group Item Score: {avg_item_score:.2f}")
    print(f"  - Average Group Member Score: {avg_member_score:.2f}")

print(f"\nPublished Table:")
if snapshot_item:
    print(f"  ✓ {GROUP_SNAPSHOT_TABLE}: {snapshot_item.homepage}")
else:
    print(f"  ✗ {GROUP_SNAPSHOT_TABLE}: Failed to publish")

# List source CSV item in user's content
print(f"\nSource CSV Item (in '{OUTPUT_FOLDER}' folder):")
print(f"  This item is required for future update operations - DO NOT DELETE")
csv_title = f"{GROUP_SNAPSHOT_TABLE}_source"
try:
    csv_search = gis.content.search(f'title:"{csv_title}" owner:{current_user} type:CSV', max_items=10)
    csv_found = [item for item in csv_search if item.title == csv_title]
    if csv_found:
        print(f"  ✓ {csv_title}: {csv_found[0].homepage}")
    else:
        print(f"  ⚠ {csv_title}: Not found (will be created on next run)")
except Exception:
    print(f"  ? {csv_title}: Could not verify")

print("\n" + "=" * 60)
print("NOTEBOOK EXECUTION COMPLETE")
print("=" * 60)

# Display DataFrame for review
print("\n--- Group Snapshot Preview ---")
try:
    display(df_group_snapshot.head(10))
except NameError:
    print(df_group_snapshot.head(10))
