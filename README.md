# ArcGIS Group Analytics Notebooks

Python notebooks for ArcGIS Online and Enterprise that analyze organizational Groups and publish metrics to hosted tables for Dashboard reporting.

## Overview

These notebooks help administrators identify groups that can be cleaned up or removed from an ArcGIS organization by collecting and analyzing group metadata, content, and membership information.

## Notebooks

| Notebook | Description | Tables Created |
|----------|-------------|----------------|
| **Group_Analytics_Notebook.py** | Full analytics with detailed content and member breakdowns | 3 (Snapshot, Content, Members) |
| **Group_Snapshot_Only_Notebook.py** | Streamlined version for group-level KPIs only | 1 (Snapshot) |

## Features

- **Automatic Table Management**: Creates new tables on first run, updates existing tables on subsequent runs
- **Dashboard Ready**: All tables are published and shared at organization level for use in ArcGIS Dashboards
- **Preserved Item IDs**: Update strategy preserves item IDs for Dashboard compatibility
- **Field Validation**: Automatic string truncation to prevent append failures
- **External Member Detection**: Identifies groups with members from partner organizations
- **Living Atlas Filtering**: Excludes Esri system content from view calculations

## Table Schemas

### Group_Snapshot (Both Notebooks)
One record per group with metrics including:
- Basic info: ID, title, owner, description, tags
- Counts: items, members, external members
- Scores: item score, member score, avg views per item
- Flags: is_empty, is_single_member, is_recent, has_external_members, is_hub, is_site
- Dates: created, days since content update

### Group_Content (Full Notebook Only)
One record per item-group association:
- Item details: ID, title, owner, type, URL
- Dates: created, last data update
- Metrics: view count, days since update
- Group association flags

### Group_Members (Full Notebook Only)
One record per user-group membership:
- User info: name, email, org ID
- Activity: last login, days since login, is_active
- Classification: Internal/External membership type

## Requirements

- ArcGIS Notebook environment (ArcGIS Online or Enterprise)
- Administrative privileges to view all groups and members
- ArcGIS API for Python 2.3.0+

## Configuration

Edit these variables in Cell 1:

```python
TEST_MODE = True          # Set to False for production runs
TEST_LIMIT = 10           # Number of groups in test mode
OUTPUT_FOLDER = "Group Analytics"  # Folder for published tables
RECENT_DAYS_THRESHOLD = 90         # Days for "recent" activity
```

## Usage

1. Copy the notebook content into an ArcGIS Notebook
2. Adjust configuration options in Cell 1
3. Run all cells in sequence
4. Tables are published to the specified folder

## Version History

See [CHANGELOG.md](CHANGELOG.md) for detailed version history.

### Current Versions
- **Group_Analytics_Notebook**: v2.19
- **Group_Snapshot_Only_Notebook**: v1.2

## License

Internal use - modify as needed for your organization.

## Contributing

1. Fork this repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## Support

For issues or feature requests, please open a GitHub issue.
