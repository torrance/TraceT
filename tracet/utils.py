def truthy(val) -> bool:
    # Bool
    if isinstance(val, bool):
        return val

    # Int/Floats 0 -> False, rest -> True
    try:
        return bool(float(val))
    except ValueError:
        pass

    # String values
    if isinstance(val, str):
        string = val.strip().lower()
        if string in ("0", "false", "no"):
            return False
        elif string in ("1", "true", "yes"):
            return True

    raise ValueError(f"Invalid boolean value: '{string}'")