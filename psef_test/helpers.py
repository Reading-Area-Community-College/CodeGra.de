import pytest


def create_marker(marker):
    def outer(*vals, **kwargs):
        def inner(vals):
            if vals is not None and isinstance(vals, tuple):
                return pytest.param(*vals, marks=marker(**kwargs))
            else:
                return pytest.param(vals, marks=marker(**kwargs))

        if kwargs:
            return inner
        return inner(*vals)

    return outer
