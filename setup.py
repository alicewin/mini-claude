#!/usr/bin/env python3
"""
Setup script for Mini-Claude
"""

from setuptools import setup, find_packages
from pathlib import Path

# Read README for long description
readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text() if readme_path.exists() else ""

# Read requirements
requirements_path = Path(__file__).parent / "requirements.txt"
if requirements_path.exists():
    with open(requirements_path) as f:
        requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]
else:
    requirements = ["anthropic>=0.25.0"]

setup(
    name="mini-claude",
    version="1.0.0",
    description="A lightweight AI agent for repetitive coding tasks",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Claude Senior Engineer",
    author_email="noreply@anthropic.com",
    url="https://github.com/anthropics/mini-claude",
    packages=find_packages(),
    py_modules=[
        "mini_claude",
        "task_queue", 
        "self_update",
        "guardrails",
        "cli"
    ],
    install_requires=requirements,
    extras_require={
        "redis": ["redis>=4.0.0"],
        "security": ["bandit>=1.7.0"],
        "dev": [
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0", 
            "black>=23.0.0",
            "flake8>=6.0.0"
        ]
    },
    entry_points={
        "console_scripts": [
            "mini-claude=cli:main",
            "mini-claude-daemon=mini_claude:main",
            "mini-claude-queue=task_queue:main",
            "mini-claude-updates=self_update:main"
        ]
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers", 
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Software Development :: Code Generators",
        "Topic :: Scientific/Engineering :: Artificial Intelligence"
    ],
    python_requires=">=3.8",
    include_package_data=True,
    package_data={
        "": ["prompt_templates/*.txt", "config.json"]
    }
)