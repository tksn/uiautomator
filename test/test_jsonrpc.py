#!/usr/bin/env python
# -*- coding: utf-8 -*-

import json
import unittest
from mock import MagicMock, patch
from uiautomatorminus import jsonrpc_call, JsonRPCClient
import os
import requests


class PostResponse(object):
    def __init__(self, text):
        self.text = text
    def json(self):
        return json.loads(self.text)


class TestJsonRPCMethod_id(unittest.TestCase):

    @patch('requests.post', return_value=PostResponse('{"result": true}'))
    def test_id(self, mock_post):
        prev_id = None
        for i in range(20):
            jsonrpc_call(url='', timeout=30, call_desc={'method': 'method'})
            rpcdata = mock_post.call_args[1]['json']
            self.assertTrue(isinstance(rpcdata['id'], str))
            self.assertTrue(len(rpcdata['id']) > 0)
            self.assertNotEqual(rpcdata['id'], prev_id)
            prev_id = rpcdata['id']


class TestJsonRPCMethod_call(unittest.TestCase):

    def jsonrpc_call(self, *args, **kwargs):
        return jsonrpc_call(
            url='http://localhost/jsonrpc',
            timeout=30, call_desc={'method': 'ping', 'args': args or kwargs})

    @patch('requests.post')
    def test_normal_call(self, mock_post):
        mock_post.return_value = PostResponse(
            '{"result": "pong", "error": null, "id": "DKNCJDLDJJ"}')
        self.assertEqual("pong", self.jsonrpc_call())

        mock_post.return_value = PostResponse(
            '{"result": "pong", "id": "JDLSFJLILJEMNC"}')
        self.assertEqual("pong", self.jsonrpc_call())
        self.assertEqual("pong", self.jsonrpc_call(1, 2, "str", {"a": 1}, ["1"]))
        self.assertEqual("pong", self.jsonrpc_call(a=1, b=2))

    @patch('requests.post')
    def test_normal_call_error(self, mock_post):
        mock_post.side_effect = requests.exceptions.ConnectionError('error')
        with self.assertRaises(Exception):
            self.jsonrpc_call()

        mock_post.return_value = PostResponse(
            '{"result": "pong", "error": {"code": -513937, "message": "error message."}, '
            '"id": "fGasV62G"}')
        with self.assertRaises(Exception):
            self.mejsonrpc_callhod()


class TestJsonRPCClient(unittest.TestCase):

    def jsonrpc_call(self, method, *args, **kwargs):
        return jsonrpc_call(
            url='http://localhost/jsonrpc',
            timeout=30, call_desc={'method': method, 'args': args or kwargs})

    @patch('requests.post')
    def test_jsonrpc(self, mock_post):
        mock_post.return_value = PostResponse(
            '{"result": "pong", "id": "JDLSFJLILJEMNC"}')
        client = JsonRPCClient(self.jsonrpc_call)
        self.assertEqual(client.ping(), 'pong')

        mock_post.return_value = PostResponse(
            '{"result": {"width": 10, "height": 20}, "id": "JDLSFJLILJEMNC"}')
        self.assertEqual(client.info(), {"width": 10, "height": 20})
