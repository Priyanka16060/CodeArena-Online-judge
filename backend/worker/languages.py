"""
Per-language definitions for the sandbox.

Each language maps to:
  - a pinned Docker image (never `:latest` — reproducibility matters for a judge)
  - the source filename the code gets written to inside the shared volume
  - an optional compile command (list[str], run inside the container)
  - the run command (list[str]) that executes against stdin

All commands are plain argv lists, never shell strings, to avoid any
shell-injection surface even though the source itself is attacker-controlled
by design (that's the whole point of the sandbox).
"""

from dataclasses import dataclass

from app.models import Language


@dataclass(frozen=True)
class LangSpec:
    image: str
    source_filename: str
    compile_cmd: list[str] | None
    run_cmd: list[str]


LANGUAGE_SPECS: dict[Language, LangSpec] = {
    Language.PYTHON: LangSpec(
        image="python:3.11.9-slim",
        source_filename="main.py",
        compile_cmd=None,
        run_cmd=["python3", "main.py"],
    ),
    Language.CPP: LangSpec(
        image="gcc:13.2.0",
        source_filename="main.cpp",
        compile_cmd=["g++", "-O2", "-std=c++17", "-o", "main", "main.cpp"],
        run_cmd=["./main"],
    ),
    Language.JAVA: LangSpec(
        image="eclipse-temurin:17.0.11_9-jdk",
        source_filename="Main.java",
        compile_cmd=["javac", "Main.java"],
        run_cmd=["java", "-XX:+UseSerialGC", "-Xshare:off", "Main"],
    ),
    Language.JAVASCRIPT: LangSpec(
        image="node:20.15.1-slim",
        source_filename="main.js",
        compile_cmd=None,
        run_cmd=["node", "main.js"],
    ),
}
