#  Copyright (c) 2016 by Enthought, Inc.
#  All rights reserved.

try:  # pragma: no cover
    from ._version import (
        version as __version__,
        is_released as __is_released__,
        git_revision as __git_revision__,
    )
except ImportError:  # pragma: no cover
    __is_released__ = False
    __version__ = __git_revision__ = "unknown"
