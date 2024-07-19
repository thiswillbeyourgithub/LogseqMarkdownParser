# setup.py

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="LogseqMarkdownParser",
    version="2.13",
    author="thiswillbeyourgithub",
    description="parse logseq markdown text with easy access to properties, hierarchy, TODO etc",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/thiswillbeyourgithub/LogseqMarkdownParser",
    package_dir={"": "src"},
    packages=find_packages(),
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
        "Programming Language :: Python",
        "Programming Language :: Python :: 3",
    ],
    keywords=["Logseq", "PKM", "Markdown", "parsing", "parser", "properties", "block", "text"],
    install_requires=[
        "fire>=0.5.0",
        "rtoml >= 0.11.0",
    ],
    extras_require={
        "beartype": ["beartype"],
    },
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "LogseqMarkdownParser=LogseqMarkdownParser:cli",
        ],
    },
    license_files=("LICENSE",),
)
