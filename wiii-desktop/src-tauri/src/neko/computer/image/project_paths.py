from pathlib import PurePosixPath


def protected_path(path: PurePosixPath) -> bool:
    protected_names = {".git", ".ssh", ".aws", ".azure", ".gnupg", ".npmrc", ".pypirc", ".wiii-perf-secret"}
    return any(
        part.casefold() in protected_names
        or part.casefold().startswith(".env")
        or PurePosixPath(part).suffix.casefold() in {".pem", ".key", ".p12", ".pfx"}
        for part in path.parts
    )
