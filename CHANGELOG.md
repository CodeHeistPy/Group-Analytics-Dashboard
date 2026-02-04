# Changelog

All notable changes to the ArcGIS Group Analytics Notebooks.

## Group_Analytics_Notebook

### [2.19] - 2025-02-04
#### Added
- `has_external_members` boolean field to Group_Snapshot table

#### Fixed
- `external_member_count` now correctly identifies external users
  - Users not in organization's user list are counted as external
  - Previously missed external users from partner organizations

### [2.18] - 2025-02-04
#### Fixed
- `external_member_count` logic to handle users not in `user_info_dict`

### [2.17] - 2025-02-03
#### Added
- `external_member_count` field to Group_Snapshot table

#### Fixed
- `avg_views_per_item` returning 0 for all groups
  - `is_living_atlas_item()` was matching any username containing 'esri'
  - Now only matches official Esri system accounts
- Date fields showing timestamps instead of date-only
  - Improved detection for both `datetime.date` and `datetime.datetime`

### [2.16] - 2025-02-03
#### Fixed
- Comprehensive field truncation for all string fields
- Removed duplicate keys in FIELD_LENGTHS
- Cleaned up unused imports

### [2.15] - 2025-02-03
#### Fixed
- String field length validation to prevent append failures
- Added `truncate_string()` helper function
- Added FIELD_LENGTHS constants

### [2.14] - 2025-01-10
#### Fixed
- Append operation failures due to field length limits

### [2.13] - 2025-01-10
#### Changed
- Simplified update logic with delete + append strategy
- Added edit_features fallback for reliability

### [2.12] - 2025-01-10
#### Fixed
- CSV source item management for append operations

### [2.11] - 2025-01-10
#### Added
- Source CSV items stored in user's content
- Item ID preservation during updates

### [2.10] - 2025-01-10
#### Changed
- Schema: Group_Content now one record per item-group association
- Schema: Group_Members now one record per user-group membership

### [2.9] - 2025-01-10
#### Added
- Full names from user profile for item_owner and user_name
- item_data_updated uses actual last edit date for Feature Services

### [2.8] - 2025-01-10
#### Added
- item_url field with short portal item page URL format

### [2.7] - 2025-01-07
#### Added
- Group type detection (Standard, Shared Update, Partnered/Distributed Collaboration)
- group_sharing_level capitalization (Private, Organization, Public)

### [2.6] - 2025-01-07
#### Added
- CSV-based storage for table updates
- Improved error handling

### [2.5] - 2025-01-07
#### Added
- is_hub and is_site flags for ArcGIS Hub/Sites detection

### [2.4] - 2025-01-07
#### Initial tracked version
- Three-table schema (Snapshot, Content, Members)
- Basic group metrics and health indicators

---

## Group_Snapshot_Only_Notebook

### [1.2] - 2025-02-04
#### Added
- `has_external_members` boolean field

### [1.1] - 2025-02-04
#### Fixed
- `external_member_count` now correctly identifies external users

### [1.0] - 2025-02-04
#### Initial Release
- Streamlined version based on Group_Analytics_Notebook v2.17
- Single table output (Group_Snapshot only)
- Faster execution without content/member detail collection
