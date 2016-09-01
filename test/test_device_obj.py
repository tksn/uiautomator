#!/usr/bin/env python
# -*- coding: utf-8 -*-

import unittest
from mock import MagicMock, call
from uiautomatorminus import AutomatorDeviceObject, Selector, AutomatorDeviceNamedUiObject


class TestDeviceObjInit(unittest.TestCase):

    def setUp(self):
        self.device = MagicMock()
        self.device.server.jsonrpc.return_value = MagicMock()

    def test_init(self):
        kwargs = {"text": "text", "className": "android"}
        self.device_obj = AutomatorDeviceObject(self.device,
                                                Selector(**kwargs))
        self.assertEqual(self.device_obj.selector,
                         Selector(**kwargs))


def fake_jsonrpc_method(rpc_client, method, **kwargs):
    rpc_method = MagicMock(**kwargs)
    rpc_client.attach_mock(rpc_method, method)
    return rpc_method


class TestDeviceObj(unittest.TestCase):

    def setUp(self):
        self.device = MagicMock()
        self.rpc_client = MagicMock()
        self.device.server.jsonrpc.return_value = self.rpc_client
        self.kwargs = {"text": "text", "className": "android"}
        self.obj = AutomatorDeviceObject(self.device,
                                         Selector(**self.kwargs))

    def fake_jsonrpc_method(self, method, **kwargs):
        return fake_jsonrpc_method(self.rpc_client, method, **kwargs)

    def test_child_selector(self):
        kwargs = {"text": "child text", "className": "android"}
        obj = self.obj.child_selector(**kwargs)
        self.assertEqual(len(obj.selector['childOrSibling']), 1)
        self.assertEqual(obj.selector['childOrSibling'][0], 'child')
        self.assertEqual(len(obj.selector['childOrSiblingSelector']), 1)
        self.assertEqual(obj.selector['childOrSiblingSelector'][0], Selector(**kwargs))

    def test_from_parent(self):
        kwargs = {"text": "parent text", "className": "android"}
        obj = self.obj.from_parent(**kwargs)
        self.assertEqual(len(obj.selector['childOrSibling']), 1)
        self.assertEqual(obj.selector['childOrSibling'][0], 'sibling')
        self.assertEqual(len(obj.selector['childOrSiblingSelector']), 1)
        self.assertEqual(obj.selector['childOrSiblingSelector'][0], Selector(**kwargs))

    def test_exists(self):
        method = self.fake_jsonrpc_method(method='exist', return_value=True)
        self.assertTrue(self.obj.exists)
        self.assertEqual(method.call_args_list, [call(self.obj.selector)])

        method = self.fake_jsonrpc_method(method='exist', return_value=False)
        self.assertFalse(self.obj.exists)
        self.assertEqual(method.call_args_list, [call(self.obj.selector)])

    def test_info(self):
        info = {"text": "item text"}
        method = self.fake_jsonrpc_method(method='objInfo', return_value=info)
        self.assertEqual(self.obj.info,
                         info)
        method.assert_called_once_with(self.obj.selector)

    def test_info_attr(self):
        info = {'contentDescription': '',
                'checked': False,
                'scrollable': False,
                'text': '',
                'packageName': 'android',
                'selected': False,
                'enabled': True,
                'bounds': {'top': 0,
                           'left': 0,
                           'right': 720,
                           'bottom': 1184},
                'className':
                'android.widget.FrameLayout',
                'focusable': False,
                'focused': False,
                'clickable': False,
                'checkable': False,
                'chileCount': 2,
                'longClickable': False,
                'visibleBounds': {'top': 0,
                                  'left': 0,
                                  'right': 720,
                                  'bottom': 1184}}
        method = self.fake_jsonrpc_method(method='objInfo', return_value=info)
        self.assertEqual(self.obj.info, info)
        method.assert_called_once_with(self.obj.selector)
        self.assertEqual(self.obj.description, info["contentDescription"])
        for k in info:
            self.assertEqual(getattr(self.obj, k), info[k])

        with self.assertRaises(AttributeError):
            self.obj.not_exists

    def test_text(self):
        method = self.fake_jsonrpc_method(method='clearTextField', return_value=None)
        self.obj.set_text(None)
        self.obj.set_text("")
        self.obj.clear_text()
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector), call(self.obj.selector), call(self.obj.selector)])

        method = self.fake_jsonrpc_method(method='setText', return_value=False)
        texts = ["abc", "123", "()#*$&"]
        for text in texts:
            self.assertFalse(self.obj.set_text(text))
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, t) for t in texts])

    def test_click(self):
        method = self.fake_jsonrpc_method(method='click', return_value=False)
        corners = ["tl", "topleft", "br", "bottomright"]
        for c in corners:
            self.assertFalse(self.obj.click(c))
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, c) for c in corners])

        method = self.fake_jsonrpc_method(method='click', return_value=True)
        corners = ["tl", "topleft", "br", "bottomright"]
        for c in corners:
            self.assertTrue(getattr(self.obj.click, c)())
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, c) for c in corners])

        method = self.fake_jsonrpc_method(method='click', return_value=True)
        self.assertTrue(self.obj.click())
        method.assert_called_once_with(self.obj.selector)

    def test_click_wait(self):
        method = self.fake_jsonrpc_method(method='clickAndWaitForNewWindow', return_value=True)
        self.assertTrue(self.obj.click.wait(timeout=321))
        method.assert_called_once_with(self.obj.selector, 321)

    def test_long_click(self):
        method = self.fake_jsonrpc_method(method='longClick', return_value=False)
        corners = ["tl", "topleft", "br", "bottomright"]
        for c in corners:
            self.assertFalse(self.obj.long_click(c))
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, c) for c in corners])

        method = self.fake_jsonrpc_method(method='longClick', return_value=True)
        corners = ["tl", "topleft", "br", "bottomright"]
        for c in corners:
            self.assertTrue(getattr(self.obj.long_click, c)())
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, c) for c in corners])

        method = self.fake_jsonrpc_method(method='longClick', return_value=True)
        self.assertTrue(self.obj.long_click())
        method.assert_called_once_with(self.obj.selector)

    def test_long_click_using_swipe(self):
        self.device.long_click.return_value = False
        method = self.fake_jsonrpc_method(method='objInfo', return_value={
            'longClickable': False,
            'visibleBounds': {
                'top': 0,
                'bottom': 60,
                'left': 0,
                'right': 60
            }
        })
        corners = ["tl", "topleft", "br", "bottomright"]
        for c in corners:
            self.assertFalse(self.obj.long_click(c))
        self.assertEqual(self.device.long_click.call_args_list,
                         [call(10, 10), call(10, 10), call(50, 50), call(50, 50)])

        self.device.long_click = MagicMock()
        self.device.long_click.return_value = True
        corners = ["tl", "topleft", "br", "bottomright"]
        for c in corners:
            self.assertTrue(getattr(self.obj.long_click, c)())
        self.assertEqual(self.device.long_click.call_args_list,
                         [call(10, 10), call(10, 10), call(50, 50), call(50, 50)])

        self.device.long_click = MagicMock()
        self.device.long_click.return_value = True
        self.assertTrue(self.obj.long_click())
        self.device.long_click.assert_called_once_with(30, 30)

    def test_drag_to(self):
        method = self.fake_jsonrpc_method(method='dragTo', return_value=False)
        self.assertFalse(self.obj.drag.to(10, 20, steps=10))
        method.return_value = True
        self.assertTrue(self.obj.drag.to(x=10, y=20, steps=20))

        sel = {"text": "text..."}
        self.assertTrue(self.obj.drag.to(steps=30, **sel))
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, 10, 20, 10),
                          call(self.obj.selector, 10, 20, 20),
                          call(self.obj.selector, Selector(**sel), 30)])

    def test_gesture(self):
        method = self.fake_jsonrpc_method(method='gesture', return_value=True)
        self.assertTrue(self.obj.gesture((1, 1), (2, 2), (3, 3), (4, 4), 100))
        self.assertTrue(self.obj.gesture(4, 3).to(2, 1, 20))
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, {'x':1, 'y': 1}, {'x':2, 'y':2}, {'x':3, 'y':3}, {'x':4, 'y':4}, 100), call(self.obj.selector, 4, 3, 2, 1, 20)])

    def test_pinch(self):
        method = self.fake_jsonrpc_method(method='pinchIn', return_value=True)
        self.assertTrue(self.obj.pinch.In(percent=90, steps=30))
        self.assertTrue(self.obj.pinch("in", 80, 40))
        self.assertTrue(self.obj.pinch("In", 70, 50))
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, 90, 30), call(self.obj.selector, 80, 40), call(self.obj.selector, 70, 50)])

        method = self.fake_jsonrpc_method(method='pinchOut', return_value=True)
        self.assertTrue(self.obj.pinch.Out(percent=90, steps=30))
        self.assertTrue(self.obj.pinch("out", 80, 40))
        self.assertTrue(self.obj.pinch("Out", 70, 50))
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, 90, 30), call(self.obj.selector, 80, 40), call(self.obj.selector, 70, 50)])

    def test_swipe(self):
        method = self.fake_jsonrpc_method(method='swipe', return_value=True)
        dirs = ["up", "down", "right", "left"]
        for d in dirs:
            self.assertTrue(self.obj.swipe(d, 30))
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, d, 30) for d in dirs])

        method = self.fake_jsonrpc_method(method='swipe', return_value=True)
        dirs = ["up", "down", "right", "left"]
        for d in dirs:
            self.assertTrue(getattr(self.obj.swipe, d)(steps=30))
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, d, 30) for d in dirs])

    def test_fling(self):
        method = self.fake_jsonrpc_method(method='flingForward', return_value=True)
        self.assertTrue(self.obj.fling.horiz.forward())
        self.assertTrue(self.obj.fling.horizentally.forward())
        self.assertTrue(self.obj.fling.vert.forward())
        self.assertTrue(self.obj.fling())
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, False), call(self.obj.selector, False), call(self.obj.selector, True), call(self.obj.selector, True)])

        method = self.fake_jsonrpc_method(method='flingBackward', return_value=True)
        self.assertTrue(self.obj.fling.horiz.backward())
        self.assertTrue(self.obj.fling.horizentally.backward())
        self.assertTrue(self.obj.fling.vert.backward())
        self.assertTrue(self.obj.fling.vertically.backward())
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, False), call(self.obj.selector, False), call(self.obj.selector, True), call(self.obj.selector, True)])

        max_swipes = 1000
        method = self.fake_jsonrpc_method(method='flingToBeginning', return_value=True)
        self.assertTrue(self.obj.fling.horiz.toBeginning())
        self.assertTrue(self.obj.fling.horizentally.toBeginning())
        self.assertTrue(self.obj.fling.vert.toBeginning())
        self.assertTrue(self.obj.fling.vertically.toBeginning(max_swipes=100))
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, False, max_swipes), call(self.obj.selector, False, max_swipes), call(self.obj.selector, True, max_swipes), call(self.obj.selector, True, 100)])

        method = self.fake_jsonrpc_method(method='flingToEnd', return_value=True)
        self.assertTrue(self.obj.fling.horiz.toEnd())
        self.assertTrue(self.obj.fling.horizentally.toEnd())
        self.assertTrue(self.obj.fling.vert.toEnd())
        self.assertTrue(self.obj.fling.vertically.toEnd(max_swipes=100))
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, False, max_swipes), call(self.obj.selector, False, max_swipes), call(self.obj.selector, True, max_swipes), call(self.obj.selector, True, 100)])

    def test_scroll(self):
        steps = 100
        max_swipes = 1000
        method = self.fake_jsonrpc_method(method='scrollForward', return_value=True)
        self.assertTrue(self.obj.scroll.horiz.forward())
        self.assertTrue(self.obj.scroll.horizentally.forward())
        self.assertTrue(self.obj.scroll.vert.forward())
        self.assertTrue(self.obj.scroll(steps=20))
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, False, steps), call(self.obj.selector, False, steps), call(self.obj.selector, True, steps), call(self.obj.selector, True, 20)])

        method = self.fake_jsonrpc_method(method='scrollBackward', return_value=True)
        self.assertTrue(self.obj.scroll.horiz.backward())
        self.assertTrue(self.obj.scroll.horizentally.backward())
        self.assertTrue(self.obj.scroll.vert.backward())
        self.assertTrue(self.obj.scroll.vertically.backward(steps=20))
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, False, steps), call(self.obj.selector, False, steps), call(self.obj.selector, True, steps), call(self.obj.selector, True, 20)])

        method = self.fake_jsonrpc_method(method='scrollToBeginning', return_value=True)
        self.assertTrue(self.obj.scroll.horiz.toBeginning())
        self.assertTrue(self.obj.scroll.horizentally.toBeginning())
        self.assertTrue(self.obj.scroll.vert.toBeginning())
        self.assertTrue(self.obj.scroll.vertically.toBeginning(steps=20, max_swipes=100))
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, False, max_swipes, steps), call(self.obj.selector, False, max_swipes, steps), call(self.obj.selector, True, max_swipes, steps), call(self.obj.selector, True, 100, 20)])

        method = self.fake_jsonrpc_method(method='scrollToEnd', return_value=True)
        self.assertTrue(self.obj.scroll.horiz.toEnd())
        self.assertTrue(self.obj.scroll.horizentally.toEnd())
        self.assertTrue(self.obj.scroll.vert.toEnd())
        self.assertTrue(self.obj.scroll.vertically.toEnd(steps=20, max_swipes=100))
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, False, max_swipes, steps), call(self.obj.selector, False, max_swipes, steps), call(self.obj.selector, True, max_swipes, steps), call(self.obj.selector, True, 100, 20)])

        info = {"text": "..."}
        method = self.fake_jsonrpc_method(method='scrollTo', return_value=True)
        self.assertTrue(self.obj.scroll.horiz.to(**info))
        self.assertTrue(self.obj.scroll.horizentally.to(**info))
        self.assertTrue(self.obj.scroll.vert.to(**info))
        self.assertTrue(self.obj.scroll.vertically.to(**info))
        self.assertEqual(method.call_args_list,
                         [call(self.obj.selector, Selector(**info), False), call(self.obj.selector, Selector(**info), False), call(self.obj.selector, Selector(**info), True), call(self.obj.selector, Selector(**info), True)])

    def test_wait(self):
        timeout = 3000
        method = self.fake_jsonrpc_method(method='waitUntilGone', return_value=True)
        self.assertTrue(self.obj.wait.gone())
        method.assert_called_once_with(self.obj.selector, timeout)
        method = self.fake_jsonrpc_method(method='waitForExists', return_value=True)
        self.assertTrue(self.obj.wait.exists(timeout=10))
        method.assert_called_once_with(self.obj.selector, 10)

    def test_child_by_text(self):
        method = self.fake_jsonrpc_method(method='childByText', return_value='myname')
        kwargs = {"className": "android", "text": "patern match text"}
        generic_obj = self.obj.child_by_text("child text", **kwargs)
        method.assert_called_once_with(Selector(**self.kwargs), Selector(**kwargs), "child text")
        self.assertEqual("myname", generic_obj.selector)

    def test_child_by_text_allow_scroll_search(self):
        method = self.fake_jsonrpc_method(method='childByText', return_value='myname')
        kwargs = {"className": "android", "text": "patern match text"}
        generic_obj = self.obj.child_by_text("child text", allow_scroll_search=False, **kwargs)
        method.assert_called_once_with(
            Selector(**self.kwargs), Selector(**kwargs), "child text", False)
        self.assertEqual("myname", generic_obj.selector)

    def test_child_by_description(self):
        method = self.fake_jsonrpc_method(method='childByDescription', return_value='myname')
        kwargs = {"className": "android", "text": "patern match text"}
        generic_obj = self.obj.child_by_description("child text", **kwargs)
        method.assert_called_once_with(
            Selector(**self.kwargs), Selector(**kwargs), "child text")
        self.assertEqual("myname", generic_obj.selector)

    def test_child_by_description_allow_scroll_search(self):
        method = self.fake_jsonrpc_method(method='childByDescription', return_value='myname')
        kwargs = {"className": "android", "text": "patern match text"}
        generic_obj = self.obj.child_by_description("child text", allow_scroll_search=False, **kwargs)
        method.assert_called_once_with(
            Selector(**self.kwargs), Selector(**kwargs), "child text", False)
        self.assertEqual("myname", generic_obj.selector)

    def test_child_by_instance(self):
        method = self.fake_jsonrpc_method(method='childByInstance', return_value='myname')
        kwargs = {"className": "android", "text": "patern match text"}
        generic_obj = self.obj.child_by_instance(1234, **kwargs)
        method.assert_called_once_with(Selector(**self.kwargs), Selector(**kwargs), 1234)
        self.assertEqual("myname", generic_obj.selector)

    def test_count(self):
        method = self.fake_jsonrpc_method(method='count', return_value=10)
        self.assertEqual(self.obj.count, 10)
        method.assert_called_once_with(Selector(**self.kwargs))

    def test_len(self):
        self.fake_jsonrpc_method(method='count', return_value=10)
        self.assertEqual(len(self.obj), 10)

    def test_instance_list(self):
        count = 10
        self.fake_jsonrpc_method(method='count', return_value=count)
        for i in range(count):
            self.assertEqual(self.obj[i].selector["instance"], i)
        with self.assertRaises(IndexError):
            self.obj[count]
        self.fake_jsonrpc_method(method='count', return_value=1)
        self.assertEqual(self.obj[0], self.obj)

    def test_instance_iter(self):
        count = 10
        self.fake_jsonrpc_method(method='count', return_value=count)
        for index, inst in enumerate(self.obj):
            self.assertEqual(inst.selector["instance"], index)

    def test_left(self):
        method = self.fake_jsonrpc_method(method='objInfo', side_effect=[
            {"bounds": {'top': 200, 'bottom': 250, 'left': 100, 'right': 150}},
            {"bounds": {'top': 250, 'bottom': 300, 'left': 150, 'right': 200}},
            {"bounds": {'top': 200, 'bottom': 300, 'left': 150, 'right': 200}},
            {"bounds": {'top': 200, 'bottom': 300, 'left': 50, 'right': 100}}
        ])
        self.fake_jsonrpc_method(method='count', return_value=3)
        self.assertEqual(self.obj.left().selector["instance"], 2)

    def test_right(self):
        method = self.fake_jsonrpc_method(method='objInfo', side_effect=[
            {"bounds": {'top': 200, 'bottom': 250, 'left': 100, 'right': 150}},
            {"bounds": {'top': 250, 'bottom': 300, 'left': 150, 'right': 200}},
            {"bounds": {'top': 200, 'bottom': 300, 'left': 50, 'right': 100}},
            {"bounds": {'top': 200, 'bottom': 300, 'left': 150, 'right': 200}}
        ])
        self.fake_jsonrpc_method(method='count', return_value=3)
        self.assertEqual(self.obj.right().selector["instance"], 2)

    def test_up(self):
        method = self.fake_jsonrpc_method(method='objInfo', side_effect=[
            {"bounds": {'top': 200, 'bottom': 250, 'left': 100, 'right': 150}},
            {"bounds": {'top': 250, 'bottom': 300, 'left': 100, 'right': 150}},
            {"bounds": {'top': 150, 'bottom': 200, 'left': 150, 'right': 200}},
            {"bounds": {'top': 150, 'bottom': 200, 'left': 100, 'right': 200}}
        ])
        self.fake_jsonrpc_method(method='count', return_value=3)
        self.assertEqual(self.obj.up().selector["instance"], 2)

    def test_down(self):
        method = self.fake_jsonrpc_method(method='objInfo', side_effect=[
            {"bounds": {'top': 200, 'bottom': 250, 'left': 100, 'right': 150}},
            {"bounds": {'top': 250, 'bottom': 300, 'left': 150, 'right': 200}},
            {"bounds": {'top': 150, 'bottom': 200, 'left': 150, 'right': 200}},
            {"bounds": {'top': 250, 'bottom': 300, 'left': 100, 'right': 150}}
        ])
        self.fake_jsonrpc_method(method='count', return_value=3)
        self.assertEqual(self.obj.down().selector["instance"], 2)

    def test_multiple_matched_down(self):
        method = self.fake_jsonrpc_method(method='objInfo', side_effect=[
            {"bounds": {'top': 200, 'bottom': 250, 'left': 100, 'right': 150}},
            {"bounds": {'top': 250, 'bottom': 300, 'left': 150, 'right': 200}},
            {"bounds": {'top': 150, 'bottom': 200, 'left': 150, 'right': 200}},
            {"bounds": {'top': 275, 'bottom': 300, 'left': 100, 'right': 150}},
            {"bounds": {'top': 300, 'bottom': 350, 'left': 100, 'right': 150}},
            {"bounds": {'top': 250, 'bottom': 275, 'left': 100, 'right': 150}}
        ])
        self.fake_jsonrpc_method(method='count', return_value=5)
        self.assertEqual(self.obj.down().selector["instance"], 4)

class TestAutomatorDeviceNamedUiObject(unittest.TestCase):

    def setUp(self):
        self.device = MagicMock()
        self.rpc_client = MagicMock()
        self.device.server.jsonrpc.return_value = self.rpc_client
        self.name = "my-name"
        self.obj = AutomatorDeviceNamedUiObject(self.device, self.name)

    def test_child(self):
        method = fake_jsonrpc_method(self.rpc_client, method='getChild', return_value='another-name')
        kwargs = {"className": "android", "text": "patern match text"}
        generic_obj = self.obj.child(**kwargs)
        method.assert_called_once_with(self.name, Selector(**kwargs))
        self.assertEqual(generic_obj.selector, method.return_value)

    def test_sibling(self):
        method = fake_jsonrpc_method(self.rpc_client, method='getFromParent', return_value='another-name')
        kwargs = {"className": "android", "text": "patern match text"}
        generic_obj = self.obj.sibling(**kwargs)
        method.assert_called_once_with(self.name, Selector(**kwargs))
        self.assertEqual(generic_obj.selector, method.return_value)
