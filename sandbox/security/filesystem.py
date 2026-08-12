import os.path

_real_open = open


def make_guarded_directory(allowed_directories: list):
    exact = set()
    for entry in allowed_directories:
        exact.add(os.path.realpath(entry))

    def is_allowed(path: str) -> bool:
        resolved = os.path.realpath(path)
        for d in exact:
            if resolved == d or resolved.startswith(d + os.sep):
                return True
        return False

    def guarded_open(file, *args, **kwargs):
        if is_allowed(file):
            return _real_open(file, *args, **kwargs)
        raise PermissionError(f"directory '{file}' is not allowed")

    return guarded_open
