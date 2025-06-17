from hatchling.builders.hooks.plugin.interface import BuildHookInterface
import subprocess
import sys

class CodegenHook(BuildHookInterface):
    def initialize(self, version, build_data):
        print("Running code generation...")

        subprocess.run(
            [sys.executable, "codegen/generate.py"],
            check=True
        )

        print("Code generation complete.")
