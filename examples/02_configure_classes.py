"""
Example of configuring classes and methods.
Please see the corresponding section in the README

EXPECTED OUTPUT:
>>> None
>>> None
>>> 1
>>> 100
"""

import tonic

@tonic.config
class Fizz(object):
    def __init__(self, foo=None):
        print(foo)

    @tonic.config
    def buzz(self, bar=None):
        print(bar)

Fizz().buzz()

tonic.config.set({
    'Fizz.foo': 1,
    'Fizz.buzz.bar': 100,
})

Fizz().buzz()
