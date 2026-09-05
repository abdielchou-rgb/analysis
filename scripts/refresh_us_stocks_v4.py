# -*- coding: utf-8 -*-
"""强制 IPv4 包装：stockanalysis.com 在 IPv6 下连接极慢（~43s/只），IPv4 仅 ~1.4s/只。"""

import socket

_orig_getaddrinfo = socket.getaddrinfo


def _v4_only(host, *args, **kwargs):
    return [x for x in _orig_getaddrinfo(host, *args, **kwargs) if x[0] == socket.AF_INET]


socket.getaddrinfo = _v4_only

import sys

sys.argv = [sys.argv[0]] + [a for a in sys.argv[1:] if a != "--ipv4"]
exec(open(r"D:\Claude\projects\2hao-analyst\scripts\refresh_us_stocks.py", encoding="utf-8").read())
