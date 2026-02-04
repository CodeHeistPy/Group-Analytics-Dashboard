# CLAUDE.md - AI Assistant Guide

This document provides guidance for AI assistants working on the Group-Analytics-Dashboard project.

## Project Overview

**Group-Analytics-Dashboard** is an ArcGIS Python project for organizational Group management. It analyzes group health metrics and publishes results to hosted tables for ArcGIS Dashboard visualization.

### Key Features (Planned/In Development)
- Membership activity analysis
- Content freshness tracking
- External collaboration monitoring
- Usage pattern analysis
- Automated publishing to ArcGIS hosted tables
- Dashboard-ready data outputs for cleanup decisions

## Current Project Status

This project is in its initial setup phase. The repository currently contains only the README.md file and requires implementation of the core analytics functionality.

## Technology Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.9+ |
| Primary SDK | ArcGIS API for Python |
| Notebook Format | Jupyter Notebooks (.ipynb) |
| Data Analysis | pandas, numpy |
| Output Platform | ArcGIS Online / Enterprise |
| Visualization | ArcGIS Dashboard |

## Expected Project Structure

When fully implemented, the project should follow this structure:

```
Group-Analytics-Dashboard/
├── CLAUDE.md                 # This file
├── README.md                 # Project overview
├── requirements.txt          # Python dependencies
├── .gitignore               # Git ignore patterns
├── config/
│   ├── config.example.py    # Example configuration
│   └── credentials.example  # Example credentials (never commit real ones)
├── notebooks/
│   ├── 01_group_inventory.ipynb      # Group enumeration
│   ├── 02_membership_analysis.ipynb  # Member activity metrics
│   ├── 03_content_freshness.ipynb    # Content age analysis
│   ├── 04_collaboration_audit.ipynb  # External sharing analysis
│   ├── 05_usage_patterns.ipynb       # Usage statistics
│   └── 06_publish_results.ipynb      # Publish to hosted tables
├── src/
│   ├── __init__.py
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── membership.py    # Membership metrics functions
│   │   ├── content.py       # Content analysis functions
│   │   ├── collaboration.py # Collaboration metrics
│   │   └── usage.py         # Usage pattern analysis
│   ├── arcgis_utils/
│   │   ├── __init__.py
│   │   ├── connection.py    # ArcGIS connection utilities
│   │   └── publishing.py    # Hosted table publishing
│   └── utils/
│       ├── __init__.py
│       └── helpers.py       # Common utility functions
├── tests/
│   ├── __init__.py
│   ├── test_membership.py
│   ├── test_content.py
│   └── test_utils.py
└── docs/
    └── dashboard_setup.md   # Dashboard configuration guide
```

## Development Guidelines

### Python Code Style
- Follow PEP 8 style guidelines
- Use type hints for function signatures
- Maximum line length: 100 characters
- Use docstrings (Google style) for all public functions

### Docstring Format
```python
def analyze_group_membership(group_id: str, days: int = 30) -> dict:
    """Analyze membership activity for a specific group.

    Args:
        group_id: The unique identifier of the ArcGIS group.
        days: Number of days to look back for activity. Defaults to 30.

    Returns:
        Dictionary containing membership metrics:
            - total_members: Total member count
            - active_members: Members active in period
            - activity_rate: Percentage of active members

    Raises:
        ValueError: If group_id is invalid or not found.
    """
```

### Jupyter Notebook Conventions
- Each notebook should be self-contained and runnable independently
- Start notebooks with a markdown cell explaining the purpose
- Use meaningful cell organization with markdown headers
- Clear outputs before committing (or use pre-commit hooks)
- Keep notebooks focused on single tasks/analyses

### ArcGIS API Best Practices
- Always use context managers for GIS connections when possible
- Handle token expiration gracefully
- Implement retry logic for API calls
- Respect rate limits on ArcGIS Online
- Never hardcode credentials - use environment variables or config files

### Security Considerations
- Never commit credentials, API keys, or tokens
- Use `.gitignore` to exclude sensitive files
- Store credentials in environment variables or secure config
- Use `config.example.py` patterns for configuration templates
- Validate and sanitize group/user inputs before API calls

## Common Commands

### Environment Setup
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Install in development mode (when setup.py exists)
pip install -e .
```

### Running Notebooks
```bash
# Start Jupyter
jupyter notebook notebooks/

# Or use JupyterLab
jupyter lab
```

### Running Tests
```bash
# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html

# Run specific test file
pytest tests/test_membership.py -v
```

### Code Quality
```bash
# Format code
black src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

## Key Dependencies

When setting up `requirements.txt`, include:

```
arcgis>=2.2.0
pandas>=2.0.0
numpy>=1.24.0
jupyter>=1.0.0
pytest>=7.0.0
python-dotenv>=1.0.0
```

## ArcGIS Connection Pattern

Standard connection pattern for notebooks and scripts:

```python
from arcgis.gis import GIS
import os
from dotenv import load_dotenv

load_dotenv()

# Connect to ArcGIS Online/Enterprise
gis = GIS(
    url=os.getenv("ARCGIS_URL", "https://www.arcgis.com"),
    username=os.getenv("ARCGIS_USERNAME"),
    password=os.getenv("ARCGIS_PASSWORD")
)

# Verify connection
print(f"Connected as: {gis.users.me.username}")
```

## Testing Guidelines

- Write unit tests for all analytics functions
- Mock ArcGIS API calls in tests to avoid external dependencies
- Use pytest fixtures for common test data
- Aim for >80% code coverage on src/ modules
- Test edge cases (empty groups, missing data, API errors)

## Error Handling

Use consistent error handling patterns:

```python
from arcgis.gis import GIS
import logging

logger = logging.getLogger(__name__)

def get_group_info(gis: GIS, group_id: str) -> dict:
    """Retrieve group information with proper error handling."""
    try:
        group = gis.groups.get(group_id)
        if group is None:
            raise ValueError(f"Group not found: {group_id}")
        return dict(group)
    except Exception as e:
        logger.error(f"Failed to retrieve group {group_id}: {e}")
        raise
```

## Contributing Workflow

1. Create feature branch from main
2. Implement changes with tests
3. Run linting and tests locally
4. Clear notebook outputs before committing
5. Create pull request with description
6. Address review feedback
7. Merge after approval

## Important Notes for AI Assistants

1. **Credentials**: Never generate or include real credentials. Always use environment variable patterns.

2. **ArcGIS API**: The ArcGIS API for Python has specific patterns. Refer to official documentation at https://developers.arcgis.com/python/

3. **Hosted Tables**: When publishing to hosted tables, ensure proper schema definition and handle existing table updates correctly.

4. **Rate Limits**: ArcGIS Online has rate limits. Implement appropriate delays and batch processing for large operations.

5. **Testing**: Since this project interacts with external services, mock ArcGIS calls in unit tests.

6. **Notebook Execution**: Notebooks may require valid ArcGIS credentials to run. Provide clear instructions for credential setup.

## Resources

- [ArcGIS API for Python Documentation](https://developers.arcgis.com/python/)
- [ArcGIS REST API Reference](https://developers.arcgis.com/rest/)
- [ArcGIS Dashboard Documentation](https://doc.arcgis.com/en/dashboards/)
- [Python Style Guide (PEP 8)](https://pep8.org/)
