from setuptools import setup, find_packages

setup(
    name="un-kicker-control",
    version="0.1.0",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    py_modules=["motherboard", "nanokicker", "main"],
    install_requires=[
        "pyserial",
        "PyQt5",
    ],
    entry_points={
        "console_scripts": ["un-kicker-control=main:main"],
    },
)
