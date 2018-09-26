"""
This module contains all plagiarism providers.

A plagiarism provider is a class that extends and implements the missing
functions from :class:`psef.plagiarism.PlagiarismProvider`.

:license: AGPLv3, see LICENSE for details.
"""


def init_app(_: object) -> None:
    from . import jplag  # pylint: disable=unused-variable
