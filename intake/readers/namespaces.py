import importlib.metadata
import re
from functools import cache
from typing import Iterable

from intake.readers.utils import subclasses


class Namespace:
    acts_on = ()
    imports = "nolibrary"

    def __init__(self, reader):
        self.reader = reader

    @classmethod
    def check_imports(cls):
        """See if required packages are importable, but don't import them"""
        # TODO: this is copied from readers.py, should refactor to utils
        try:
            importlib.metadata.distribution(cls.imports)
            return True
        except (ImportError, ModuleNotFoundError, NameError):
            return False

    @classmethod
    @cache
    def _funcs(cls) -> Iterable[str]:
        if not cls.check_imports():
            return []
        # if self.reader.output_instance doesn't match self.acts_on
        cls.mod = importlib.import_module(cls.imports)
        return [f for f in dir(cls.mod) if callable(getattr(cls.mod, f))]

    def __dir__(self) -> Iterable[str]:
        # if self.reader.output_instance doesn't match self.acts_on:
        # return []
        return self._funcs()

    def __getattr__(self, item):
        dir(self)
        func = getattr(self.mod, item)
        return FuncHolder(self.reader, func)

    def __repr__(self):
        return f"{self.imports} namespace"


class FuncHolder:
    def __init__(self, reader, func):
        self.reader = reader
        self.func = func

    def __call__(self, *args, **kwargs):
        return self.reader.apply(self.func, **kwargs)


class np(Namespace):
    acts_on = (".*",)  # numpy works with a wide variety of objects
    imports = "numpy"


class ak(Namespace):
    acts_on = "awkward:Array", "dask_awkward:Array"
    imports = "awkward"


class xr(Namespace):
    acts_on = "xr.DataArray", "xr.DataSet"
    imports = "xarray"


class pd(Namespace):
    acts_on = "pandas:DataFrame"  # numpy works with a wide variety of objects
    imports = "pandas"


def get_namespaces(reader):
    out = {}
    for space in subclasses(Namespace):
        if any(re.match(act, reader.output_instance) for act in space.acts_on):
            out[space.__name__] = space(reader)
    return out