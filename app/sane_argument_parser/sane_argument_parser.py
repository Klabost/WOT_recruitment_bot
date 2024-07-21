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

    @classmethod
    def non_negative_int(cls, value):
        """
        Check if the value is a non negative integer.
        """
        ivalue = int(value)
        if ivalue < 0:
            raise argparse.ArgumentTypeError(f"{value} is an invalid non negative int value")
        return ivalue
