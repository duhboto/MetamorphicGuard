from setuptools import setup, find_packages

setup(
    name="metamorphic-guard",
    version="1.0.0",
    description="A Python library for comparing program versions using metamorphic testing",
    author="Engineer Alpha",
    packages=find_packages(),
    install_requires=[
        "click>=8.0.0",
        "pytest>=7.0.0",
        "jsonschema>=4.0.0",
        "numpy>=1.21.0",
    ],
    entry_points={
        "console_scripts": [
            "metamorphic-guard=metamorphic_guard.cli:main",
            "mg=metamorphic_guard.cli:main",
        ],
    },
    python_requires=">=3.10",
)
