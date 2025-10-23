"""Setup script for research-to-blog package."""

from setuptools import find_packages, setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="research-to-blog",
    version="0.1.0",
    author="Research-to-Blog Team",
    description="Verified Research-to-Blog Multi-Agent Pipeline with enforced citations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/research-to-blog",
    packages=find_packages(exclude=["tests*"]),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "research-to-blog=app.cli.main:app",
        ],
    },
)

