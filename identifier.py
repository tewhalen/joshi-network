"""
An extremly dumb dictionary that assigns an incrementing integer to each new key.
"""

from collections import defaultdict


class Identifier(defaultdict):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_factory = lambda: len(self) + 1


if __name__ == "__main__":
    c = Identifier()
    assert c["hello"] == 1
    assert c["check"] == 2
    assert c["hello"] == 1
