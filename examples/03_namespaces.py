"""
Example of using custom namespaces.
Please see the corresponding section in the README

EXPECTED OUTPUT:
>>> 1 bar
>>> 2 bar
"""

import tonic


@tonic.config('fizz.buzz')
def foobar1(foo=1, bar=None):
    print(foo, bar)

@tonic.config('fizz.buzz')
def foobar2(foo=2, bar=None):
    print(foo, bar)

tonic.config.set({
    'fizz.buzz.bar': 'bar'
})

foobar1()
foobar2()
