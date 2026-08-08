"""
preflight.py — Is this machine ready to run.

Two checks, both about things the application can act on: whether the Python
packages match the set this release was tested against, and how to install
Ollama on this operating system.

An earlier version also read the machine's memory and recommended models sized
to it. That was removed. Anyone who has installed Python, made a virtual
environment and started Ollama has already chosen their models, and a
recommendation baked into code goes stale every time the landscape moves.
Model guidance belongs in the README, where it can be corrected without a
release.
"""

import platform
from importlib.metadata import PackageNotFoundError, version

# The versions this release was built and tested against. Requirements are
# pinned, so a mismatch means something was upgraded afterwards.
TESTED = {
    "streamlit": "1.61.0",
    "starlette": "0.49.1",
    "chromadb": "1.5.9",
    "ollama": "0.6.2",
}


def system_label() -> str:
    """A plain name for this operating system."""
    system = platform.system()
    machine = platform.machine()
    if system == "Darwin":
        return "Mac, Apple silicon" if machine in ("arm64", "aarch64") else "Mac, Intel"
    return {"Linux": "Linux", "Windows": "Windows"}.get(system, system or "unknown")


def install_instructions() -> list[str]:
    """How to install Ollama here. One instruction per line."""
    system = platform.system()
    if system == "Darwin":
        return [
            "brew install ollama",
            "Or download the installer from ollama.com and drag Ollama to Applications.",
            "Then start it:  ollama serve",
        ]
    if system == "Linux":
        return [
            "curl -fsSL https://ollama.com/install.sh | sh",
            "The installer sets up a service that starts on boot.",
        ]
    if system == "Windows":
        return [
            "Download the installer from ollama.com and run it.",
            "Ollama starts automatically after installation.",
        ]
    return ["Install Ollama from ollama.com."]


def dependency_problems() -> list[str]:
    """
    Installed packages that differ from the tested set.

    Pinned requirements protect a clean install. This catches the case where a
    package was upgraded afterwards, so a mismatch reads as a sentence rather
    than a stack trace several screens later.
    """
    problems = []
    for package, expected in TESTED.items():
        try:
            installed = version(package)
        except PackageNotFoundError:
            problems.append(f"{package} is not installed.")
            continue
        if installed != expected:
            problems.append(
                f"{package} {installed} is installed; this release is tested "
                f"with {expected}."
            )
    return problems
