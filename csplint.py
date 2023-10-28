import ast
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from subprocess import run
from typing import Iterable


def main(argv: Sequence[str] = sys.argv[1:]):
    root_dir = Path(argv[0] if argv else ".")
    pyproject_path = root_dir / "package/pyproject.toml"
    if not pyproject_path.exists():
        raise SystemExit(0)
    result = run(["tomljson", str(pyproject_path)], text=True, shell=True)
    if result.returncode != 0:
        raise SystemExit(result.stderr)

    pyproject = json.loads(result.stdout)
    main_package_name = pyproject["tool"]["poetry"]["name"]
    package_names = {dct["include"] for dct in pyproject["tool"]["poetry"].get("packages", [])} or {main_package_name}

    exceptions = []
    exceptions.extend(check_non_package_imports(pyproject_path, package_names))
    exceptions.extend(check_non_relative_imports(package_names))

    print("\n".join(exceptions))
    raise SystemExit(1 if exceptions else 0)


def check_non_relative_imports(package_names: Iterable[str]) -> Iterable[str]:
    for package_name in package_names:
        for f in Path("package").joinpath(package_name).glob("**/*.py"):
            for node, import_, is_relative in parse_imports_from_file(f):
                if (import_.startswith(package_name) and not is_relative) or import_.startswith(
                    f"package.{package_name}"
                ):
                    yield (
                        f"Found a non-relative import from own package at: '{f}:{node.lineno}'. "
                        "Use relative imports instead."
                    )


def check_non_package_imports(pyproject_path: Path, package_names: Iterable[str]) -> Iterable[str]:
    for f in Path().glob("**/*.py"):
        if pyproject_path.parent not in f.parents:
            for node, import_, is_relative in parse_imports_from_file(f):
                for name in package_names:
                    if import_.startswith(name) and not is_relative:
                        yield (
                            f"Found import from own package at: '{f}:{node.lineno}'. Use 'from package.{name}' instead."
                        )


def parse_imports_from_file(file_path: Path) -> Iterable[tuple[ast.AST, str, bool]]:
    tree = ast.parse(file_path.read_text(), file_path.name)
    for node in ast.walk(tree):
        if isinstance(node, (ast.ImportFrom, ast.Import)):
            for module, relative in get_import_modules(node):
                yield (node, module, relative)


def get_import_modules(node: ast.ImportFrom | ast.Import) -> set[tuple[str, bool]]:
    if isinstance(node, ast.ImportFrom):
        return {(node.module, node.level != 0)} if node.module else set()
    else:
        return {(alias.name, False) for alias in node.names}


if __name__ == "__main__":
    main()
