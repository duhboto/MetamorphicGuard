from setuptools import setup, find_packages

setup(
    name="metamorphic_guard",
    version="2.0.0",
    description="A Python library for comparing program versions using metamorphic testing",
    author="Engineer Alpha",
    packages=find_packages(),
    install_requires=[
        "click>=8.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "metamorphic-guard=metamorphic_guard.cli:main",
            "metaguard=metamorphic_guard.cli:main",
        ],
    },
    python_requires=">=3.10",
)
