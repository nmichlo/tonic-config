"""
Example of using instanced values.
Please see the corresponding section in the README

EXPECTED OUTPUT:
>>> None
>>> None
>>> 2
>>> 2
>>> 7
>>> 7
"""

import tonic


COUNT = 0

@tonic.config
def counter(step_size=1):
    global COUNT
    COUNT += step_size
    return COUNT

@tonic.config
def print_count(count=None):
    print(count)

print_count()
print_count()

tonic.config.set({
    'counter.step_size': 2,
    '@print_count.count': 'counter'
})

print_count()
print_count()

tonic.config.update({
    'counter.step_size': 5,
})

print_count()
print_count()
