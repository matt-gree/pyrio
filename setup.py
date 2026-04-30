from setuptools import setup

setup(
    name="pyrio",
    version="0.1.0",
    packages=["pyrio"],
    package_dir={"pyrio": "."},
    install_requires=[
        "numpy>=2.2.0",
        "pandas>=2.2.3",
        "pytz>=2024.2",
        "Requests>=2.29.0",
        "requests_cache>=1.2.1",
    ],
    extras_require={
        # The draw module is plotting-only and not imported by pyrio's
        # public API. Install with `pip install pyrio[draw]` to use it.
        "draw": ["matplotlib>=3.10.3"],
    },
    description="Library for interacting with Mario Superstar Baseball and Project Rio",
    author="MattGree",
    author_email="MattGreeMSSB@gmail.com",
    url="https://github.com/matt-gree/pyrio",
)
