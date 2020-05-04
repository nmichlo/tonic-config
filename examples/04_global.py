"""
Example of using global values.
Please see the corresponding section in the README

EXPECTED OUTPUT:
>>> foo bar global
>>> fizz bang global
>>> foo bar global
>>> fizz bang overwritten
"""

import tonic

@tonic.config
def foobar(foo=None, bar=None, buzz=None):
    print(foo, bar, buzz)

@tonic.config
def fizzbang(fizz=None, bang=None, buzz=None):
    print(fizz, bang, buzz)

tonic.config.set({
    '*.buzz': 'global',
    # configure foobar
    'foobar.foo': 'foo',
    'foobar.bar': 'bar',
    # configure fizzbang
    'fizzbang.fizz': 'fizz',
    'fizzbang.bang': 'bang',
})

foobar()
fizzbang()

# merge the given config with the previous
# reset config instead with tonic.config.reset()
tonic.config.update({
    'fizzbang.buzz': 'overwritten'
})

foobar()
fizzbang()
