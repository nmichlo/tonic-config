# tonic-config
📜 Tonic is a lightweight configuration framework and experiment manager for Python, combining the most notable aspects of Gin and Sacred.


## Getting Started

Configurations are handled via annotating functions.
With tonic, only default parameters of functions can be configured.

The most simple tonic example looks as follows:
```python
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
```

When run, the above will output:
```
>>> 1000 None
>>> 1000 1337
>>> 1000 bar
```

Notice in the above example even if a function has been configured, manually
specifing the named values when calling the function takes priority.


### Namespaces

Tonic groups parameters of registered functions under their
own namespace by default, corresponding to the hierarchy of
objects within the file to that function.

If you manually specify the namespace of a configured function, any
other configured function with the same namespace will also share the same
configurations for parameters.

But can no longer access the function under the default name.
**this condition might be relaxed in future versions**

```python
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
```

Outputs:
```
>>> 1 bar
>>> 2 bar
```


### Global Configurations

Tonic also supports global parameter configurations by using the `*` namespace.

Any function with a parameter that matches the global namespace will be configured.

Explicit configuration of a namespace with matching parameters will take priority.

```python
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
```

The above will output:
```
>>> foo bar global
>>> fizz bang global
>>> foo bar global
>>> fizz bang overwritten
```

### 4. Instanced Values

prefixing any key in the configuration with an `@` marks the
corresponding value as an instanced value.

The requirement for a value that is instanced, is that it is an already
registered/configured class or function.

Marking a parameter as instanced means that the function/class
is called on every function with a matching parameter, with the
resulting value from the call taking its place.

Every time the configuration is updated, these instanced
values are lazily recomputed.


```python
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
```

The above will output the following:
```
>>> None
>>> None
>>> 2
>>> 2
>>> 7
>>> 7
```


### Multiple Configurations

`tonic.config` is an instance of `tonic.Config()`

you can instantiate your own version for example: `my_config = tonic.Config()`
and use `my_config` instead of `tonic.config`
