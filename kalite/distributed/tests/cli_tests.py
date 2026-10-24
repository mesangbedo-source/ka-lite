import sys
import time

from StringIO import StringIO

from django.test import TestCase
from thread import start_new_thread

from cherrypy import engine

from kalite import cli


class CLITestCase(TestCase):
    """
    Quick and dirty tests to ensure that we have a functional CLI
    """
    
    def test_manage(self):
        """
        Run the `manage videoscan` command synchronously
        """
        cli.manage("videoscan")

    def test_thread_manage(self):
        """
        Run the `manage help` command as thread
        """
        cli.manage("help", as_thread=True)

    def test_start(self):
        def cherry_py_stop_thread():
            time.sleep(15)
            engine.exit()

        # Because threads use the database with transactions, we can't run
        # the server in its own thread. Instead, we run `cli.start` from the
        # main thread and ask cherrypy to stop from a separate countdown
        # thread.
        start_new_thread(cherry_py_stop_thread, ())
        cli.start(
            debug=False,
            daemonize=False,
            args=[],
            skip_job_scheduler=True,
            port=8009,
        )


class PrintServerAddressTestCase(TestCase):
    """
    Regression test for a startup abort in minimal/headless environments.

    ``kalite start`` calls ``print_server_address()``.  That used to call
    ``get_ip_addresses()`` unguarded; the latter shells out to ``ifconfig``
    through ifcfg and raises ``OSError: [Errno 2] No such file or directory``
    when the binary is not installed (minimal container images, and many
    current distributions that only ship ``ip``).  The server therefore never
    started even though nothing else was wrong.
    """

    def setUp(self):
        self._orig_get_ip_addresses = cli.get_ip_addresses
        self._orig_get_urls_proxy = cli.get_urls_proxy
        self._orig_stdout = sys.stdout
        self._orig_stderr = sys.stderr

    def tearDown(self):
        cli.get_ip_addresses = self._orig_get_ip_addresses
        cli.get_urls_proxy = self._orig_get_urls_proxy
        sys.stdout = self._orig_stdout
        sys.stderr = self._orig_stderr

    def test_prints_loopback_address_when_interfaces_cannot_be_enumerated(self):
        def raise_oserror(*args, **kwargs):
            raise OSError(2, "No such file or directory")

        cli.get_ip_addresses = raise_oserror
        cli.get_urls_proxy = lambda *args, **kwargs: []

        out, err = StringIO(), StringIO()
        sys.stdout, sys.stderr = out, err
        try:
            cli.print_server_address(8008)
        finally:
            sys.stdout, sys.stderr = self._orig_stdout, self._orig_stderr

        self.assertIn("http://127.0.0.1:8008/", out.getvalue())
        self.assertIn("Unable to determine", err.getvalue())

    def test_prints_lan_addresses_when_available(self):
        cli.get_ip_addresses = lambda **kwargs: ["192.0.2.10"]
        cli.get_urls_proxy = lambda *args, **kwargs: []

        out, err = StringIO(), StringIO()
        sys.stdout, sys.stderr = out, err
        try:
            cli.print_server_address(8008)
        finally:
            sys.stdout, sys.stderr = self._orig_stdout, self._orig_stderr

        value = out.getvalue()
        self.assertIn("http://192.0.2.10:8008/", value)
        self.assertIn("http://127.0.0.1:8008/", value)
        self.assertEqual(err.getvalue(), "")
