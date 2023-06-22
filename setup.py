"""The setup script."""
import subprocess

from setuptools import setup

if __name__ == "__main__":
    # First of all... run the automatic code generation
    subprocess.call("python codegen/generate.py", shell=True)

    setup()
