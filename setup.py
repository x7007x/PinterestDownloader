from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="pinterest-downloader",
    version="3.0.0",
    author="Ahmed Nagm",
    description="Pinterest data extractor library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/x7007x/PinterestDownloader",
    project_urls={
        "Bug Tracker": "https://github.com/x7007x/PinterestDownloader/issues",
        "PyPI": "https://pypi.org/project/pinterest-downloader/",
    },
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=[],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Topic :: Internet :: WWW/HTTP :: Indexing/Search",
        "Topic :: Multimedia :: Graphics",
        "Topic :: Multimedia :: Video",
    ],
    keywords="pinterest downloader scraper extractor pin video image gif board user",
)
