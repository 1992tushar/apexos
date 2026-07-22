"""Integrations module — external system bridges (QuickBooks Online).

Feature-flagged and non-blocking: when the flag is off, every method no-ops
cleanly. No core flow depends on this module (docs §2.9 / Phase C).
"""
