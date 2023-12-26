import os

coverage_instance = None
if os.environ.get("NEXUS_COVERAGE_TEST", "0") == "1":
    if coverage_instance is None:
        import coverage
        coverage_instance = coverage.Coverage()
        coverage_instance.start()
        print("Starting a coverage...")
