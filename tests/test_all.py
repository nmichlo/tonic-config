import tonic
import subprocess
import sys
import random as ran


# ========================================================================= #
# test_config                                                               #
# ========================================================================= #

def do_test(get_wrapped, config, target):
    # reset tonic config
    tonic_config = tonic.Config()
    # @tonic.config
    wrapped = get_wrapped(tonic_config)
    # set configuration
    tonic_config.set(config)
    # now test
    assert wrapped() == target


def train(optimizer='adam', lr=0.001):
    return optimizer, lr


def test_defaults():
    # reset tonic config
    tonic.config = tonic.Config()
    # @tonic.config
    wrapped = tonic.config(train)
    # set configuration
    tonic.config.set({
        'train.optimizer': 'sgd',
        'train.lr': 0.005,
    })
    # now test
    assert wrapped() == ('sgd', 0.005)

def test_namespaced():
    # reset tonic config
    tonic.config = tonic.Config()
    # @tonic.config
    wrapped = tonic.config('train_namespace.inner_namespace')(train)
    # set configuration
    tonic.config.set({
        'train_namespace.inner_namespace.optimizer': 'sgd',
        'train_namespace.inner_namespace.lr': 0.005,
    })
    # now test
    assert wrapped() == ('sgd', 0.005)

def test_local_nested():
    # NESTED FUNCTION
    def train_nested(optimizer='adam', lr=0.001):
        return optimizer, lr
    # reset tonic config
    tonic.config = tonic.Config()
    # @tonic.config
    wrapped = tonic.config(train_nested)
    # set configuration
    tonic.config.set({
        'test_local_nested.train_nested.optimizer': 'sgd',
        'test_local_nested.train_nested.lr': 0.005,
    })
    # now test
    assert wrapped() == ('sgd', 0.005)

def test_class():
    # NESTED FUNCTION
    class Trainer(object):
        def __init__(self, optimizer='adam', lr=0.001):
            self.optimizer = optimizer
            self.lr = lr
        def get(self):
            return self.optimizer, self.lr
    # reset tonic config
    tonic.config = tonic.Config()
    # @tonic.config
    WrappedCls = tonic.config(Trainer)
    # set configuration
    tonic.config.set({
        'test_class.Trainer.optimizer': 'sgd',
        'test_class.Trainer.lr': 0.005,
    })
    # now test
    assert WrappedCls().get()                          == ('sgd', 0.005)

    # TODO: these dont work | ERROR: multiple values for optimizer
    # assert WrappedCls('radam').get()                 == ('radam', 0.005)
    # assert WrappedCls('radam', 0.1).get()            == ('radam', 0.1)
    # assert WrappedCls('radam', lr=0.1).get()         == ('radam', 0.1)

    assert WrappedCls(lr=0.1).get()                    == ('sgd', 0.1)
    assert WrappedCls(optimizer='radam', lr=0.1).get() == ('radam', 0.1)
    assert WrappedCls(optimizer='radam').get()         == ('radam', 0.005)


