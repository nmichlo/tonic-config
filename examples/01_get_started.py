"""
Example of how to get started.
Please see the corresponding section in the README

EXPECTED OUTPUT:
>>> 1000 None
>>> 1000 1337
>>> 1000 bar
"""

import tonic

@tonic.config
def foobar(foo, bar=None):
    print(foo, bar)

# no configuration used for call
foobar(1000)

# set configuration and reconfigure registered functions
# tonic.config.reset() resets configuration
# tonic.config.update() merges the given configuration with the previous, overwriting values.
tonic.config.set({
    'foobar.bar': 1337
})

# call functions with new configuration
foobar(1000)
foobar(1000, bar='bar')