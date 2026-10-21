"""Minimal verification: run pytest and smoke test, report pass/fail."""
import subprocess, sys

# Run pytest
r = subprocess.run(
    [sys.executable, "-m", "pytest", "-q"],
    cwd="c:\\Users\\bijaya.chauhan\\MLBB-draftAI\\windows",
    capture_output=True, text=True,
)
pytest_ok = "passed" in r.stdout and "failed" not in r.stdout

# Run smoke test
s = subprocess.run(
    [sys.executable, "-m", "receiver.smoke_test", "--token", "mlbb-phase1", "--frames", "30", "--fps", "15"],
    cwd="c:\\Users\\bijaya.chauhan\\MLBB-draftAI\\windows",
    capture_output=True, text=True,
)
smoke_ok = "RESULT: PASS" in s.stdout

print(f"pytest: {'PASS' if pytest_ok else 'FAIL'}")
print(f"smoke:  {'PASS' if smoke_ok else 'FAIL'}")
if not pytest_ok:
    print("pytest stderr:", r.stderr[-500:])
if not smoke_ok:
    print("smoke stderr:", s.stderr[-500:])
print(f"\nOVERALL: {'ALL CHECKS PASSED' if pytest_ok and smoke_ok else 'SOME CHECKS FAILED'}")