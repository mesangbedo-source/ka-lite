import os
import shutil
import stat
import tempfile
import unittest

from django.test import TestCase

from kalite.contentload import settings as contentload_settings


class EnsureDirTestCase(TestCase):
    """
    Regression tests for directory creation in ``contentload.settings``.

    Importing ``kalite.contentload.settings`` used to call ``os.mkdir()`` on
    ``CONTENT_ROOT/assessment`` unconditionally.  When ``CONTENT_ROOT`` is a
    read-only mount (containers, read-only network shares) the resulting
    ``OSError`` propagated out of the import and every request failed with a
    server error.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        for root, dirs, _files in os.walk(self.tmpdir):
            os.chmod(root, 0o755)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_missing_directory_tree(self):
        target = os.path.join(self.tmpdir, "assessment", "khan")
        self.assertTrue(contentload_settings.ensure_dir(target))
        self.assertTrue(os.path.isdir(target))

    def test_is_idempotent_for_existing_directories(self):
        target = os.path.join(self.tmpdir, "assessment")
        self.assertTrue(contentload_settings.ensure_dir(target))
        self.assertTrue(contentload_settings.ensure_dir(target))

    @unittest.skipIf(
        hasattr(os, "geteuid") and os.geteuid() == 0,
        "permission checks are not enforced for uid 0",
    )
    def test_read_only_parent_does_not_raise(self):
        read_only = os.path.join(self.tmpdir, "readonly")
        os.mkdir(read_only)
        os.chmod(read_only, stat.S_IRUSR | stat.S_IXUSR)
        try:
            target = os.path.join(read_only, "assessment")
            self.assertFalse(contentload_settings.ensure_dir(target))
            self.assertFalse(os.path.exists(target))
        finally:
            os.chmod(read_only, 0o755)

    def test_module_import_survives_read_only_content_root(self):
        """
        The assessment roots are computed at import time; importing the module
        again with a read-only CONTENT_ROOT must not raise.
        """
        read_only = os.path.join(self.tmpdir, "content-ro")
        os.mkdir(read_only)
        os.chmod(read_only, stat.S_IRUSR | stat.S_IXUSR)
        try:
            from django.test.utils import override_settings
            import imp

            with override_settings(CONTENT_ROOT=read_only):
                # re-execute the module body against the overridden settings
                try:
                    imp.reload(contentload_settings)
                except OSError as exc:  # pragma: no cover - regression guard
                    self.fail(
                        "importing contentload.settings with a read-only "
                        "CONTENT_ROOT raised %r" % (exc,)
                    )
                self.assertEqual(
                    contentload_settings.ASSESSMENT_ITEM_ROOT,
                    os.path.join(read_only, "assessment"),
                )
        finally:
            os.chmod(read_only, 0o755)
            imp.reload(contentload_settings)
