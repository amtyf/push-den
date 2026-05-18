from setuptools import setup, find_packages
from pathlib import Path

this_directory = Path(__file__).parent
long_description = (this_directory / "README.md").read_text(encoding="utf-8")

setup(
    name="push-den",
    author="Asif Mahmud",
    author_email="asifmahmud.tayef@gmail.com",
    version="1.3.3",
    description="A wrapper library for using firebase-admin-python to send data and notification messages.",
    license="Proprietary",
    long_description=long_description,
    long_description_content_type="text/markdown",
    python_requires=">=3.8",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Operating System :: OS Independent",
        "License :: Other/Proprietary License",
        "Topic :: Software Development :: Libraries",
    ],
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    install_requires=[
        "firebase-admin==6.6.0",
        "jsonschema==4.4.0",
        "PyJWT==2.9.0",
        "httpx[http2]==0.23.0",
        "cryptography==44.0.0",
    ],
    zip_safe=False,
)
