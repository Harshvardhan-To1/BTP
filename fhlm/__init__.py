"""fhlm - Fronthaul Load Management research prototype.

Simulates N O-RAN split 7-2x cells (O-DU -> O-RU downlink U-plane) sharing one
packet-switched fronthaul aggregation link, and compares budget-allocation
controllers that decide, once per control interval, how much of the link each
cell may use.
"""

__version__ = "0.1.0"
