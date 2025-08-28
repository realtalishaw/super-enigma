#!/usr/bin/env python3
"""
Test runner script for the workflow automation engine.
"""
import sys
import os
import subprocess
import argparse
from pathlib import Path


def run_tests(test_type=None, coverage=True, verbose=True, parallel=False):
    """Run the test suite."""
    # Get the project root directory
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    # Build pytest command
    cmd = ["python", "-m", "pytest"]
    
    if test_type:
        cmd.extend(["-m", test_type])
    
    if coverage:
        cmd.extend(["--cov=.", "--cov-report=html", "--cov-report=term-missing"])
    
    if verbose:
        cmd.append("-v")
    
    if parallel:
        cmd.extend(["-n", "auto"])
    
    # Add test directory
    cmd.append("tests/")
    
    print(f"Running tests with command: {' '.join(cmd)}")
    print(f"Project root: {project_root}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n" + "=" * 50)
        print("✅ All tests passed!")
        return True
    except subprocess.CalledProcessError as e:
        print("\n" + "=" * 50)
        print(f"❌ Tests failed with exit code: {e.returncode}")
        return False


def run_specific_test(test_file):
    """Run a specific test file."""
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    cmd = ["python", "-m", "pytest", f"tests/{test_file}", "-v"]
    
    print(f"Running specific test: {test_file}")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, check=True)
        print("\n" + "=" * 50)
        print("✅ Test passed!")
        return True
    except subprocess.CalledProcessError as e:
        print("\n" + "=" * 50)
        print(f"❌ Test failed with exit code: {e.returncode}")
        return False


def run_coverage_report():
    """Generate coverage report."""
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)
    
    cmd = ["python", "-m", "coverage", "report", "--show-missing"]
    
    print("Generating coverage report...")
    print(f"Command: {' '.join(cmd)}")
    print("-" * 50)
    
    try:
        result = subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Coverage report failed with exit code: {e.returncode}")
        return False


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="Run tests for the workflow automation engine")
    parser.add_argument(
        "--type", "-t",
        choices=["unit", "integration", "api", "services", "core"],
        help="Run only tests of a specific type"
    )
    parser.add_argument(
        "--no-coverage", "-nc",
        action="store_true",
        help="Disable coverage reporting"
    )
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Reduce verbosity"
    )
    parser.add_argument(
        "--parallel", "-p",
        action="store_true",
        help="Run tests in parallel"
    )
    parser.add_argument(
        "--file", "-f",
        help="Run a specific test file"
    )
    parser.add_argument(
        "--coverage-only", "-co",
        action="store_true",
        help="Only generate coverage report"
    )
    
    args = parser.parse_args()
    
    if args.coverage_only:
        success = run_coverage_report()
        sys.exit(0 if success else 1)
    
    if args.file:
        success = run_specific_test(args.file)
        sys.exit(0 if success else 1)
    
    success = run_tests(
        test_type=args.type,
        coverage=not args.no_coverage,
        verbose=not args.quiet,
        parallel=args.parallel
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
