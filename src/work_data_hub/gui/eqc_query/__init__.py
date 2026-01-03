"""
EQC Quick Query GUI Package.

A tkinter-based GUI for quick EQC lookups with optional database persistence.
"""

from work_data_hub.gui.eqc_query.app import EqcQueryApp
from work_data_hub.gui.eqc_query.controller import EqcQueryController

__all__ = ["EqcQueryApp", "EqcQueryController"]
