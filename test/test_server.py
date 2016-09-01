#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import unittest
from mock import MagicMock, patch, call
from uiautomatorminus import AutomatorServer, JsonRPCError
import requests


class PostResponse(object):
    def __init__(self, text):
        self.text = text
    def json(self):
        return json.loads(self.text)


class TestAutomatorServer(unittest.TestCase):

    def setUp(self):
        self.Adb_patch = patch('uiautomatorminus.Adb')
        self.Adb = self.Adb_patch.start()

    def tearDown(self):
        self.Adb_patch.stop()

    def test_local_port(self):
        self.assertEqual(AutomatorServer("1234", 9010).local_port, 9010)
        self.Adb.assert_called_once_with(serial="1234", adb_server_host=None, adb_server_port=None)

    def test_local_port_forwarded(self):
        self.Adb.return_value.forward_list.return_value = [
            ("1234", "tcp:1001", "tcp:9009"),
            ("1234", "tcp:1000", "tcp:9008")
        ]
        self.Adb.return_value.device_serial.return_value = "1234"
        self.assertEqual(AutomatorServer("1234").local_port, 1000)

    def test_local_port_scanning(self):
        with patch('uiautomatorminus.next_local_port') as next_local_port:
            self.Adb.return_value.forward_list.return_value = []
            next_local_port.return_value = 1234
            self.assertEqual(AutomatorServer("abcd", None).local_port,
                             next_local_port.return_value)

            next_local_port.return_value = 14321
            self.Adb.return_value.forward_list.return_value = Exception("error")
            self.assertEqual(AutomatorServer("abcd", None).local_port,
                             next_local_port.return_value)

    def test_device_port(self):
        self.assertEqual(AutomatorServer().device_port, 9008)

    def test_start_success(self):
        server = AutomatorServer()
        server.ping = MagicMock()
        server.ping.return_value = "pong"
        server.adb = MagicMock()
        server.start()

        def find_call_with_args(*target_args):
            for call_args in server.adb.cmd.call_args_list:
                args, kwargs = call_args
                found = True
                for target_arg in target_args:
                    if target_arg not in args:
                        found = False
                        break
                if found:
                    return call_args
            return None

        self.assertIsNotNone(find_call_with_args('shell', 'am', 'instrument'))

    def test_start_error(self):
        server = AutomatorServer()
        server.ping = MagicMock()
        server.ping.return_value = None
        server.adb = MagicMock()
        server.adb.cmd.return_value = cmd_ret = MagicMock()
        cmd_ret.communicate.return_value = ('', '')
        with patch("time.sleep"):
            with self.assertRaises(IOError):
                server.start()

    def test_auto_start(self):
        with patch("uiautomatorminus.jsonrpc_call") as jsonrpc_call:
            jsonrpc_call.side_effect = [
                requests.exceptions.ConnectionError('error'), 'ok']
            server = AutomatorServer()
            server.restart = MagicMock()
            self.assertEqual("ok", server.jsonrpc().any_method())
            assert server.restart.called
        with patch("uiautomatorminus.jsonrpc_call") as jsonrpc_call:
            jsonrpc_call.side_effect = [JsonRPCError(-32000-1, "error msg"), "ok"]
            server = AutomatorServer()
            server.restart = MagicMock()
            self.assertEqual("ok", server.jsonrpc().any_method())
            server.restart.assert_called_once_with()
        with patch("uiautomatorminus.jsonrpc_call") as jsonrpc_call:
            jsonrpc_call.side_effect = JsonRPCError(-32000-2, "error msg")
            server = AutomatorServer()
            server.restart = MagicMock()
            with self.assertRaises(JsonRPCError):
                server.jsonrpc().any_method()

    def test_start_ping(self):
        with patch("uiautomatorminus.jsonrpc_call") as jsonrpc_call:
            jsonrpc_call.return_value = "pong"
            server = AutomatorServer()
            server.adb = MagicMock()
            server.adb.forward.return_value = 0
            self.assertEqual(server.ping(), "pong")

    def test_start_ping_none(self):
        with patch("uiautomatorminus.JsonRPCClient") as JsonRPCClient:
            JsonRPCClient.return_value.ping.side_effect = Exception("error")
            server = AutomatorServer()
            self.assertEqual(server.ping(), None)


class TestAutomatorServer_Stop(unittest.TestCase):

    def setUp(self):
        try:
            import urllib2
            self.urlopen_patch = patch('urllib2.urlopen')
        except:
            self.urlopen_patch = patch('urllib.request.urlopen')
        finally:
            self.urlopen = self.urlopen_patch.start()

    def tearDown(self):
        self.urlopen_patch.stop()

    @patch('requests.get')
    def test_screenshot(self, mock_get):
        server = AutomatorServer()
        server.sdk_version = MagicMock()
        server.sdk_version.return_value = 18
        class GetResponse(object):
            content = b'123456'
        mock_get.return_value = GetResponse()
        self.assertEqual(server.screenshot(), b"123456")

    @patch('requests.post')
    def test_stop_started_server(self, mock_post):
        mock_post.return_value = PostResponse('{"result": null}')
        server = AutomatorServer()
        server.adb = MagicMock()
        server.uiautomator_process = process = MagicMock()
        process.poll.return_value = None
        server.stop()
        self.assertTrue(process.communicate.called)

        server.uiautomator_process = process = MagicMock()
        process.poll.return_value = None        
        mock_post.side_effect = requests.exceptions.ConnectionError("error")
        server.stop()
        process.kill.assert_called_once_with()

    @patch('requests.post', return_value=PostResponse('{"result": "pong"}'))
    def test_restart_server(self, mock_post):
        server = AutomatorServer()
        server.adb = MagicMock()
        server.restart()

        def get_index(kw):
            for i, args in enumerate(server.adb.cmd.call_args_list):
                if kw in args[0]:
                    return i
            return -1

        istop = get_index('force-stop')
        istart = get_index('instrument')
        self.assertTrue(istop >= 0 and istart >= 0)
        self.assertTrue(istop < istart)


class TestJsonRPCError(unittest.TestCase):

    def testJsonRPCError(self):
        e = JsonRPCError(200, "error")
        self.assertEqual(200, e.code)
        self.assertTrue(len(str(e)) > 0)
        e = JsonRPCError("200", "error")
        self.assertEqual(200, e.code)
