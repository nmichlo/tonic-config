# tonic-config ![Tests Status](https://github.com/nmichlo/tonic-config/workflows/Tests/badge.svg)
📜 Tonic is a lightweight configuration framework and experiment manager for Python, combining the most notable aspects of Gin and Sacred.

## Why?

- Gin-config is designed around their own configuration files and syntax, and is difficult to work with programatically.

- Sacred has a larger yet familiar featureset, but the configuration syntax is very different. The additional advantage of tonic-config is that it has the concept of global variables.

## Getting Started

### 1. Minimal Example

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


### 2. Configuring Classes

If a class is annotated, the configuration will apply to parameters of the __init__ method.

Other methods within the class also need to be annotated separately.

```python
import tonic

@tonic.config
class Fizz(object):
    def __init__(self, foo=None):
        print(foo)
    
    @tonic.config
    def buzz(bar=None):
        print(bar)

Fizz().buzz()

tonic.config.set({
    'Fizz.foo': 1,
    'Fizz.buzz.bar': 100,
})

Fizz().buzz()
```

The output of the above will be:
```
>>> None
>>> None
>>> 1
>>> 100
```

### 3. Namespaces

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


### 4. Global Configurations

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

### 5. Instanced Values

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

### 6. Saving/Loading Configurations

Save and load your configurations using `tonic.config.save('file.toml')` and `tonic.config.load('file.toml')`


### 7. Multiple Configurations

`tonic.config` is an instance of `tonic.Config()`

you can instantiate your own version for example: `my_config = tonic.Config()`
and use `my_config` instead of `tonic.config`
