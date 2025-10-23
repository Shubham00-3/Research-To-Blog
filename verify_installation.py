#!/usr/bin/env python
"""Verify installation and configuration of research-to-blog pipeline."""

import sys
from pathlib import Path


def check_python_version():
    """Check Python version."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print(f"[X] Python 3.11+ required, found {version.major}.{version.minor}")
        return False
    print(f"[OK] Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_dependencies():
    """Check if dependencies are installed."""
    required = [
        "groq",
        "langgraph",
        "fastembed",
        "chromadb",
        "fastapi",
        "typer",
        "structlog",
        "pydantic",
    ]

    missing = []
    for package in required:
        try:
            __import__(package)
            print(f"[OK] {package}")
        except ImportError:
            print(f"[X] {package}")
            missing.append(package)

    if missing:
        print(f"\n[X] Missing dependencies: {', '.join(missing)}")
        print("Run: pip install -r requirements.txt")
        return False

    return True


def check_env_file():
    """Check if .env file exists."""
    env_path = Path(".env")
    if not env_path.exists():
        print("[X] .env file not found")
        print("Run: copy env.example .env")
        print("Then add your GROQ_API_KEY")
        return False

    content = env_path.read_text()
    if "your_groq_api_key_here" in content:
        print("[!] .env file exists but GROQ_API_KEY looks like placeholder")
        print("Edit .env and add your actual Groq API key from https://console.groq.com")
        return False

    print("[OK] .env file configured")
    return True


def check_directories():
    """Check if data directories exist."""
    dirs = ["data/chroma", "data/cache", "outputs"]
    all_exist = True

    for dir_path in dirs:
        path = Path(dir_path)
        if path.exists():
            print(f"[OK] {dir_path}/")
        else:
            print(f"[i] {dir_path}/ will be created automatically")

    return True


def main():
    """Run all checks."""
    print("Verifying Research-to-Blog Installation\n")

    checks = [
        ("Python Version", check_python_version),
        ("Dependencies", check_dependencies),
        ("Configuration", check_env_file),
        ("Directories", check_directories),
    ]

    results = []
    for name, check_func in checks:
        print(f"\nChecking {name}:")
        results.append(check_func())

    print("\n" + "=" * 50)

    if all(results):
        print("[OK] All checks passed! Ready to run.")
        print("\nTry:")
        print('  python -m app.cli.main run "Your topic" --audience "your audience"')
        return 0
    else:
        print("[X] Some checks failed. See above for details.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

