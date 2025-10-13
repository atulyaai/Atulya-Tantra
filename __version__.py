"""
Atulya Tantra - Version Information
Semantic Versioning: MAJOR.MINOR.PATCH
"""

__version__ = "1.0.3"
__version_info__ = tuple(int(i) for i in __version__.split("."))

# Version history
VERSION_HISTORY = {
    "1.0.3": "MAJOR MERGE: Protocols moved into configuration/, FastAPI server, all duplicates removed",
    "1.0.2": "Global configuration manager, base classes, consolidated architecture",
    "1.0.1": "Professional restructure with protocol frameworks",
    "1.0.0": "Initial release - Voice assistant with multi-model support"
}

# Release information
RELEASE_DATE = "2025-10-12"
CODENAME = "Jarvis"
STATUS = "stable"

def get_version():
    """Get formatted version string"""
    return f"v{__version__} ({CODENAME})"

def get_version_info():
    """Get detailed version information"""
    return {
        "version": __version__,
        "version_info": __version_info__,
        "codename": CODENAME,
        "status": STATUS,
        "release_date": RELEASE_DATE
    }

if __name__ == "__main__":
    print(f"Atulya Tantra {get_version()}")
    print(f"Status: {STATUS}")
    print(f"Released: {RELEASE_DATE}")

