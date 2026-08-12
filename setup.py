from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pinterest-downloader",
    version="4.1.0",
    author="Ahmed Negm",
    description="Unofficial Python library to download and interact with Pinterest content (pins, videos, GIFs, profiles, and boards). No API key required.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/x7007x/PinterestDownloader",
    project_urls={
        "Bug Tracker": "https://github.com/x7007x/PinterestDownloader/issues",
        "PyPI": "https://pypi.org/project/pinterest-downloader/",
    },
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.25.0",
        "beautifulsoup4>=4.10.0",
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Multimedia :: Graphics",
        "Topic :: Multimedia :: Video",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Utilities",
    ],
    keywords=[
        "pinterest",
        "downloader",
        "pins",
        "boards",
        "profiles",
        "media",
        "images",
        "videos",
        "gifs",
        "scraper",
        "unofficial-api",
    ],
    include_package_data=True,
    zip_safe=False,
)