def test_general():
        config = tonic.Config()

        @config
        def random():
            return tuple(ran.randint(0, 999999999) for i in range(99))  # yes... this could still conflict, but highly unlikely

        @config
        def test(a, b, c=2, d=3, e=-2):
            return (a, b, c, d, e)

        @config('test.test')
        def test2(a, b, c=2, d=3, e=-1, seed=None):
            return (a, b, c, d, e, seed)

        @config
        def testran1(random=None):
            return random

        @config
        def testran2(random=None):
            return random

        config.set({
            # global parameters
            '*.seed': 100,
            '*.e': -100,

            # Per Instance Parameters
            '@*.random': random,

            'test_general.test.c': 55,
            'test.test.c': 77,
            'test.test.d': 100,
            'test.test.e': 100,
        })

        assert test(0, 1, c=77) == (0, 1, 77, 3, -100)
        assert test(0, 1)       == (0, 1, 55, 3, -100)
        assert test2(0, 1)      == (0, 1, 77, 100, 100, 100)
        assert test2(0, 1)      == (0, 1, 77, 100, 100, 100)

        # check equal per func
        ran1_1a, ran1_1b = testran1(), testran1()
        ran1_2a, ran1_2b = testran2(), testran2()
        assert ran1_1a is ran1_1b
        assert ran1_2a is ran1_2b
        assert ran1_1a is not ran1_2a

        config.save_config('test_conf.toml')
        config.reset()

        assert test(0, 1)  == (0, 1, 2, 3, -2)
        assert test(0, 1)  == (0, 1, 2, 3, -2)
        assert test2(0, 1) == (0, 1, 2, 3, -1, None)
        assert test2(0, 1) == (0, 1, 2, 3, -1, None)

        # check equal per func
        ran2_1a, ran2_1b = testran1(), testran1()
        ran2_2a, ran2_2b = testran2(), testran2()
        assert ran2_1a is None
        assert ran2_1b is None
        assert ran2_2a is None
        assert ran2_2b is None

        # check not equal to previous
        assert ran2_1a is not ran1_1a
        assert ran2_2a is not ran1_2a

        config.load_config('test_conf.toml')

        assert test(0, 1)  == (0, 1, 55, 3, -100)
        assert test(0, 1)  == (0, 1, 55, 3, -100)
        assert test2(0, 1) == (0, 1, 77, 100, 100, 100)
        assert test2(0, 1) == (0, 1, 77, 100, 100, 100)

        ran3_1a, ran3_1b = testran1(), testran1()
        ran3_2a, ran3_2b = testran2(), testran2()
        assert ran3_1a is ran3_1b
        assert ran3_2a is ran3_2b
        assert ran3_1a is not ran3_2a

        # check not equal to previous
        assert ran3_1a is not ran1_1a
        assert ran3_2a is not ran1_2a
        assert ran3_1a is not ran2_1a
        assert ran3_2a is not ran2_2a

        assert config.to_pretty_string() == '\x1b[90m{\x1b[0m\n  \x1b[90m"\x1b[92m\x1b[0m\x1b[95mtest.test\x1b[90m.\x1b[94mc\x1b[90m"\x1b[0m: \x1b[93m77\x1b[90m,\x1b[0m\n  \x1b[90m"\x1b[92m\x1b[0m\x1b[95mtest.test\x1b[90m.\x1b[94md\x1b[90m"\x1b[0m: \x1b[93m100\x1b[90m,\x1b[0m\n  \x1b[90m"\x1b[92m\x1b[0m\x1b[95mtest.test\x1b[90m.\x1b[94me\x1b[90m"\x1b[0m: \x1b[93m100\x1b[90m,\x1b[0m  \x1b[90m# "*.e\x1b[90m": -100,\x1b[0m\n  \x1b[90m"\x1b[92m\x1b[0m\x1b[95mtest.test\x1b[90m.\x1b[94mseed\x1b[90m"\x1b[0m: \x1b[91m100\x1b[90m,\x1b[0m  \x1b[90m# "*.seed\x1b[90m": 100,\x1b[0m\n  \x1b[90m"\x1b[92m\x1b[0m\x1b[95mtest_general.test\x1b[90m.\x1b[94mc\x1b[90m"\x1b[0m: \x1b[93m55\x1b[90m,\x1b[0m\n\x1b[90m# \x1b[90m"\x1b[92m\x1b[0m\x1b[95mtest_general.test\x1b[90m.\x1b[94md\x1b[90m"\x1b[0m: \x1b[90m,\x1b[0m\n  \x1b[90m"\x1b[92m\x1b[0m\x1b[95mtest_general.test\x1b[90m.\x1b[94me\x1b[90m"\x1b[0m: \x1b[91m-100\x1b[90m,\x1b[0m  \x1b[90m# "*.e\x1b[90m": -100,\x1b[0m\n  \x1b[90m"\x1b[92m@\x1b[0m\x1b[95mtest_general.testran1\x1b[90m.\x1b[94mrandom\x1b[90m"\x1b[0m: \x1b[91m\'test_general.random\'\x1b[90m,\x1b[0m  \x1b[90m# "@*.random\x1b[90m": \'test_general.random\',\x1b[0m\n  \x1b[90m"\x1b[92m@\x1b[0m\x1b[95mtest_general.testran2\x1b[90m.\x1b[94mrandom\x1b[90m"\x1b[0m: \x1b[91m\'test_general.random\'\x1b[90m,\x1b[0m  \x1b[90m# "@*.random\x1b[90m": \'test_general.random\',\x1b[0m\n\x1b[90m}\x1b[0m'

