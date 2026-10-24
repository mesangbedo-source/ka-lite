import os
import shutil
import tempfile

from django.test import TestCase
from django.test.utils import override_settings

from kalite.topic_tools import base


class AvailableContentDatabasesTestCase(TestCase):
    """
    Regression tests for ``available_content_databases()``.

    Before the fix, the function called ``glob.iglob()`` with the database
    *directory* instead of a pattern, so it always yielded nothing.  Any code
    path relying on it (e.g. ``get_video_from_youtube_id``) silently found no
    content databases.
    """

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        for filename in (
            "content_khan_en.sqlite",
            "content_khan_fr.sqlite",
            "content_otherchannel_es.sqlite",
            "data.sqlite",
            "notes.txt",
        ):
            with open(os.path.join(self.tmpdir, filename), "w"):
                pass

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_yields_channel_and_language_for_each_content_database(self):
        with override_settings(DEFAULT_DATABASE_DIR=self.tmpdir):
            found = sorted(base.available_content_databases())
        self.assertEqual(
            found,
            [("khan", "en"), ("khan", "fr"), ("otherchannel", "es")],
        )

    def test_ignores_files_that_are_not_content_databases(self):
        with override_settings(DEFAULT_DATABASE_DIR=self.tmpdir):
            found = [pair for pair in base.available_content_databases()]
        for channel, language in found:
            self.assertNotEqual(language, "sqlite")
        self.assertEqual(len(found), 3)

    def test_yields_nothing_for_an_empty_directory(self):
        empty_dir = tempfile.mkdtemp()
        try:
            with override_settings(DEFAULT_DATABASE_DIR=empty_dir):
                self.assertEqual(list(base.available_content_databases()), [])
        finally:
            shutil.rmtree(empty_dir, ignore_errors=True)

    def test_does_not_descend_into_subdirectories(self):
        subdir = os.path.join(self.tmpdir, "nested")
        os.mkdir(subdir)
        with open(os.path.join(subdir, "content_khan_en.sqlite"), "w"):
            pass
        with override_settings(DEFAULT_DATABASE_DIR=self.tmpdir):
            found = sorted(base.available_content_databases())
        self.assertEqual(
            found,
            [("khan", "en"), ("khan", "fr"), ("otherchannel", "es")],
        )
