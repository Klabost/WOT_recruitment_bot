"""Extend functionality of ArgumentParser class"""
import argparse

class SaneArgumentParser(argparse.ArgumentParser):
    """
    Argument parser for which arguments are required on the CLI unless:
      - required=False is provided
        and/or
      - a default value is provided that is not None.
    """
    def add_argument(self, *args, default=None, **kwargs):
        if default is None:
            # Tentatively make this argument required
            kwargs.setdefault("required", True)
        super().add_argument(*args, **kwargs, default=default)
