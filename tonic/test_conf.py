import tonic
import numpy as np


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
            return np.random.randint(9999999, size=99) # yes... this could still fail, but highly unlikely

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



        config.print()



# ========================================================================= #
# END                                                                       #
# ========================================================================= #
