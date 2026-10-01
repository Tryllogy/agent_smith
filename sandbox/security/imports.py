import builtins

_real_import = builtins.__import__


def make_guarded_import(authorized_imports: list):
    exact = set()
    prefixes = []
    for entry in authorized_imports:
        if entry.endswith(".*"):
            prefixes.append(entry[:-2])
        else:
            exact.add(entry)

    def is_allowed(name: str) -> bool:
        if name in exact:
            return True
        return any(name == p or name.startswith(p + ".") for p in prefixes)

    def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
        if is_allowed(name):
            return _real_import(name, globals, locals, fromlist, level)
        raise ImportError(f"import of '{name}' is not allowed")

    return guarded_import