def test_readme_get_started():
    @tonic.config
    def foobar(foo, bar=None):
        return (foo, bar)

    # no configuration used for call
    assert foobar(1000) == (1000, None)

    # set configuration and reconfigure registered functions
    # tonic.config.reset() resets configuration
    # tonic.config.update() merges the given configuration with the previous, overwriting values.
    tonic.config.set({
        'test_readme_get_started.foobar.bar': 1337
    })

    # call functions with new configuration
    assert foobar(1000) == (1000, 1337)
    assert foobar(1000, bar='bar') == (1000, 'bar')

def test_readme_namespaces():
    @tonic.config('fizz.buzz')
    def foobar1(foo=1, bar=None):
        return (foo, bar)

    @tonic.config('fizz.buzz')
    def foobar2(foo=2, bar=None):
        return (foo, bar)

    tonic.config.set({
        'fizz.buzz.bar': 'bar'
    })

    assert foobar1() == (1, 'bar')
    assert foobar2() == (2, 'bar')

def test_readme_global():
    @tonic.config
    def foobar(foo=None, bar=None, buzz=None):
        return (foo, bar, buzz)

    @tonic.config
    def fizzbang(fizz=None, bang=None, buzz=None):
        return (fizz, bang, buzz)

    tonic.config.set({
        '*.buzz': 'global',
        # configure foobar
        'test_readme_global.foobar.foo': 'foo',
        'test_readme_global.foobar.bar': 'bar',
        # configure fizzbang
        'test_readme_global.fizzbang.fizz': 'fizz',
        'test_readme_global.fizzbang.bang': 'bang',
    })

    assert foobar() == ('foo', 'bar', 'global')
    assert fizzbang() == ('fizz', 'bang', 'global')

    # merge the given config with the previous
    # reset config instead with tonic.config.reset()
    tonic.config.update({
        'test_readme_global.fizzbang.buzz': 'overwritten'
    })

    assert foobar() == ('foo', 'bar', 'global')
    assert fizzbang() == ('fizz', 'bang', 'overwritten')


def test_readme_instanced():
    COUNT = 0

    @tonic.config
    def counter(step_size=1):
        nonlocal COUNT
        COUNT += step_size
        return COUNT

    @tonic.config
    def print_count(count=None):
        return count

    assert print_count() == None
    assert print_count() == None

    tonic.config.set({
        'test_readme_instanced.counter.step_size': 2,
        '@test_readme_instanced.print_count.count': 'test_readme_instanced.counter'
    })

    assert print_count() == 2
    assert print_count() == 2

    tonic.config.update({
        'test_readme_instanced.counter.step_size': 3,
    })

    assert print_count() == 5
    assert print_count() == 5


def test_examples():
    example_01 = subprocess.getoutput(f'{sys.executable} examples/01_get_started.py')
    assert example_01 == '1000 None\n1000 1337\n1000 bar'
    example_02 = subprocess.getoutput(f'{sys.executable} examples/02_configure_classes.py')
    assert example_02 == 'None\nNone\n1\n100'
    example_03 = subprocess.getoutput(f'{sys.executable} examples/03_namespaces.py')
    assert example_03 == '1 bar\n2 bar'
    example_04 = subprocess.getoutput(f'{sys.executable} examples/04_global.py')
    assert example_04 == 'foo bar global\nfizz bang global\nfoo bar global\nfizz bang overwritten'
    example_05 = subprocess.getoutput(f'{sys.executable} examples/05_instanced_values.py')
    assert example_05 == 'None\nNone\n2\n2\n7\n7'


# ========================================================================= #
# END                                                                       #
# ========================================================================= #
