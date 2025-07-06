from setuptools import setup, find_packages

setup(
    name="pyrio",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "matplotlib>=3.10.3",
        "numpy>=2.2.0",
        "pandas>=2.2.3",
        "pytz>=2024.2",
        "Requests>=2.29.0",
        "requests_cache>=1.2.1",
        "scipy>=1.15.0",
        "setuptools>=75.6.0",
        "SQLAlchemy>=2.0.36",
    ],
    description="Library for interacting with Mario Superstar Baseball and Project Rio",
    author="MattGree",
    author_email="MattGreeMSSB@gmail.com",
    url="https://github.com/matt-gree/pyRio",
)