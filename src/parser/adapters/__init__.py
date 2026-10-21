"""Collector schema adapters used before canonical normalization."""

from .bloodhound_v3 import adapt_bloodhound_v3_records

__all__ = ["adapt_bloodhound_v3_records"]
