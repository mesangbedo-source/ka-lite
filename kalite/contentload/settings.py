"""

New settings pattern

See:
https://github.com/learningequality/ka-lite/issues/4054
https://github.com/learningequality/ka-lite/issues/3757

All settings for the topic_tools app should be defined here, they can
only on django.conf.settings
"""
import os
from django.conf import settings

logging = settings.LOG


def ensure_dir(path):
    """
    Create ``path`` if it does not exist yet.

    ``CONTENT_ROOT`` is not necessarily writable: it may be a read-only
    bind-mount, a read-only network share, or a directory owned by another
    user.  Failing to create a directory there must not abort the import of
    this module, because that would make the entire application unusable for
    such deployments.
    """
    if os.path.isdir(path):
        return True
    try:
        os.makedirs(path)
    except OSError as exc:
        logging.warning(
            "Unable to create content directory {path}: {exc}. "
            "Continuing with a read-only content root.".format(path=path, exc=exc)
        )
        return False
    return True


# Where assessment items are stored in general (but no additional channels
# exist yet so it's all hard-coded for KHAN_ASSESSMENT_ITEM_ROOT below)
ASSESSMENT_ITEM_ROOT = os.path.join(settings.CONTENT_ROOT, 'assessment')
ensure_dir(ASSESSMENT_ITEM_ROOT)

KHAN_ASSESSMENT_ITEM_ROOT = os.path.join(ASSESSMENT_ITEM_ROOT, 'khan')
ensure_dir(KHAN_ASSESSMENT_ITEM_ROOT)
